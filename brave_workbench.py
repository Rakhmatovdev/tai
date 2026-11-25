"""Usage, persistent file recovery and local microphone calibration pages."""
import threading,time,statistics
from pathlib import Path
from PyQt6.QtCore import Qt,QTimer,pyqtSignal
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QLabel,QListWidget,QListWidgetItem,QPushButton,QSpinBox,QMessageBox
from brave_i18n import translate as t
from core import usage,workspace_store,file_backups

def usage_page(center):
    page=QWidget();layout=QVBoxLayout(page);report=QLabel();report.setWordWrap(True);layout.addWidget(report)
    report.setTextFormat(Qt.TextFormat.PlainText)
    note=QLabel(t('Bu hajmlar lokal hisoblanadi. Ular token, narx yoki qolgan API kvotasi emas. Aniq limitlar provayder hisobida ko‘rinadi.'));note.setWordWrap(True);layout.addWidget(note);layout.addStretch()
    def refresh():
        from core import gemini
        data=usage.snapshot();lines=[t('Sessiya davomiyligi')+f": {data['seconds']//60:02}:{data['seconds']%60:02}",t('Chat so‘rovlari')+': '+str(data['chat_requests'])]
        for key,label in [('chat_bytes','Matn va fayl yuborildi'),('audio_sent','Ovoz yuborildi'),('audio_received','Ovoz olindi')]:lines.append(t(label)+f": {data[key]/1024:.1f} KB")
        lines.append(t('Yordamchi model so‘rovlari')+': '+str(data['side_calls']))
        for model,seconds in gemini.cooldown_snapshot().items():lines.append(t('Model tanaffusi')+f': {model} · {seconds} s')
        report.setText('\n\n'.join(lines))
    timer=QTimer(page);timer.setInterval(1000);timer.timeout.connect(refresh);timer.start();refresh();return page

class RecoveryPage(QWidget):
    ready=pyqtSignal(str)
    def __init__(self,center):
        super().__init__();self.center=center;layout=QVBoxLayout(self)
        note=QLabel(t('Brave fayl boshqaruvchisi yozgan fayllarning oldingi nusxalari. Keyinroq o‘zgargan fayl avtomatik almashtirilmaydi.'));note.setWordWrap(True);layout.addWidget(note)
        self.list=QListWidget();layout.addWidget(self.list,1)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.restore=QPushButton(t('Oldingi nusxani tiklash'));self.restore.setStyleSheet(center.button_style);self.restore.clicked.connect(self.run);layout.addWidget(self.restore)
        refresh=QPushButton(t('Yangilash'));refresh.setStyleSheet(center.button_style);refresh.clicked.connect(self.refresh);layout.addWidget(refresh)
        remove=QPushButton(t('Nusxani o‘chirish'));remove.setStyleSheet(center.button_style);remove.clicked.connect(self.delete);layout.addWidget(remove)
        self.ready.connect(self.done);self.refresh()
        self.list.currentItemChanged.connect(lambda item:self.restore.setEnabled(bool(item and not item.data(Qt.ItemDataRole.UserRole).get('restored'))))
    def refresh(self):
        self.list.clear()
        rows=workspace_store.read('file-backups.json',[]) if self.center.controller.persist else []
        for row in reversed(rows):
            item=QListWidgetItem((t('Tiklangan')+' · ' if row.get('restored') else '')+row['at'][:19]+' · '+row['path']);item.setData(Qt.ItemDataRole.UserRole,row);self.list.addItem(item)
    def run(self):
        row=self.list.currentItem()
        if not row:return
        if not self.center.controller.policy['permissions']['files']:self.status.setText(t('Fayl ruxsati o‘chiq.'));return
        if self.center.win.can_change_chat and not self.center.win.can_change_chat():self.status.setText(t('Avval joriy vazifa tugashini kuting.'));return
        value=row.data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self,t('Oldingi nusxani tiklash'),t('Fayl oldingi nusxa bilan almashtirilsinmi?')+'\n'+value['path'],QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        self.restore.setEnabled(False)
        def work():
            try:
                if not self.center.controller.policy['permissions']['files']:raise PermissionError(t('Fayl ruxsati o‘chiq.'))
                result=t('Nusxa tiklandi.')+' '+file_backups.restore(value['id'])
            except Exception as error:result=str(error)
            try:self.ready.emit(result)
            except RuntimeError:pass
        threading.Thread(target=work,daemon=True).start()
    def done(self,result):self.restore.setEnabled(True);self.status.setText(result);self.refresh()
    def delete(self):
        row=self.list.currentItem()
        if row and self.center.controller.policy['permissions']['files']:
            file_backups.delete(row.data(Qt.ItemDataRole.UserRole)['id']);self.refresh()

