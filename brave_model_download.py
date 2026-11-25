"""Explicit, cancellable model pulls through the configured loopback server."""
import json
import os
import shutil
from pathlib import Path
from PyQt6.QtCore import QByteArray,QObject,QTimer,QUrl,pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager,QNetworkProxy,QNetworkRequest,QNetworkReply
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLineEdit,QLabel,QPushButton,QProgressBar
from core.ollama_chat import local_url,local_model
from brave_i18n import translate as t


class ModelPull(QObject):
    progress=pyqtSignal(object)
    finished=pyqtSignal(str,bool)

    def __init__(self,url,model,parent=None):
        super().__init__(parent)
        self.url,self.model=local_url(url),local_model(model)
        self.manager=QNetworkAccessManager(self)
        self.manager.setProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))
        self.reply=None;self.buffer=bytearray();self.ended=False
        self.idle=QTimer(self);self.idle.setSingleShot(True);self.idle.timeout.connect(lambda:self.finish('Yuklash javobi uzildi. Qayta urinib davom ettiring.'))
        self.deadline=QTimer(self);self.deadline.setSingleShot(True);self.deadline.timeout.connect(lambda:self.finish('Yuklash vaqti tugadi. Qayta urinib davom ettiring.'))

    def start(self):
        request=QNetworkRequest(QUrl(self.url+'/api/pull'))
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader,'application/json')
        self.reply=self.manager.post(request,QByteArray(json.dumps({'model':self.model,'stream':True}).encode()))
        self.reply.readyRead.connect(self.read)
        self.reply.finished.connect(self.received)
        self.idle.start(120000);self.deadline.start(3600000)

    def read(self):
        if self.ended or self.reply is None:return
        self.buffer.extend(bytes(self.reply.readAll()))
        if len(self.buffer)>1024*1024:
            self.finish('Ollama noto‘g‘ri javob qaytardi. Qayta urinib ko‘ring.');return
        if self.reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)!=200:return
        while b'\n' in self.buffer and not self.ended:
            line,_,rest=self.buffer.partition(b'\n');self.buffer=bytearray(rest)
            if line.strip():self.chunk(line)

    def chunk(self,line):
        try:
            data=json.loads(line)
            if not isinstance(data,dict):raise ValueError()
            if data.get('error'):
                error=str(data['error']).lower()
                self.finish('Diskda joy yetarli emas.' if 'space' in error or 'disk' in error else 'Model yuklanmadi. Nom va internetni tekshiring.');return
            self.idle.start(120000)
            status=data.get('status','')
            total,completed=data.get('total'),data.get('completed',0)
            if type(total) is not int or total<=0:total=None
            if type(completed) is not int or completed<0:completed=0
            if status=='success':self.finish();return
            phase='downloading' if total else 'verifying' if isinstance(status,str) and 'verif' in status else 'preparing'
            self.progress.emit({'phase':phase,'total':total,'completed':min(completed,total) if total else 0})
        except (ValueError,TypeError):
            self.finish('Ollama noto‘g‘ri javob qaytardi. Qayta urinib ko‘ring.')

    def received(self):
        if self.ended:return
        self.read()
        if self.ended:return
        code=self.reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if code!=200 or self.reply.error()!=QNetworkReply.NetworkError.NoError:
            self.finish('Ollama lokal manzildan boshqa joyga yo‘naltirdi.' if code and 300<=code<400 else
                        'Model yuklanmadi. Nom va internetni tekshiring.');return
        if self.buffer.strip():self.chunk(bytes(self.buffer))
        if not self.ended:self.finish('Yuklash javobi uzildi. Qayta urinib davom ettiring.')

    def cancel(self):self.finish(cancelled=True)

    def finish(self,error='',cancelled=False):
        if self.ended:return
        self.ended=True;self.idle.stop();self.deadline.stop()
        reply,self.reply=self.reply,None
        if reply is not None:reply.abort();reply.deleteLater()
        self.finished.emit(error,cancelled)


