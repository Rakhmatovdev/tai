"""Native editor for custom prompt commands; selecting never sends a request."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QLineEdit,
    QPlainTextEdit,QComboBox,QListWidget,QListWidgetItem,QPushButton,QMessageBox)
from brave_i18n import translate as t
from core import custom_commands


class CustomCommands(QDialog):
    def __init__(self,win):
        super().__init__(win);self.win=win;self.identity='';self.original=None
        from brave_control_center import style_dialog
        style=style_dialog(self,'Shaxsiy slash buyruqlar')
        screen=win.screen().availableGeometry();self.resize(min(740,screen.width()-40),min(650,screen.height()-64))
        layout=QVBoxLayout(self)
        note=QLabel(t('Prompt ichidagi {input} o‘rniga buyruqdan keyingi matn qo‘yiladi. Model/profil faqat shu so‘rovga tegishli.'));note.setWordWrap(True);layout.addWidget(note)
        self.list=QListWidget();self.list.setMaximumHeight(140);layout.addWidget(self.list)
        form=QFormLayout();layout.addLayout(form)
        self.name=QLineEdit();self.name.setPlaceholderText('myplan');self.name.setMaxLength(25)
        self.title=QLineEdit();self.title.setMaxLength(80)
        self.model=QLineEdit();self.model.setMaxLength(200);self.model.setPlaceholderText(t('Joriy model'))
        self.profile=QComboBox()
        for label,key in [('Joriy profil',''),('Automatic','auto'),('Economy','economy'),('Balanced','balanced'),('Quality','quality')]:self.profile.addItem(t(label),key)
        for label,widget in [('Buyruq nomi',self.name),('Sarlavha',self.title),('Ollama modeli',self.model),('Resurs profili',self.profile)]:form.addRow(t(label),widget)
        self.text=QPlainTextEdit();self.text.setPlaceholderText(t('Ushbu vazifa uchun reja tuz: {input}'));layout.addWidget(self.text,1)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        bar=QHBoxLayout();layout.addLayout(bar)
        for label,handler in [('Yangi',self.new),('Saqlash',self.save),('Buyruqni o‘chirish',self.delete),('Buyruqni qo‘yish',self.insert),('Yopish',self.reject)]:
            button=QPushButton(t(label));button.setStyleSheet(style);button.setAutoDefault(False);button.clicked.connect(handler);bar.addWidget(button)
        self.list.currentItemChanged.connect(self.select);self.original=self.values();self.refresh()

    def values(self):return dict(name=self.name.text(),title=self.title.text(),template=self.text.toPlainText(),model=self.model.text(),profile=self.profile.currentData())

    def allowed(self):
        allowed=self.win._capabilities.policy['permissions']['files']
        if not allowed:self.status.setText(t('Fayllarga ruxsat o‘chiq.'))
        return allowed

    def discard(self):
        return self.values()==self.original or QMessageBox.question(self,t('Saqlanmagan o‘zgarishlar'),t('Saqlanmagan shablon o‘zgarishlari bekor qilinsinmi?'),QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes

    def refresh(self):
        self.list.blockSignals(True);self.list.clear()
        if self.allowed():
            for row in custom_commands.rows():
                item=QListWidgetItem('/'+row['name']+' · '+row['title']);item.setData(Qt.ItemDataRole.UserRole,row);self.list.addItem(item)
                if row['name']==self.identity:self.list.setCurrentItem(item)
        self.list.blockSignals(False)
        menu=getattr(self.win,'_slash_menu',None)
        if menu:menu.popup.hide()

    def load(self,row):
        self.identity=row['name'];self.name.setText(row['name']);self.title.setText(row['title']);self.text.setPlainText(row['template']);self.model.setText(row['model']);self.profile.setCurrentIndex(self.profile.findData(row['profile']));self.original=self.values()

    def select(self,item,previous):
        if not item:return
        if not self.discard():
            self.list.blockSignals(True);self.list.setCurrentItem(previous);self.list.blockSignals(False);return
        if self.allowed():self.load(item.data(Qt.ItemDataRole.UserRole))

    def new(self):
        if not self.discard():return
        self.load(dict(name='',title='',template='',model='',profile=''))
        self.list.blockSignals(True);self.list.setCurrentItem(None);self.list.clearSelection();self.list.blockSignals(False);self.name.setFocus()

    def save(self):
        if not self.allowed():return False
        try:self.identity=custom_commands.save(self.identity,**self.values())
        except (ValueError,OSError) as error:self.status.setText(t(str(error)));return False
        self.load(next(row for row in custom_commands.rows() if row['name']==self.identity));self.refresh();self.status.setText(t('Saqlandi.'));return True

    def delete(self):
        if not self.identity or not self.allowed():return
        if QMessageBox.question(self,t('O‘chirish'),t('Tanlangan shablon o‘chirilsinmi?'),QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        try:custom_commands.delete(self.identity)
        except OSError as error:self.status.setText(str(error));return
        self.original=self.values();self.new();self.refresh()

    def insert(self):
        if not self.allowed():return
        if self.values()!=self.original or not self.identity:
            self.status.setText(t('Avval buyruqni saqlang.'));return
        from brave_command_library import insert_draft
        insert_draft(self.win,'/'+self.identity+' ');self.accept();self.win._input.setFocus()

    def reject(self):
        if self.discard():super().reject()


def open_commands(win):
    dialog=getattr(win,'_custom_commands',None)
    if dialog is None:
        dialog=CustomCommands(win);win._custom_commands=dialog;dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.finished.connect(lambda _:setattr(win,'_custom_commands',None))
    dialog.show();dialog.raise_();dialog.activateWindow();return dialog
