"""Explicit local task queue, independent of chat drafts and transcript history."""
from copy import deepcopy
from pathlib import Path
from PyQt6.QtCore import QObject,QTimer,Qt,pyqtSignal
from PyQt6.QtWidgets import (QApplication,QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,
    QPlainTextEdit,QComboBox,QPushButton,QListWidget,QListWidgetItem,QFileDialog,QSplitter,QWidget,QCheckBox)
from brave_i18n import translate as t
from core import task_queue

LABELS={'pending':'Navbatda','running':'Bajarilmoqda','completed':'Tugallandi','failed':'Xato','cancelled':'Bekor qilindi','interrupted':'Uzuldi'}


class QueueManager(QObject):
    changed=pyqtSignal()
    progress=pyqtSignal(str)
    partial=pyqtSignal(str)

    def __init__(self,win):
        super().__init__(win);self.win=win;self.rows=[];self.loaded=False;self.enabled=False;self.closed=False
        self.active=None;self.worker=None;self.job=None;self.generation=0;self.status='Navbat to‘xtatilgan.'
        self.timer=QTimer(self);self.timer.setInterval(200);self.timer.timeout.connect(self.next)
        QApplication.instance().aboutToQuit.connect(self.shutdown)
        win.destroyed.connect(self.shutdown)
        self.ensure_loaded()

    def ensure_loaded(self):
        if not self.loaded and self.win._capabilities.policy['permissions']['files']:
            self.rows=task_queue.load();self.loaded=True

    def allowed(self):
        return not self.closed and self.win._active_provider=='ollama' and self.win._capabilities.policy['permissions']['files'] and not getattr(self.win,'_meeting_recording',False)

    def commit(self):
        try:task_queue.save(self.rows)
        except (OSError,ValueError) as error:
            self.enabled=False;self.status=str(error);self.changed.emit();return False
        self.changed.emit();return True

    def add(self,row):
        self.add_many([row])

    def add_many(self,rows):
        self.ensure_loaded()
        if not self.loaded or not self.win._capabilities.policy['permissions']['files']:raise ValueError('Fayllarga ruxsat o‘chiq.')
        if len(self.rows)+len(rows)>30:raise ValueError('Navbatda ko‘pi bilan 30 ta vazifa saqlang.')
        previous=self.rows;self.rows=self.rows+rows
        if not self.commit():self.rows=previous;self.changed.emit();raise OSError(self.status)

    def start(self):
        if not self.allowed():self.status='Navbat uchun Ollama va fayl ruxsati kerak. Jonli yozuvni tugating.';self.changed.emit();return
        self.ensure_loaded();self.enabled=True;self.timer.start();self.status='Navbat boshlandi.';self.changed.emit();self.next()

    def pause(self):
        self.enabled=False;self.status='Joriy vazifa tugagach navbat kutadi.' if self.active else 'Navbat to‘xtatilgan.'
        if not self.active:self.timer.stop()
        self.changed.emit()

    def next(self):
        if self.closed:return
        if self.active:
            if not self.allowed():self.enabled=False;self.finish(self.generation,'','Tahlil uchun ruxsat o‘chiq yoki rejim o‘zgardi.')
            return
        if not self.enabled:self.timer.stop();return
        if not self.allowed():self.enabled=False;self.timer.stop();self.status='Navbat uchun Ollama va fayl ruxsati kerak. Jonli yozuvni tugating.';self.changed.emit();return
        runtime=getattr(self.win,'_local_chat',None);voice=getattr(self.win,'_local_voice',None)
        if (runtime and runtime.busy) or (voice and voice.busy):return
        row=next((row for row in self.rows if row['status']=='pending'),None)
        if not row:self.enabled=False;self.timer.stop();self.status='Navbat tugadi.';self.changed.emit();return
        self.active=row;row.update(status='running',result='',error='');self.generation+=1;generation=self.generation
        self.status=row['title']
        if not self.commit():row['status']='pending';self.active=None;self.timer.stop();self.changed.emit();return
        source=deepcopy(row)
        from brave_local_jobs import Worker
        from core.text_import import convert
        from core.offline_voice import model_directory
        from memory.config_manager import load_api_keys
        model=load_api_keys().get('local_stt_path') or str(model_directory())
        allowed=lambda:self.allowed() and self.generation==generation and self.active is row
        def read(cancelled,progress):
            if not allowed():raise ValueError('Fayllarga ruxsat o‘chiq.')
            paths=task_queue.verify_paths(source['files'])
            text=source['text']
            if paths:text+=('\n\n' if text else '')+convert(paths,model,'auto',cancelled,progress,allowed)
            if len(text)>200000:raise ValueError('Matn 200 ming belgidan oshmasin.')
            return text
        worker=Worker(self,read);self.worker=worker;worker.progress.connect(lambda text:self.progress.emit(text) if generation==self.generation else None)
        worker.completed.connect(lambda result,error:self.prepared(generation,result,error));worker.start()

    def prepared(self,generation,result,error):
        if self.closed or generation!=self.generation or not self.active:return
        self.worker=None;row=self.active
        if error or result is None or not self.allowed():self.finish(generation,'',error or 'Bekor qilindi.');return
        if row['kind']=='totext':self.finish(generation,result);return
        from brave_ai_pipeline import AnalysisJob
        job=AnalysisJob([('Source',result)],row['instruction'],self,authorize=lambda:self.allowed() and generation==self.generation,
                        settings=task_queue.settings(row['settings']))
        self.job=job;job.progress.connect(self.progress.emit);job.partial.connect(self.partial.emit)
        job.finished.connect(lambda text,error,cancelled:self.finish(generation,text,error,cancelled));job.start()

    def finish(self,generation,text='',error='',cancelled=False):
        if generation!=self.generation or not self.active:return
        row=self.active;self.active=None;self.generation+=1
        worker,job=self.worker,self.job;self.worker=self.job=None
        if worker:worker.cancel()
        if job:
            if not job.ended:job.cancel()
            job.deleteLater()
        if not self.allowed():
            self.enabled=False
            if not cancelled:error=error or 'Tahlil uchun ruxsat o‘chiq yoki rejim o‘zgardi.'
        row.update(status='cancelled' if cancelled else 'failed' if error or not text.strip() else 'completed',
                   result=text[:200000] if not error and not cancelled else '',error=error[:2000])
        self.status=LABELS[row['status']];self.commit()
        if not self.enabled:self.timer.stop()

    def cancel(self,identity):
        row=next((row for row in self.rows if row['id']==identity),None)
        if not row:return
        if self.active is row:self.finish(self.generation,cancelled=True)
        elif row['status']=='pending':row.update(status='cancelled',error='');self.commit()

    def retry(self,identity):
        row=next((row for row in self.rows if row['id']==identity),None)
        if row and row['status'] in ('failed','cancelled','interrupted'):
            row.update(status='pending',result='',error='');self.commit()

    def remove(self,identity):
        if not any(row['id']==identity for row in self.rows):return
        if self.active and self.active['id']==identity:return
        previous=self.rows;self.rows=[row for row in self.rows if row['id']!=identity]
        if not self.commit():self.rows=previous;self.changed.emit()

    def shutdown(self,*args):
        if self.closed:return
        self.enabled=False;self.timer.stop()
        if self.active:
            row=self.active;generation=self.generation;self.finish(generation,'','Ilova yopilganda vazifa uzilgan. Qayta boshlashni o‘zingiz tanlang.')
            row['status']='interrupted';self.commit()
        self.closed=True


