"""Local-only preview of the content prepared for an explicit chat send."""
import base64,threading
from pathlib import Path
from PyQt6.QtCore import Qt,pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QLabel,QPlainTextEdit,QPushButton,QInputDialog
from brave_i18n import translate as t

class AttachmentPreview(QDialog):
    ready=pyqtSignal(object)
    def __init__(self,win,path):
        super().__init__(win)
        from brave_control_center import style_dialog
        style=style_dialog(self,'Faylni ko‘rish');self.resize(720,600)
        layout=QVBoxLayout(self);self.title=QLabel(Path(path).name);self.title.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(self.title)
        note=QLabel(t('Bu ko‘rinish lokal. Tanlangan parchalar savol yuborilganda lokal modelga beriladi.' if win._active_provider=='ollama' else 'Bu ko‘rinish lokal. Kontent faqat savol yuborilganda Gemini’ga jo‘natiladi.'));note.setWordWrap(True);layout.addWidget(note)
        self.image=QLabel();self.image.setAlignment(Qt.AlignmentFlag.AlignCenter);self.image.hide();layout.addWidget(self.image,1)
        self.text=QPlainTextEdit();self.text.setReadOnly(True);self.text.setPlainText(t('Fayl o‘qilmoqda…'));layout.addWidget(self.text,1)
        close=QPushButton(t('Yopish'));close.setStyleSheet(style);close.clicked.connect(self.accept);layout.addWidget(close)
        self.ready.connect(self.present)
        turbo=win._capabilities.policy['turbo'];allowed=win._capabilities.policy['permissions']['files']
        def work():
            try:
                if not allowed:raise PermissionError(t('Fayl ruxsati o‘chiq.'))
                from core.attachments import parts
                result=parts(path,turbo)
            except Exception as error:result=[{'text':str(error)}]
            try:self.ready.emit(result)
            except RuntimeError:pass
        threading.Thread(target=work,daemon=True,name='brave-local-preview').start()

    def present(self,parts):
        self.text.setPlainText('\n'.join(part['text'].partition('\n')[2] if part['text'].startswith('Attachment ') else part['text'] for part in parts if 'text' in part))
        for part in parts:
            if 'inline_data' in part:
                pixmap=QPixmap();pixmap.loadFromData(base64.b64decode(part['inline_data']['data']))
                self.image.setPixmap(pixmap.scaled(650,410,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
                self.image.show();self.text.hide()

def open_preview(win):
    paths=win._drop_zone.current_files();path=paths[0] if paths else None
    if len(paths)>1:
        chosen,ok=QInputDialog.getItem(win,t('Faylni ko‘rish'),t('Fayl tanlang'),paths,0,False)
        if not ok:return
        path=chosen
    if path:AttachmentPreview(win,path).exec()
