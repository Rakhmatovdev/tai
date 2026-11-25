"""Searchable command reference and explicit, local prompt templates."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLineEdit,QListWidget,
    QListWidgetItem,QLabel,QPushButton,QComboBox,QPlainTextEdit,QMessageBox)
from brave_i18n import translate as t
from core.slash_commands import get,matches,example
from core import command_store

CATEGORIES=(('all','Barchasi'),('ai','AI matn'),('code','Kod'),('tools','Vositalar'),('chat','Suhbat'),('favorites','Saralanganlar'))


def insert_draft(win,text):
    old=win._input.text().strip()
    win._input.setText((old+'\n\n' if old else '')+text)
    win._input.setFocus()


class CommandLibrary(QDialog):
    def __init__(self,win):
        super().__init__(win);self.win=win
        from brave_control_center import style_dialog
        style=style_dialog(self,'Slash buyruqlar');self.resize(720,570)
        layout=QVBoxLayout(self);self.search=QLineEdit();self.search.setPlaceholderText(t('Buyruq yoki tavsifni qidirish…'));layout.addWidget(self.search)
        self.category=QComboBox()
        for key,label in CATEGORIES:self.category.addItem(t(label),key)
        layout.addWidget(self.category);self.list=QListWidget();layout.addWidget(self.list,1)
        self.detail=QLabel();self.detail.setTextFormat(Qt.TextFormat.PlainText);self.detail.setWordWrap(True);layout.addWidget(self.detail)
        note=QLabel(t('@last — shu suhbatdagi oxirgi tugallangan javob. Tanlash faqat qoralamaga qo‘yadi.'));note.setWordWrap(True);layout.addWidget(note)
        bar=QHBoxLayout();layout.addLayout(bar)
        self.star=QPushButton();self.star.clicked.connect(self.favorite);bar.addWidget(self.star)
        self.insert=QPushButton(t('Buyruqni qo‘yish'));self.insert.clicked.connect(self.choose);bar.addWidget(self.insert)
        close=QPushButton(t('Yopish'));close.clicked.connect(self.reject);bar.addWidget(close)
        for button in (self.star,self.insert,close):button.setStyleSheet(style);button.setAutoDefault(False)
        self.search.textChanged.connect(self.refresh);self.category.currentIndexChanged.connect(self.refresh)
        self.list.currentItemChanged.connect(self.describe);self.list.itemDoubleClicked.connect(self.choose)
        self.refresh()

    def current(self):
        item=self.list.currentItem();return get(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def refresh(self):
        old=self.current();prefs=command_store.preferences();self.list.clear()
        for row in matches('/'+self.search.text().lstrip('/'),self.category.currentData(),prefs['favorites'],prefs['recent']):
            item=QListWidgetItem('/'+row.name+' · '+t(row.description))
            if row.name in prefs['favorites']:
                from brave_ui import icon,colors
                item.setIcon(icon('star-filled',colors().PRI,14))
            item.setData(Qt.ItemDataRole.UserRole,row.name);self.list.addItem(item)
            if old and row.name==old.name:self.list.setCurrentItem(item)
        if self.list.currentRow()<0 and self.list.count():self.list.setCurrentRow(0)
        self.describe()

    def describe(self,*args):
        row=self.current();enabled=row is not None
        self.star.setEnabled(enabled);self.insert.setEnabled(enabled)
        from brave_ui import set_icon
        selected=row and row.name in command_store.preferences()['favorites']
        self.star.setText(t('Saralanganlar'));set_icon(self.star,'star-filled' if selected else 'star','PRI' if selected else 'TEXT_MED')
        self.detail.setText('/'+row.name+' · '+t(row.description)+'\n'+example(row) if row else t('Mos buyruq topilmadi.'))

    def favorite(self):
        row=self.current()
        if not row:return
        try:command_store.favorite(row.name)
        except (OSError,ValueError) as error:self.detail.setText(t(str(error)));return
        self.refresh()

    def choose(self,*args):
        row=self.current()
        if row:insert_draft(self.win,'/'+row.name+' ');self.accept()


class PromptSnippets(QDialog):
    def __init__(self,win):
        super().__init__(win);self.win=win;self.identity=None;self.original=('','')
        from brave_control_center import style_dialog
        style=style_dialog(self,'Shaxsiy prompt shablonlari');self.resize(680,590)
        layout=QVBoxLayout(self)
        note=QLabel(t('Shablonlar shu qurilmada saqlanadi. Qo‘yish xabar yubormaydi.'));note.setWordWrap(True);layout.addWidget(note)
        self.list=QListWidget();self.list.setMaximumHeight(150);layout.addWidget(self.list)
        self.title=QLineEdit();self.title.setMaxLength(80);self.title.setPlaceholderText(t('Shablon nomi'));layout.addWidget(self.title)
        self.text=QPlainTextEdit();self.text.setPlaceholderText('/plan …');layout.addWidget(self.text,1)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        bar=QHBoxLayout();layout.addLayout(bar)
        for label,handler in [('Yangi',self.new),('Saqlash',self.save),('O‘chirish',self.delete),('Qoralamaga qo‘yish',self.insert),('Yopish',self.reject)]:
            button=QPushButton(t(label));button.setStyleSheet(style);button.setAutoDefault(False);button.clicked.connect(handler);bar.addWidget(button)
        self.list.currentItemChanged.connect(self.select);self.refresh()

    def allowed(self):
        allowed=self.win._capabilities.policy['permissions']['files']
        if not allowed:self.status.setText(t('Shablonlar uchun fayl ruxsatini yoqing.'))
        return allowed

    def refresh(self):
        self.list.blockSignals(True);self.list.clear()
        if self.allowed():
            for row in command_store.snippets():
                item=QListWidgetItem(row['title']);item.setData(Qt.ItemDataRole.UserRole,row);self.list.addItem(item)
                if row['id']==self.identity:self.list.setCurrentItem(item)
        self.list.blockSignals(False)

    def discard(self):
        if (self.title.text(),self.text.toPlainText())==self.original:return True
        return QMessageBox.question(self,t('Saqlanmagan o‘zgarishlar'),t('Saqlanmagan shablon o‘zgarishlari bekor qilinsinmi?'),QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes

    def select(self,item,previous):
        if not item:return
        if not self.discard():
            self.list.blockSignals(True);self.list.setCurrentItem(previous);self.list.blockSignals(False);return
        if not self.allowed():return
        row=item.data(Qt.ItemDataRole.UserRole);self.identity=row['id'];self.title.setText(row['title']);self.text.setPlainText(row['text']);self.original=(row['title'],row['text'])

    def new(self):
        if not self.discard():return
        self.identity=None;self.title.clear();self.text.clear();self.original=('','')
        self.list.blockSignals(True);self.list.setCurrentItem(None);self.list.clearSelection();self.list.blockSignals(False);self.title.setFocus()

    def save(self):
        if not self.allowed():return
        try:self.identity=command_store.save_snippet(self.identity,self.title.text(),self.text.toPlainText())
        except (OSError,ValueError) as error:self.status.setText(t(str(error)));return
        self.title.setText(self.title.text().strip());self.text.setPlainText(self.text.toPlainText().strip())
        self.original=(self.title.text(),self.text.toPlainText());self.refresh();self.status.setText(t('Saqlandi.'))

    def delete(self):
        if not self.identity or not self.allowed():return
        if QMessageBox.question(self,t('O‘chirish'),t('Tanlangan shablon o‘chirilsinmi?'),QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        try:command_store.delete_snippet(self.identity)
        except OSError as error:self.status.setText(str(error));return
        self.original=(self.title.text(),self.text.toPlainText());self.new();self.refresh()

    def insert(self):
        if not self.allowed():return
        text=self.text.toPlainText().strip()
        if not 1<=len(text)<=10000:self.status.setText(t('Sarlavha 1–80, prompt 1–10000 belgi bo‘lsin.'));return
        insert_draft(self.win,text)
        self.hide();self.win._input.setFocus()

    def reject(self):
        if self.discard():super().reject()


def open_library(win,snippets=False,query=''):
    attr='_prompt_snippets' if snippets else '_slash_help';dialog=getattr(win,attr,None)
    if dialog is None:
        dialog=PromptSnippets(win) if snippets else CommandLibrary(win);setattr(win,attr,dialog)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.finished.connect(lambda _:setattr(win,attr,None))
    if not snippets:dialog.search.setText(query)
    dialog.show();dialog.raise_();dialog.activateWindow()
    return dialog