class TaskQueue(QDialog):
    def __init__(self,win,manager):
        super().__init__(win);self.win=win;self.manager=manager;self.paths=[]
        from brave_control_center import style_dialog
        style=style_dialog(self,'AI vazifalar navbati')
        screen=win.screen().availableGeometry();self.resize(min(980,screen.width()-40),min(720,screen.height()-64))
        layout=QVBoxLayout(self)
        note=QLabel(t('Faqat lokal Ollama. Boshlashni bosmaguncha ish bajarilmaydi. Oynani yopish navbatni to‘xtatmaydi.'));note.setWordWrap(True);layout.addWidget(note)
        split=QSplitter();layout.addWidget(split,1);left=QWidget();form=QVBoxLayout(left);split.addWidget(left)
        self.title=QLineEdit();self.title.setMaxLength(80);self.title.setPlaceholderText(t('Vazifa nomi'));form.addWidget(self.title)
        self.kind=QComboBox();self.kind.addItem(t('AI tahlil'),'analysis');self.kind.addItem(t('Fayldan matnga'),'totext');form.addWidget(self.kind)
        self.instruction=QPlainTextEdit();self.instruction.setPlaceholderText(t('Topshiriq: xulosala, tarjima qil, taqqosla…'));self.instruction.setMaximumHeight(95);form.addWidget(self.instruction)
        self.source=QPlainTextEdit();self.source.setPlaceholderText(t('Manba matni yoki quyida fayl tanlang'));form.addWidget(self.source,1)
        self.files=QLabel(t('Fayl tanlang'));self.files.setWordWrap(True);self.files.setTextFormat(Qt.TextFormat.PlainText);form.addWidget(self.files)
        files=QHBoxLayout();form.addLayout(files)
        for title,handler in [('Fayl tanlash',self.choose),('Tozalash',self.clear_files)]:
            button=QPushButton(t(title));button.setStyleSheet(style);button.clicked.connect(handler);files.addWidget(button)
        self.separate=QCheckBox(t('Har bir fayl alohida vazifa'));form.addWidget(self.separate)
        self.model=QLineEdit();self.model.setPlaceholderText(t('Joriy model'));self.model.setMaxLength(200);form.addWidget(self.model)
        self.profile=QComboBox()
        for label,value in [('Joriy profil',''),('Automatic','auto'),('Economy','economy'),('Balanced','balanced'),('Quality','quality')]:self.profile.addItem(t(label),value)
        form.addWidget(self.profile)
        add=QPushButton(t('Navbatga qo‘shish'));add.setStyleSheet(style);add.clicked.connect(self.add);form.addWidget(add)
        right=QWidget();column=QVBoxLayout(right);split.addWidget(right);self.list=QListWidget();column.addWidget(self.list,1)
        self.preview=QPlainTextEdit();self.preview.setReadOnly(True);column.addWidget(self.preview,1)
        split.setSizes([390,540]);self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        bar=QHBoxLayout();layout.addLayout(bar);results=QHBoxLayout();layout.addLayout(results);self.buttons={}
        for key,title,handler in [('start','Boshlash',manager.start),('pause','Pauza',manager.pause),('cancel','Bekor qilish',lambda:manager.cancel(self.selected())),
                ('retry','Qayta navbatga',lambda:manager.retry(self.selected())),('remove','Vazifani o‘chirish',lambda:manager.remove(self.selected())),('insert','Qoralamaga qo‘yish',self.insert),('copy','Nusxalash',self.copy),('export','Natijani eksport qilish',self.export)]:
            button=QPushButton(t(title));button.setStyleSheet(style);button.setAutoDefault(False);button.clicked.connect(handler)
            (results if key in ('insert','copy','export') else bar).addWidget(button);self.buttons[key]=button
        close=QPushButton(t('Yopish'));close.setStyleSheet(style);close.clicked.connect(self.reject);results.addWidget(close)
        self.list.currentItemChanged.connect(self.describe);manager.changed.connect(self.refresh);manager.progress.connect(self.progress);manager.partial.connect(self.partial);self.refresh()

    def selected(self):
        item=self.list.currentItem();return item.data(Qt.ItemDataRole.UserRole) if item else None
    def row(self):return next((row for row in self.manager.rows if row['id']==self.selected()),None)

    def refresh(self):
        selected=self.selected();self.list.blockSignals(True);self.list.clear()
        for row in self.manager.rows:
            item=QListWidgetItem(t(LABELS[row['status']])+' · '+row['title']+'\n'+row['settings']['model']+' · '+row['settings']['profile'])
            item.setData(Qt.ItemDataRole.UserRole,row['id']);self.list.addItem(item)
            if row['id']==selected:self.list.setCurrentItem(item)
        if self.list.currentRow()<0 and self.list.count():self.list.setCurrentRow(0)
        self.list.blockSignals(False);self.describe();self.status.setText(t(self.manager.status))

    def describe(self,*args):
        row=self.row();self.preview.setPlainText((row['result'] or t(row['error']) or row['instruction']+'\n\n'+row['text']) if row else '')
        for key in ('insert','copy','export'):self.buttons[key].setEnabled(bool(row and row['status']=='completed' and row['result'] and self.win._capabilities.policy['permissions']['files']))
        self.buttons['cancel'].setEnabled(bool(row and row['status'] in ('pending','running')))
        self.buttons['retry'].setEnabled(bool(row and row['status'] in ('failed','cancelled','interrupted')))
        self.buttons['remove'].setEnabled(bool(row and row is not self.manager.active))
        self.buttons['start'].setEnabled(not self.manager.enabled);self.buttons['pause'].setEnabled(self.manager.enabled)

    def progress(self,text):self.status.setText(t(text))
    def partial(self,text):
        if self.row() is self.manager.active:self.preview.setPlainText(text)
    def choose(self):
        paths,_=QFileDialog.getOpenFileNames(self,t('Fayl tanlash'),'','All files (*)')
        if paths:self.paths=paths;self.files.setText('\n'.join(Path(path).name for path in paths))
    def clear_files(self):self.paths=[];self.files.setText(t('Fayl tanlang'))

    def add(self):
        if not self.win._capabilities.policy['permissions']['files']:self.status.setText(t('Fayllarga ruxsat o‘chiq.'));return
        try:
            from dataclasses import replace
            from core.ollama_chat import Settings,local_model
            settings=Settings.read()
            settings=replace(settings,model=local_model(self.model.text().strip()) if self.model.text().strip() else settings.model,profile=self.profile.currentData() or settings.profile)
            groups=[[path] for path in self.paths] if self.separate.isChecked() and self.paths else [self.paths]
            rows=[task_queue.create((self.title.text().strip()+' · '+Path(paths[0]).name)[:80] if len(groups)>1 else self.title.text(),
                self.instruction.toPlainText(),self.source.toPlainText(),paths,settings,self.kind.currentData()) for paths in groups]
            self.manager.add_many(rows)
        except (OSError,ValueError) as error:self.status.setText(t(str(error)));return
        self.title.clear();self.source.clear();self.clear_files();self.status.setText(t('Vazifa navbatga qo‘shildi.'))

    def insert(self):
        row=self.row()
        if row and row['status']=='completed' and self.win._capabilities.policy['permissions']['files']:
            from brave_command_library import insert_draft
            insert_draft(self.win,row['result']);self.hide();self.win._input.setFocus()
    def copy(self):
        row=self.row()
        if row and row['status']=='completed' and self.win._capabilities.policy['permissions']['files']:
            self.win._clipboard_self_value=row['result'];QApplication.clipboard().setText(row['result'])

    def export(self):
        row=self.row()
        if not row or row['status']!='completed' or not row['result']:return
        if not self.win._capabilities.policy['permissions']['files']:self.status.setText(t('Fayllarga ruxsat o‘chiq.'));return
        path,kind=QFileDialog.getSaveFileName(self,t('Natijani eksport qilish'),'brave-task.md','Markdown (*.md);;Text (*.txt)')
        if not path:return
        if not self.win._capabilities.policy['permissions']['files']:self.status.setText(t('Fayllarga ruxsat o‘chiq.'));return
        target=Path(path)
        if not target.suffix:target=target.with_suffix('.txt' if kind.startswith('Text') else '.md')
        text=row['result']
        if target.suffix.casefold()!='.txt':
            title=' '.join(row['title'].split());settings=row['settings']
            text=f"# {title}\n\n{settings['model']} · {settings['profile']}\n\n{text}\n"
        try:
            from core.text_export import write
            write(target,text);self.status.setText(t('Saqlandi.'))
        except OSError as error:self.status.setText(str(error))


def open_queue(win):
    manager=getattr(win,'_queue_manager',None)
    if manager is None:manager=QueueManager(win);win._queue_manager=manager
    manager.ensure_loaded();dialog=getattr(win,'_task_queue',None)
    if dialog is None:
        dialog=TaskQueue(win,manager);win._task_queue=dialog;dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.finished.connect(lambda _:setattr(win,'_task_queue',None))
    dialog.refresh();dialog.show();dialog.raise_();dialog.activateWindow();return dialog
