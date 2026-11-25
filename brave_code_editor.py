"""Reviewable editable replacement and diff. Only Apply writes the selected file."""
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QPlainTextEdit,QPushButton,QLabel,QTabWidget,QWidget
from brave_i18n import translate as t
from core import code_changes


class CodeEditDialog(QDialog):
    def __init__(self,page,source,new_text):
        super().__init__(page);self.page=page;self.source=source
        from brave_control_center import style_dialog
        style=style_dialog(self,t('Tuzatishni ko‘rib chiqish'));self.resize(850,650)
        layout=QVBoxLayout(self);label=QLabel(source.path);label.setWordWrap(True);layout.addWidget(label)
        note=QLabel(t('Matnni tekshiring. Qo‘llash tugmasi faqat shu faylni o‘zgartiradi va zaxira nusxa yaratadi.'))
        note.setWordWrap(True);layout.addWidget(note)
        self.editor=QPlainTextEdit(new_text);layout.addWidget(self.editor,1)
        self.diff=QPlainTextEdit();self.diff.setReadOnly(True);layout.addWidget(self.diff,1)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        row=QHBoxLayout();layout.addLayout(row)
        self.apply_button=QPushButton(t('Diffni tasdiqlab qo‘llash'));self.apply_button.clicked.connect(self.apply)
        close=QPushButton(t('Yopish'));close.clicked.connect(self.reject)
        for button in (self.apply_button,close):button.setStyleSheet(style);row.addWidget(button)
        self.editor.textChanged.connect(self.refresh);self.refresh()

    def refresh(self):
        text=self.editor.toPlainText();diff=code_changes.preview(self.source,text)
        self.diff.setPlainText(diff);self.apply_button.setEnabled(bool(diff) and bool(text.strip()))

    def apply(self):
        if self.page.closed:return self.reject()
        if not all(self.page.win._capabilities.policy['permissions'][cap] for cap in ('files','code')):
            self.status.setText(t('Kod va fayl ruxsatlarini yoqing.'));return
        try:
            identity=code_changes.apply(self.source,self.editor.toPlainText())
            self.page.last_backup=identity;self.page.last_backups=[];self.page.sections=[];self.page.preview.clear();self.page.invalidate_output()
            self.page.status.setText(t('Tuzatish qo‘llandi. Zaxira nusxadan qaytarish mumkin.'));self.accept()
        except (ValueError,OSError) as error:self.status.setText(t(str(error)))


class MultiCodeEditDialog(QDialog):
    def __init__(self,page,changes):
        super().__init__(page);self.page=page;self.changes=changes;self.editors=[]
        from brave_control_center import style_dialog
        style=style_dialog(self,'Bir nechta fayldagi tuzatish');self.resize(900,700)
        layout=QVBoxLayout(self);self.tabs=QTabWidget();layout.addWidget(self.tabs)
        for source,text in changes:
            tab=QWidget();column=QVBoxLayout(tab)
            label=QLabel(source.path);label.setWordWrap(True);column.addWidget(label)
            editor=QPlainTextEdit(text);column.addWidget(editor,1)
            diff=QPlainTextEdit();diff.setReadOnly(True);column.addWidget(diff,1)
            editor.textChanged.connect(lambda e=editor,d=diff,s=source:d.setPlainText(code_changes.preview(s,e.toPlainText())))
            diff.setPlainText(code_changes.preview(source,text));self.editors.append(editor)
            self.tabs.addTab(tab,__import__('pathlib').Path(source.path).name)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        row=QHBoxLayout();layout.addLayout(row)
        for title,callback in [('Barcha difflarni tasdiqlab qo‘llash',self.apply),('Yopish',self.reject)]:
            button=QPushButton(t(title));button.setStyleSheet(style);button.clicked.connect(callback);row.addWidget(button)

    def apply(self):
        if self.page.closed:return self.reject()
        if not all(self.page.win._capabilities.policy['permissions'][cap] for cap in ('files','code')):
            self.status.setText(t('Kod va fayl ruxsatlarini yoqing.'));return
        try:
            records=code_changes.apply_many([(source,editor.toPlainText()) for (source,_),editor in zip(self.changes,self.editors)])
            self.page.last_backups=records;self.page.last_backup=None
            self.page.sections=[];self.page.preview.clear();self.page.invalidate_output()
            self.page.status.setText(t('Tuzatish qo‘llandi. Zaxira nusxadan qaytarish mumkin.'));self.accept()
        except (ValueError,OSError) as error:self.status.setText(t(str(error)))