class VoicePage(QWidget):
    def __init__(self,center):
        super().__init__();self.center=center;self.phase=None;self.samples=[];self.noise=[];layout=QVBoxLayout(self)
        note=QLabel(t('Sinovda ovoz Gemini’ga uzatilmaydi va yozib saqlanmaydi. Avval jim turing, keyin odatdagi ovozda gapiring.'));note.setWordWrap(True);layout.addWidget(note)
        self.status=QLabel(t('Brave ulangan va ovozli rejimda bo‘lishi kerak.'));self.status.setWordWrap(True);layout.addWidget(self.status)
        self.start=QPushButton(t('Mikrofonni sinash'));self.start.setStyleSheet(center.button_style);self.start.clicked.connect(self.begin);layout.addWidget(self.start)
        layout.addWidget(QLabel(t('Gap tugashidan keyingi kutish · ms')))
        self.silence=QSpinBox();self.silence.setRange(200,3000)
        from memory.config_manager import get_turn_tuning
        self.silence.setValue(get_turn_tuning()['silence_ms']);layout.addWidget(self.silence)
        apply=QPushButton(t('Ovoz sozlamasini qo‘llash'));apply.setStyleSheet(center.button_style);apply.clicked.connect(self.apply);layout.addWidget(apply);layout.addStretch()
        self.timer=QTimer(self);self.timer.setInterval(100);self.timer.timeout.connect(self.tick)
        center.win._calibration_level_sig.connect(self.observe);center.finished.connect(self.stop)
    def begin(self):
        snapshot=self.center.win.get_diagnostics() if self.center.win.get_diagnostics else {}
        if not snapshot.get('microphone') or not self.center.controller.policy['permissions']['microphone'] or self.center.win._text_only:
            self.status.setText(t('Brave ulangan va ovozli rejimda bo‘lishi kerak.'));return
        self.center.win._do_interrupt();self.center.win._calibrating=True;self.phase='quiet';self.samples=[];self.deadline=time.monotonic()+3
        self.start.setEnabled(False);self.status.setText(t('3 soniya jim turing…'));self.timer.start()
    def observe(self,level):
        if self.phase:self.samples.append(max(0,float(level)))
    def tick(self):
        if time.monotonic()<self.deadline:return
        if self.phase=='quiet':
            self.noise=self.samples;self.samples=[];self.phase='speech';self.deadline=time.monotonic()+5;self.status.setText(t('5 soniya odatdagi ovozda gapiring…'));return
        quiet=statistics.median(self.noise) if self.noise else 0;speech=statistics.median(self.samples) if self.samples else 0
        if not self.samples or speech<max(.015,quiet*1.5):self.status.setText(t('Ovoz yetarlicha ajralmadi. Mikrofonni yaqinlashtirib qayta sinang.'))
        else:self.silence.setValue(800 if quiet>.06 else 550);self.status.setText(t('Sinov tugadi. Tavsiya qilingan kutish vaqtini qo‘llashingiz mumkin.')+f' RMS: {quiet:.3f} → {speech:.3f}')
        self.stop()
    def stop(self,*_):self.timer.stop();self.phase=None;self.center.win._calibrating=False;self.start.setEnabled(True)
    def apply(self):
        self.stop()
        from memory.config_manager import save_turn_tuning
        save_turn_tuning({'enabled':True,'silence_ms':self.silence.value()});self.center.controller.save()
        self.status.setText(t('Ovoz sozlamasi saqlandi.'))
