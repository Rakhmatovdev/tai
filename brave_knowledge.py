"""Knowledge lives in the existing Center; attaching reuses the normal file chips."""
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QListWidget,QListWidgetItem,QPushButton,QFileDialog,QAbstractItemView,QPlainTextEdit
from brave_i18n import translate as t
from core.knowledge import KnowledgeStore
from core.ollama_chat import Settings
from memory.config_manager import load_api_keys,_patch_config
from brave_local_jobs import Worker


class KnowledgePage(QWidget):
    def __init__(self,center):
        super().__init__(center);self.win=center.win;self.job=None
        layout=QVBoxLayout(self)
        note=QLabel(t('Tanlangan hujjatlar lokal indekslanadi. Embedding modeli bo‘sh bo‘lsa so‘z bo‘yicha qidiriladi.'))
        note.setWordWrap(True);layout.addWidget(note)
        self.model=QLineEdit(load_api_keys().get('local_embedding_model','embeddinggemma'))
        self.model.setPlaceholderText(t('Embedding modeli · masalan embeddinggemma'));layout.addWidget(self.model)
        self.files=QListWidget();self.files.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection);layout.addWidget(self.files,1)
        row=QHBoxLayout();layout.addLayout(row)
        for title,callback in [('Fayllarni indekslash',self.add),('Qayta indekslash',self.reindex),('Indeksdan o‘chirish',self.remove),('Suhbatga biriktirish',self.attach)]:
            button=QPushButton(t(title));button.setStyleSheet(center.button_style);button.clicked.connect(callback);row.addWidget(button)
        self.query=QLineEdit();self.query.setPlaceholderText(t('Kutubxonadan qidirish…'));self.query.returnPressed.connect(self.search);layout.addWidget(self.query)
        self.preview=QPlainTextEdit();self.preview.setReadOnly(True);self.preview.setMaximumHeight(160);layout.addWidget(self.preview)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        cancel=QPushButton(t('Bekor qilish'));cancel.setStyleSheet(center.button_style);cancel.clicked.connect(lambda:self.job.cancel() if self.job else None);layout.addWidget(cancel)
        center.finished.connect(lambda:self.job.cancel() if self.job else None)
        self.refresh()

    def selected(self):return [item.data(Qt.ItemDataRole.UserRole) for item in self.files.selectedItems()]

    def refresh(self):
        self.files.clear();store=KnowledgeStore()
        try:
            for path,model,count,clipped in store.list():
                item=QListWidgetItem(f'{Path(path).name} · {count} · {model or "lexical"}'+(' · limited' if clipped else ''))
                item.setData(Qt.ItemDataRole.UserRole,path);item.setToolTip(path);self.files.addItem(item)
        finally:store.close()

    def run(self,operation):
        if self.job:return
        if not self.win._capabilities.policy['permissions']['files']:
            self.status.setText(t('Fayllarga ruxsat o‘chiq.'));return
        self.job=Worker(self.win,operation)
        self.job.progress.connect(self.status.setText);self.job.completed.connect(self.finished)
        self.status.setText(t('Tayyorlanmoqda…'));self.job.start()

    def finished(self,result,error):
        job,self.job=self.job,None
        if job:job.deleteLater()
        self.status.setText(t(error or ('Bekor qilindi.' if result is None else 'Tayyor.')))
        if isinstance(result,list):self.preview.setPlainText('\n\n'.join(row['label']+'\n'+row['text'] for row in result))
        if result==[]:self.status.setText(t('Hujjatdan savolga mos dalil topilmadi. Savolni aniqlashtiring.'))
        self.refresh()

    def add(self):
        paths,_=QFileDialog.getOpenFileNames(self,t('Fayl tanlang'),'','Documents (*.pdf *.docx *.txt *.md *.csv *.json *.py *.png *.jpg *.jpeg)')
        if paths:self.index(paths)

    def reindex(self):
        if self.selected():self.index(self.selected())

    def index(self,paths):
        try:settings=Settings.read()
        except ValueError as exc:self.status.setText(t(str(exc)));return
        model=self.model.text().strip()
        _patch_config(local_embedding_model=model)
        policy=self.win._capabilities.policy
        def operation(cancel,progress):
            from core.ollama_service import ensure_server
            if model and settings.autostart:ensure_server(settings.url,cancelled=cancel)
            store=KnowledgeStore()
            try:
                if not policy['permissions']['files']:raise ValueError('Fayllarga ruxsat o‘chiq.')
                store.index(paths,settings,model,cancel,progress)
                return True
            finally:store.close()
        self.run(operation)

    def remove(self):
        if self.job:return
        store=KnowledgeStore()
        try:store.remove(self.selected())
        finally:store.close()
        self.refresh()

    def attach(self):
        if not self.win._capabilities.policy['permissions']['files']:return
        for path in self.selected():self.win._drop_zone._set_file(path)
        self.window().accept()

    def search(self):
        question=self.query.text().strip()
        if not question:return
        store=KnowledgeStore()
        try:paths=self.selected() or [row[0] for row in store.list()][:10]
        finally:store.close()
        try:settings=Settings.read()
        except ValueError as exc:self.status.setText(t(str(exc)));return
        def operation(cancel,progress):
            from core.local_jobs import gate
            store=KnowledgeStore()
            try:
                with gate.hold(cancel):return store.retrieve(paths,question,4000,cancel,settings)[0]
            finally:store.close()
        self.run(operation)
