"""Paged message navigation, independent branches and user-confirmed source-backed notes."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QListWidget,QListWidgetItem,QPushButton,QPlainTextEdit,QComboBox,QInputDialog,QTabWidget,QWidget
from brave_control_center import style_dialog
from brave_i18n import translate as t


class Inspector(QDialog):
    def __init__(self,win):
        super().__init__(win);self.win=win;self.store=win._features.store;self.chat_id=win._features.chat_id;self.offset=0
        self.style=style_dialog(self,'Suhbat versiyalari va faktlar');self.resize(950,700)
        layout=QVBoxLayout(self)
        self.query=QLineEdit();self.query.setPlaceholderText(t('Shu suhbatdan qidirish…'));self.query.returnPressed.connect(self.search);layout.addWidget(self.query)
        self.messages=QListWidget();self.messages.currentItemChanged.connect(self.preview_message);layout.addWidget(self.messages,1)
        row=QHBoxLayout();layout.addLayout(row)
        for title,callback in [('Oldingi sahifa',lambda:self.move(-60)),('Keyingi sahifa',lambda:self.move(60)),('Shu xabardan tahrirlash',self.edit),('Shu xabardan qayta javob',self.regenerate)]:self.button(title,callback,row)
        self.preview=QPlainTextEdit();self.preview.setReadOnly(True);self.preview.setMaximumHeight(140);layout.addWidget(self.preview)
        tabs=QTabWidget();layout.addWidget(tabs,1)
        notes=QWidget();notes_layout=QVBoxLayout(notes);tabs.addTab(notes,t('Tasdiqlangan faktlar'))
        self.notes=QListWidget();notes_layout.addWidget(self.notes)
        actions=QHBoxLayout();notes_layout.addLayout(actions)
        self.kind=QComboBox()
        for title,key in [('Fakt','fact'),('Qaror','decision'),('Talab','requirement'),('Ochiq savol','question')]:self.kind.addItem(t(title),key)
        actions.addWidget(self.kind);self.button('Tanlangan xabardan saqlash',self.add_fact,actions);self.button('O‘chirish',self.delete_fact,actions)
        compare=QWidget();compare_layout=QVBoxLayout(compare);tabs.addTab(compare,t('Javoblarni solishtirish'))
        selections=QHBoxLayout();compare_layout.addLayout(selections)
        self.left=QComboBox();self.right=QComboBox();selections.addWidget(self.left);selections.addWidget(self.right)
        views=QHBoxLayout();compare_layout.addLayout(views)
        self.left_text=QPlainTextEdit();self.right_text=QPlainTextEdit()
        for view in (self.left_text,self.right_text):view.setReadOnly(True);views.addWidget(view)
        for key,title,index,model in self.store.branches(self.chat_id):
            label=f'{title[:35]} · #{(index or 0)+1} · {model}'
            self.left.addItem(label,key);self.right.addItem(label,key)
        self.right.setCurrentIndex(max(0,self.right.count()-1))
        self.left.currentIndexChanged.connect(self.compare);self.right.currentIndexChanged.connect(self.compare)
        self.refresh();self.refresh_facts();self.compare()

    def button(self,title,callback,row):
        button=QPushButton(t(title));button.setStyleSheet(self.style);button.clicked.connect(callback);row.addWidget(button)

    def refresh(self):
        self.messages.clear()
        for index,(role,body,stamp) in enumerate(self.store.page(self.chat_id,self.offset,60),self.offset):
            item=QListWidgetItem(f'#{index+1} · {role} · {body[:100].replace(chr(10)," ")}')
            item.setData(Qt.ItemDataRole.UserRole,(index,role,body));self.messages.addItem(item)
        if self.messages.count():self.messages.setCurrentRow(0)

    def move(self,amount):
        self.offset=min(max(0,self.offset+amount),max(0,self.store.count(self.chat_id)-1)//60*60);self.refresh()

    def selected(self):
        item=self.messages.currentItem();return item.data(Qt.ItemDataRole.UserRole) if item else None

    def preview_message(self,*args):
        row=self.selected();self.preview.setPlainText(row[2] if row else '')

    def search(self):
        query=self.query.text().strip().casefold()
        if not query:return
        row=self.store.db.execute('''SELECT position FROM
            (SELECT body,ROW_NUMBER() OVER (ORDER BY seq)-1 AS position FROM messages WHERE chat_id=?)
            WHERE instr(brave_casefold(body),?)>0 LIMIT 1''',(self.chat_id,query)).fetchone()
        if row:self.offset=row[0]//60*60;self.refresh();self.messages.setCurrentRow(row[0]%60)

    def branch(self,edit):
        row=self.selected()
        if row and row[1]=='user':
            from brave_conversation import branch_last
            if branch_last(self.win,edit,row[0]):self.accept()

    def edit(self):self.branch(True)
    def regenerate(self):self.branch(False)

    def refresh_facts(self):
        self.notes.clear()
        for key,kind,body,index in self.store.facts(self.chat_id):
            item=QListWidgetItem(f'{t({"fact":"Fakt","decision":"Qaror","requirement":"Talab","question":"Ochiq savol"}[kind])} · #{index+1}: {body}')
            item.setData(Qt.ItemDataRole.UserRole,key);self.notes.addItem(item)

    def add_fact(self):
        row=self.selected()
        if not row:return
        text,ok=QInputDialog.getMultiLineText(self,t('Tasdiqlangan fakt'),t('Qisqa, aniq yozuv · 1000 belgigacha'),row[2][:1000])
        if ok and text.strip() and len(text)<=1000:
            self.store.add_fact(self.chat_id,self.kind.currentData(),text,row[0]);self.refresh_facts()

    def delete_fact(self):
        item=self.notes.currentItem()
        if item:self.store.remove_fact(item.data(Qt.ItemDataRole.UserRole));self.refresh_facts()

    def compare(self):
        for choice,view in ((self.left,self.left_text),(self.right,self.right_text)):
            key=choice.currentData();offset=max(0,self.store.count(key)-30) if key else 0
            view.setPlainText('\n\n'.join(role+': '+body for role,body,_ in self.store.page(key,offset,30)))


def open_inspector(win):
    from brave_conversation import idle
    if idle(win):Inspector(win).exec()
