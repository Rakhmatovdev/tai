"""Reviewable /totext conversion of local audio, images, PDF, DOCX and text."""
from pathlib import Path
from PyQt6.QtCore import Qt,QTimer
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QPlainTextEdit,QPushButton,QFileDialog,QApplication
from brave_i18n import translate as t
from brave_local_jobs import Worker


class TextImport(QDialog):
    def __init__(self,win,paths=()):
        super().__init__(win);self.win=win;self.paths=list(paths);self.worker=None;self.answer='';self.closed=False
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        from brave_control_center import style_dialog
        style=style_dialog(self,'Fayldan matnga · /totext');self.resize(820,600)
        layout=QVBoxLayout(self)
        note=QLabel(t('Audio — lokal nutq modeli; rasm/skan — OCR; PDF, DOCX va matn — lokal o‘qish. Natija avtomatik yuborilmaydi.'))
        note.setWordWrap(True);layout.addWidget(note)
        self.files=QLabel();self.files.setWordWrap(True);layout.addWidget(self.files)
        self.language=QComboBox()
        for name,key in [('Auto','auto'),('O‘zbekcha','uz'),('English','en'),('Русский','ru')]:self.language.addItem(name,key)
        layout.addWidget(self.language)
        self.output=QPlainTextEdit();self.output.setReadOnly(True);layout.addWidget(self.output,1)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        row=QHBoxLayout();layout.addLayout(row);self.buttons={}
        for key,title,callback in [('choose','Fayl tanlash',self.choose),('convert','Matnga aylantirish',self.start),
                ('insert','Chatga qo‘yish',self.insert),('copy','Nusxalash',self.copy),('export','Eksport',self.export),('cancel','Bekor qilish',self.cancel)]:
            button=QPushButton(t(title));button.setStyleSheet(style);button.clicked.connect(callback);row.addWidget(button);self.buttons[key]=button
        self.refresh()
        self.permission_timer=QTimer(self);self.permission_timer.setInterval(100)
        self.permission_timer.timeout.connect(self.check_permission)

    def check_permission(self):
        if self.worker and not self.win._capabilities.policy['permissions']['files']:self.worker.cancel()

    def refresh(self):
        self.files.setText('\n'.join(Path(path).name for path in self.paths) or t('Fayl tanlang'))
        for key in ('choose','convert'):self.buttons[key].setEnabled(not self.worker)
        self.language.setEnabled(not self.worker)
        for key in ('insert','copy','export'):self.buttons[key].setEnabled(not self.worker and bool(self.answer))

    def choose(self):
        paths,_=QFileDialog.getOpenFileNames(self,t('Fayl tanlash'),'','Files (*.txt *.md *.pdf *.docx *.png *.jpg *.jpeg *.webp *.bmp *.tif *.wav *.mp3 *.m4a *.flac *.ogg *.aac *.mp4 *.webm);;All files (*)')
        if paths:self.paths=paths;self.answer='';self.output.clear();self.refresh()

    def start(self):
        if self.worker:return
        allowed=lambda:not self.closed and self.win._capabilities.policy['permissions']['files']
        if not allowed():self.status.setText(t('Fayllarga ruxsat o‘chiq.'));return
        from core.offline_voice import model_directory
        from memory.config_manager import load_api_keys
        from core.text_import import convert
        model=load_api_keys().get('local_stt_path') or str(model_directory());paths=list(self.paths);language=self.language.currentData()
        self.answer='';self.output.clear()
        worker=Worker(self,lambda cancel,progress:convert(paths,model,language,cancel,progress,allowed))
        self.worker=worker;self.permission_timer.start();self.refresh();worker.progress.connect(self.status.setText)
        def done(result,error):
            if self.closed or self.worker is not worker:return
            self.worker=None;self.permission_timer.stop()
            if error or result is None:self.status.setText(t(error or 'Bekor qilindi.'))
            else:self.answer=result;self.output.setPlainText(result);self.status.setText(t('Matn tayyor. Tekshiring va nusxalang.'))
            self.refresh()
        worker.completed.connect(done);worker.start()

    def insert(self):
        if self.answer:
            before=self.win._input.text();self.win._input.setText(before+('\n\n' if before else '')+self.answer)

    def copy(self):
        if self.answer:self.win._clipboard_self_value=self.answer;QApplication.clipboard().setText(self.answer)

    def export(self):
        if not self.answer:return
        path,_=QFileDialog.getSaveFileName(self,t('Eksport'),'transcript.txt','Text (*.txt)')
        if path:
            try:Path(path).write_text(self.answer,encoding='utf-8')
            except OSError:self.status.setText(t('Faylni saqlab bo‘lmadi. Boshqa joy tanlang.'))

    def cancel(self):
        if self.worker:self.worker.cancel();self.status.setText(t('Bekor qilinmoqda…'))

    def done(self,result):self.closed=True;self.permission_timer.stop();self.cancel();super().done(result)


def open_import(win,paths=()):
    dialog=TextImport(win,paths);win._text_import=dialog;dialog.open();return dialog
