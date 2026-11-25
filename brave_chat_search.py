"""Local, paged search across this chat with guarded navigation and highlights."""
from PyQt6.QtCore import Qt,QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLineEdit,QLabel,QListWidget,QListWidgetItem,QPushButton,QTextEdit
from brave_i18n import translate as t


class ChatSearch(QDialog):
    def __init__(self,win):
        super().__init__(win);self.win=win;self.chat_id=win._features.chat_id;self.offset=0;self.has_more=False
        from brave_control_center import style_dialog
        style=style_dialog(self,'Suhbat ichida qidirish')
        screen=win.screen().availableGeometry();self.resize(min(700,screen.width()-40),min(500,screen.height()-64))
        layout=QVBoxLayout(self);self.query=QLineEdit();self.query.setMaxLength(200);self.query.setPlaceholderText(t('So‘z, ibora yoki kodni qidiring…'));layout.addWidget(self.query)
        self.list=QListWidget();self.list.setWordWrap(True);layout.addWidget(self.list,1)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        bar=QHBoxLayout();layout.addLayout(bar);self.previous=QPushButton(t('Oldingi sahifa'));self.next=QPushButton(t('Keyingi sahifa'));self.jump=QPushButton(t('Xabarga o‘tish'));close=QPushButton(t('Yopish'))
        for button in (self.previous,self.next,self.jump,close):button.setStyleSheet(style);button.setAutoDefault(False);bar.addWidget(button)
        self.previous.clicked.connect(lambda:self.page(-50));self.next.clicked.connect(lambda:self.page(50));self.jump.clicked.connect(self.go);close.clicked.connect(self.reject)
        self.list.itemDoubleClicked.connect(self.go);self.list.currentItemChanged.connect(lambda:self.jump.setEnabled(self.list.currentItem() is not None))
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(180);self.timer.timeout.connect(self.refresh)
        self.query.textChanged.connect(self.changed);self.query.returnPressed.connect(self.flush)
        self.refresh()

    def changed(self):self.offset=0;self.timer.start()
    def flush(self):self.timer.stop();self.refresh()
    def page(self,delta):self.offset=max(0,self.offset+delta);self.refresh()

    def refresh(self):
        if self.chat_id!=self.win._features.chat_id:self.chat_id=self.win._features.chat_id;self.offset=0
        rows=self.win._features.store.search_messages(self.chat_id,self.query.text(),self.offset,51)
        self.has_more=len(rows)>50;self.list.clear()
        for seq,role,excerpt,stamp in rows[:50]:
            item=QListWidgetItem((t('Siz') if role=='user' else self.win._assistant_name)+' · '+stamp+'\n'+excerpt)
            item.setData(Qt.ItemDataRole.UserRole,seq);self.list.addItem(item)
        if self.list.count():self.list.setCurrentRow(0)
        self.previous.setEnabled(self.offset>0);self.next.setEnabled(self.has_more)
        self.jump.setEnabled(bool(rows));self.status.setText(f'{self.offset+1}–{self.offset+min(50,len(rows))}' if rows else t('Mos xabar topilmadi.'))

    def go(self,*args):
        if self.timer.isActive():self.flush()
        item=self.list.currentItem()
        if not item:return
        from brave_navigation import action_enabled
        if not action_enabled(self.win,'new-chat'):
            self.status.setText(t('Avval joriy javob tugashini kuting.'));return
        features=self.win._features
        if self.chat_id!=features.chat_id:self.refresh();return
        index=features.store.message_index(self.chat_id,item.data(Qt.ItemDataRole.UserRole))
        if index is None:self.refresh();return
        offset=(index//60)*60;features.show_page(offset)
        log=self.win._log;row_index=index-features.page_offset;query=self.query.text().strip();chat_id=self.chat_id
        page_offset=features.page_offset
        from brave_chat import MessageCard
        from brave_ui import colors
        if row_index<len(log._rows):
            card=log._rows[row_index].findChild(MessageCard)
            if card:
                selections=[];cursor=card.body.document().find(query)
                while not cursor.isNull() and len(selections)<100:
                    selected=QTextEdit.ExtraSelection();selected.cursor=cursor;selected.format.setBackground(QColor(colors().PRI_GHO));selections.append(selected)
                    cursor=card.body.document().find(query,cursor)
                card.body.setExtraSelections(selections)
        self.hide()
        def reveal():
            from PyQt6 import sip
            if sip.isdeleted(log) or features.chat_id!=chat_id or features.page_offset!=page_offset or row_index>=len(log._rows):return
            row=log._rows[row_index]
            log.scroll.ensureWidgetVisible(row,0,20)
        QTimer.singleShot(60,reveal)


def open_search(win,query=''):
    dialog=getattr(win,'_chat_search',None)
    if dialog is None:
        dialog=ChatSearch(win);win._chat_search=dialog;dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.finished.connect(lambda _:setattr(win,'_chat_search',None))
    if query:dialog.query.setText(query)
    dialog.flush();dialog.show();dialog.raise_();dialog.activateWindow();dialog.query.setFocus();return dialog