class DownloadDialog(QDialog):
    def __init__(self, form, initial_model=None):
        super().__init__(form.window());self.form=form;self.job=None;self.completed_model=None
        from brave_control_center import style_dialog
        style=style_dialog(self,'Model yuklash');self.resize(540,360)
        from brave_ui import colors
        c=colors()
        self.setStyleSheet(self.styleSheet()+f'QProgressBar {{background:{c.BG};border:1px solid {c.BORDER};border-radius:6px;text-align:center;min-height:20px;}} QProgressBar::chunk {{background:{c.PRI_GHO};border-radius:5px;}}')
        layout=QVBoxLayout(self)
        chosen = initial_model or form.model.currentText().strip() or 'llama3.2:latest'
        self.model=QLineEdit(chosen);self.model.setPlaceholderText('llama3.2:latest');layout.addWidget(self.model)

        # Quick hardware-based download recommendations
        try:
            from core.ollama_resources import sample_hardware
            res = getattr(form, 'resources', None) or sample_hardware()
            from core.model_recommender import suggest_downloads
            suggestions = suggest_downloads(res)
            if suggestions:
                sug_box = QVBoxLayout()
                sug_label = QLabel(t('Noutbukingiz uchun tavsiya etilgan modellar:'))
                sug_box.addWidget(sug_label)
                sug_row = QHBoxLayout()
                for item in suggestions[:3]:
                    btn = QPushButton(f"{item['display']} ({item['size_str']})")
                    btn.setToolTip(item['reason'])
                    btn.setStyleSheet(style)
                    btn.clicked.connect(lambda _, name=item['name']: self.model.setText(name))
                    sug_row.addWidget(btn)
                sug_box.addLayout(sug_row)
                layout.addLayout(sug_box)
        except Exception:
            pass

        root=Path(os.environ.get('OLLAMA_MODELS',str(Path.home()/'.ollama'/'models'))).expanduser()
        while not root.exists() and root.parent!=root:root=root.parent
        free=shutil.disk_usage(root).free/1024**3
        note=QLabel(t('Yuklash internetdan foydalanadi. Model tayyor bo‘lgach offline ishlaydi.')+f'\n{t("Diskda bo‘sh joy")}: {free:.1f} GB\n'+t('Disk ko‘rsatkichi lokal taxmin; server papkasi boshqacha bo‘lishi mumkin.'));note.setWordWrap(True);layout.addWidget(note)
        self.progress=QProgressBar();self.progress.setRange(0,100);self.progress.setValue(0);layout.addWidget(self.progress)
        self.status=QLabel(t('Yuklashni boshlash uchun model nomini tekshiring.'));self.status.setWordWrap(True);layout.addWidget(self.status)
        row=QHBoxLayout();layout.addLayout(row)
        self.start_button=QPushButton(t('Yuklash / davom ettirish'));self.start_button.clicked.connect(self.start)
        self.cancel_button=QPushButton(t('Bekor qilish'));self.cancel_button.clicked.connect(self.stop)
        for button in (self.start_button,self.cancel_button):button.setStyleSheet(style);row.addWidget(button)

    def start(self):
        if self.job:return
        if not self.form.win._capabilities.policy['permissions']['network']:
            self.status.setText(t('Yuklash uchun internet ruxsatini yoqing.'));return
        try:self.job=ModelPull(self.form.url.text(),self.model.text().strip(),self)
        except ValueError as exc:self.status.setText(t(str(exc)));return
        self.model.setEnabled(False);self.start_button.setEnabled(False)
        self.progress.setRange(0,0);self.status.setText(t('Model yuklanmoqda…'))
        self.job.progress.connect(self.update_progress)
        self.job.finished.connect(self.done_pull)
        self.job.start()

    def update_progress(self,value):
        total=value['total'];completed=value['completed']
        if total:
            self.progress.setRange(0,100);self.progress.setValue(int(completed/total*100))
            self.status.setText(t('Joriy qatlam')+f': {completed/1024**2:.1f} / {total/1024**2:.1f} MB')
        else:
            self.progress.setRange(0,0)
            self.status.setText(t('Model tekshirilmoqda…' if value['phase']=='verifying' else 'Yuklash tayyorlanmoqda…'))

    def done_pull(self,error,cancelled):
        job,self.job=self.job,None
        if job:job.deleteLater()
        self.model.setEnabled(True);self.start_button.setEnabled(True)
        self.progress.setRange(0,100);self.progress.setValue(100 if not error and not cancelled else 0)
        self.status.setText(t(error) if error else t('Yuklash to‘xtatildi. Qayta bosib davom ettirishingiz mumkin.' if cancelled else 'Model yuklandi. Sozlamalarda tanlang va Saqlashni bosing.'))
        if not error and not cancelled:
            self.completed_model=self.model.text().strip()
            self.form.model.setEditText(self.completed_model)
            self.form.refresh_models()

    def stop(self):
        if self.job:self.job.cancel()

    def done(self,result):
        self.stop();super().done(result)


def open_download(form, initial_model=None):
    DownloadDialog(form, initial_model=initial_model).exec()
