"""Conversation history, response mode and a native task status panel."""
import os
import time
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QComboBox,QDialog,QFrame,QHBoxLayout,QInputDialog,
    QLabel,QLineEdit,QListWidget,QListWidgetItem,QMessageBox,
    QPushButton,QSizePolicy,QVBoxLayout,QMenu,QApplication,QCheckBox)
from PyQt6.QtGui import QShortcut,QKeySequence
from brave_i18n import translate as t
from brave_history import HistoryStore


class HistoryDialog(QDialog):
    def __init__(self, controller):
        super().__init__(controller.win)
        from brave_ui import colors,font,button_style
        from brave_chat import MessageText
        self.controller=controller
        c=colors()
        self.setWindowTitle(t('Suhbatlar tarixi'))
        self.setFont(font(10))
        screen=controller.win.screen().availableGeometry();self.resize(min(900,screen.width()-40),min(720,screen.height()-64))
        from brave_control_center import style_dialog
        style_dialog(self,'Suhbatlar tarixi')
        layout=QVBoxLayout(self)
        self.search=QLineEdit()
        self.search.setPlaceholderText(t('Suhbatlarni qidirish…'))
        layout.addWidget(self.search)
        filters=QHBoxLayout();layout.addLayout(filters)
        self.folder_filter=QComboBox();self.tag_filter=QComboBox();self.pinned_filter=QCheckBox(t('Mahkamlanganlar'))
        for combo in (self.folder_filter,self.tag_filter):combo.setMinimumContentsLength(8);combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);combo.setProperty('brave_literal_text',True)
        filters.addWidget(self.folder_filter,1);filters.addWidget(self.tag_filter,1);filters.addWidget(self.pinned_filter)
        self.chat_offset=0;self.edited_chat=None;self.organization_drafts={}
        columns=QHBoxLayout()
        self.list=QListWidget()
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setFixedWidth(230)
        self.list.setFont(font(10))
        columns.addWidget(self.list)
        # This safe Markdown viewer blocks remote/local image resources.
        class HistoryText(MessageText):
            def fit_height(self):
                pass
        self.preview=HistoryText('')
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        self.preview.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.preview.setMinimumHeight(180)
        self.preview.setMaximumHeight(16777215)
        self.preview.setStyleSheet(f'QTextBrowser {{background:{c.BG};color:{c.TEXT};border:1px solid {c.BORDER};border-radius:8px;padding:14px;}}')
        columns.addWidget(self.preview,1)
        layout.addLayout(columns,1)
        paging=QHBoxLayout();layout.addLayout(paging)
        self.preview_offset=0;self.preview_chat=None
        for title,amount in [('Oldingi sahifa',-60),('Keyingi sahifa',60)]:
            button=QPushButton(t(title));button.setStyleSheet(button_style());button.clicked.connect(lambda checked=False,n=amount:self.preview_page(n));paging.addWidget(button)
        self.preview_count=QLabel();paging.addWidget(self.preview_count)
        note=QLabel(t('Tarix shu qurilmada saqlanadi. Faqat davom ettirilgan suhbat Gemini’ga yuboriladi.'))
        note.setWordWrap(True)
        note.setStyleSheet(f'color:{c.TEXT_DIM};')
        layout.addWidget(note)
        actions=QHBoxLayout()
        for title,handler in [('Nomlash',self.rename),('Suhbatni o‘chirish',self.delete),('Suhbatni davom ettirish',self.resume)]:
            button=QPushButton(t(title));button.setStyleSheet(button_style());button.clicked.connect(handler)
            actions.addWidget(button)
        layout.addLayout(actions)
        organize=QHBoxLayout();layout.addLayout(organize)
        self.folder_edit=QComboBox();self.tags_edit=QLineEdit();self.tags_edit.setMaxLength(270);self.tags_edit.setPlaceholderText(t('Teglar, vergul bilan'))
        self.folder_edit.setMinimumContentsLength(8);self.folder_edit.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.folder_edit.setProperty('brave_literal_text',True)
        self.pin_edit=QCheckBox(t('Mahkamlash'));self.organize_save=QPushButton(t('Joylashuvni saqlash'));self.organize_save.setStyleSheet(button_style())
        for widget in (self.folder_edit,self.tags_edit,self.pin_edit,self.organize_save):organize.addWidget(widget)
        self.organize_save.clicked.connect(self.save_organization)
        folders=QHBoxLayout();layout.addLayout(folders)
        for label,handler in [('Yangi papka',self.new_folder),('Papkani nomlash',self.rename_folder),('Papkani o‘chirish',self.delete_folder)]:
            button=QPushButton(t(label));button.setStyleSheet(button_style());button.clicked.connect(handler);folders.addWidget(button)
        chat_paging=QHBoxLayout();layout.addLayout(chat_paging)
        self.chat_previous=QPushButton(t('Oldingi suhbatlar'));self.chat_next=QPushButton(t('Keyingi suhbatlar'))
        for button,delta in ((self.chat_previous,-100),(self.chat_next,100)):
            button.setStyleSheet(button_style());button.clicked.connect(lambda checked=False,d=delta:self.chat_page(d));chat_paging.addWidget(button)
        self.status=QLabel();self.status.setWordWrap(True);self.status.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(self.status)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(180)
        self.timer.timeout.connect(self.refresh)
        self.search.textChanged.connect(self.filter_changed)
        self.folder_filter.currentIndexChanged.connect(self.filter_changed);self.tag_filter.currentIndexChanged.connect(self.filter_changed);self.pinned_filter.toggled.connect(self.filter_changed)
        self.list.currentItemChanged.connect(self.show_chat)
        self.refresh()

    def selected(self):
        item=self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def refresh(self):
        self.remember_organization()
        self.reload_filters()
        selected=self.selected()
        self.edited_chat=None
        self.list.clear()
        rows=self.controller.store.search(self.search.text().strip(),self.folder_filter.currentData(),self.pinned_filter.isChecked(),self.tag_filter.currentData() or '',self.chat_offset,100)
        for chat_id,title,updated in rows:
            info=self.controller.store.chat_info(chat_id)
            item=QListWidgetItem(('* ' if info['pinned'] else '')+title+'\n'+updated[:10]+(' · '+', '.join(info['tags']) if info['tags'] else ''))
            item.setData(Qt.ItemDataRole.UserRole,chat_id)
            self.list.addItem(item)
            if chat_id==selected:self.list.setCurrentItem(item)
        if not self.list.currentItem() and self.list.count():self.list.setCurrentRow(0)
        if not self.list.count():
            self.preview.setPlainText(t('Suhbat topilmadi.'))
            self.preview_count.clear()
        for widget in (self.folder_edit,self.tags_edit,self.pin_edit,self.organize_save):widget.setEnabled(bool(self.list.count()))
        self.chat_previous.setEnabled(self.chat_offset>0);self.chat_next.setEnabled(len(rows)==100)
        self.show_unsaved()

    def remember_organization(self):
        if not self.edited_chat:return
        value=dict(folder_id=self.folder_edit.currentData(),pinned=self.pin_edit.isChecked(),
                   tags=[tag.strip() for tag in self.tags_edit.text().split(',') if tag.strip()])
        if value!=self.controller.store.chat_info(self.edited_chat):self.organization_drafts[self.edited_chat]=value
        else:self.organization_drafts.pop(self.edited_chat,None)

    def show_unsaved(self):
        if self.organization_drafts:self.status.setText(t('Saqlanmagan joylashuv o‘zgarishlari')+f': {len(self.organization_drafts)}')

    def filter_changed(self,*args):self.chat_offset=0;self.timer.start()
    def chat_page(self,delta):self.chat_offset=max(0,self.chat_offset+delta);self.timer.stop();self.refresh()

    def reload_filters(self):
        store=self.controller.store
        for combo,rows in ((self.folder_filter,[(t('Barcha papkalar'),None),(t('Papkalanmagan'),'')]+[(name,identity) for identity,name in store.folders()]),
                           (self.tag_filter,[(t('Barcha teglar'),'')]+[(tag,tag) for tag in store.tags()])):
            old=combo.currentData();combo.blockSignals(True);combo.clear()
            for title,data in rows:combo.addItem(title,data)
            index=combo.findData(old);combo.setCurrentIndex(max(0,index));combo.blockSignals(False)

    def save_organization(self):
        chat_id=self.selected()
        if not chat_id:return
        try:self.controller.store.organize(chat_id,self.folder_edit.currentData(),self.pin_edit.isChecked(),[tag.strip() for tag in self.tags_edit.text().split(',') if tag.strip()])
        except (ValueError,OSError) as error:self.status.setText(t(str(error)));return
        self.organization_drafts.pop(chat_id,None);self.edited_chat=None
        self.refresh();self.status.setText(t('Saqlandi.'))
        self.show_unsaved()

    def new_folder(self):
        name,ok=QInputDialog.getText(self,t('Yangi papka'),t('Papka nomi'))
        if not ok:return
        try:self.controller.store.save_folder(name)
        except ValueError as error:self.status.setText(t(str(error)));return
        self.refresh()

    def folder_target(self):return self.folder_filter.currentData() or self.folder_edit.currentData()

    def rename_folder(self):
        identity=self.folder_target();rows=dict(self.controller.store.folders())
        if identity not in rows:self.status.setText(t('Avval papkani tanlang.'));return
        name,ok=QInputDialog.getText(self,t('Papkani nomlash'),t('Papka nomi'),text=rows[identity])
        if not ok:return
        try:self.controller.store.save_folder(name,identity)
        except ValueError as error:self.status.setText(t(str(error)));return
        self.refresh()

    def delete_folder(self):
        identity=self.folder_target()
        if not identity:self.status.setText(t('Avval papkani tanlang.'));return
        if QMessageBox.question(self,t('Papkani o‘chirish'),t('Papka o‘chirilsinmi? Suhbatlar papkalanmagan bo‘limga o‘tadi.'),QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        self.remember_organization();self.edited_chat=None
        self.controller.store.delete_folder(identity)
        for draft in self.organization_drafts.values():
            if draft['folder_id']==identity:draft['folder_id']=None
        self.refresh()

    def show_chat(self,*args):
        chat_id=self.selected()
        if not chat_id:return
        if chat_id!=self.edited_chat:
            self.remember_organization()
            self.edited_chat=chat_id;info=self.organization_drafts.get(chat_id,self.controller.store.chat_info(chat_id))
            self.folder_edit.clear();self.folder_edit.addItem(t('Papkalanmagan'),None)
            for identity,name in self.controller.store.folders():self.folder_edit.addItem(name,identity)
            self.folder_edit.setCurrentIndex(max(0,self.folder_edit.findData(info['folder_id'])))
            self.tags_edit.setText(', '.join(info['tags']));self.pin_edit.setChecked(info['pinned'])
            self.show_unsaved()
        if chat_id!=self.preview_chat:
            self.preview_chat=chat_id;self.preview_offset=max(0,self.controller.store.count(chat_id)-60)
        from PyQt6.QtGui import QTextDocument
        parts=[]
        for role,body,stamp in self.controller.store.page(chat_id,self.preview_offset,60):
            parts.extend(['### '+(t('Siz') if role=='user' else 'Brave')+' · '+stamp,body,''])
        self.preview.document().setMarkdown('\n\n'.join(parts),QTextDocument.MarkdownFeature.MarkdownNoHTML)
        count=self.controller.store.count(chat_id)
        self.preview_count.setText(f'{min(self.preview_offset+1,count)}–{min(self.preview_offset+60,count)} / {count}')

    def preview_page(self,amount):
        count=self.controller.store.count(self.selected())
        self.preview_offset=max(0,min(self.preview_offset+amount,max(0,count-60)));self.show_chat()

    def rename(self):
        chat_id=self.selected()
        if not chat_id:return
        title,ok=QInputDialog.getText(self,t('Nomlash'),t('Suhbat nomi'),text=self.controller.store.title(chat_id))
        if ok:self.controller.store.rename(chat_id,title);self.refresh()

    def delete(self):
        chat_id=self.selected()
        if not chat_id:return
        result=QMessageBox.question(self,t('Suhbatni o‘chirish'),t('Bu suhbat tarixdan o‘chirilsinmi?'),QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
        if result==QMessageBox.StandardButton.Yes:
            win=self.controller.win
            if chat_id==self.controller.chat_id:
                from brave_navigation import action_enabled
                if not action_enabled(win,'new-chat'):self.status.setText(t('Avval joriy javob tugashini kuting.'));return
                draft=win._input.text()
                if not self.controller.switch_chat():return
                win._input.setText(draft)
            self.controller.store.delete(chat_id)
            self.organization_drafts.pop(chat_id,None);self.edited_chat=None
            runtime=getattr(self.controller.win,'_local_chat',None)
            if runtime:runtime.visual_context.clear(chat_id)
            self.refresh()

    def resume(self):
        chat_id=self.selected()
        if chat_id and self.confirm_discard() and self.controller.switch_chat(chat_id):
            self.organization_drafts.clear();self.edited_chat=None;self.accept()

    def confirm_discard(self):
        self.remember_organization()
        return not self.organization_drafts or QMessageBox.question(self,t('Saqlanmagan o‘zgarishlar'),
            t('Papka, teg va mahkamlash o‘zgarishlari saqlanmagan. Ular bekor qilinsinmi?'),
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes

    def done(self,result):
        if self.confirm_discard():
            self.organization_drafts.clear();self.edited_chat=None;super().done(result)


class Features:
    def __init__(self, win):
        self.win=win
        self.store=HistoryStore()
        self.chat_id=HistoryStore.new_id()
        if hasattr(win, '_language_tutor'):
            win._language_tutor.on_new_chat_started(self.chat_id)
        self.started=None
        self.cancel_pending=False
        self.stage='idle'
        self.persist=False
        self.tasks=[];self.current_task=None
        self.drafts={}
        self.page_offset=0
        win._log.older_page.clicked.connect(lambda:self.show_page(self.page_offset-60))
        win._log.newer_page.clicked.connect(lambda:self.show_page(self.page_offset+60))
        self.draft_timer=QTimer(win);self.draft_timer.setSingleShot(True);self.draft_timer.setInterval(500)
        self.draft_timer.timeout.connect(self.save_draft)
        QApplication.instance().aboutToQuit.connect(self.save_draft)
        win._log.messageAdded.connect(self.save_message)
        self.timer=QTimer(win);self.timer.setInterval(1000);self.timer.timeout.connect(self.tick)
        self.timer.start()

    def enable_persistence(self):
        if self.persist:return
        if not getattr(self,'_draft_bound',False):
            self.win._input.textChanged.connect(self.draft_changed);self._draft_bound=True
        directory=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local'/'share')))/'Brave'
        try:
            store=HistoryStore(directory/'chat-history.sqlite3')
        except Exception:
            self.win._log.append_log('ERR: Suhbatlar tarixini diskka saqlab bo‘lmadi.')
            return
        self.store.close();self.store=store;self.persist=True
        from core import workspace_store
        def mark_interrupted(rows):
            for row in rows:
                if row.get('status')=='Bajarilmoqda':row['status']='Uzuldi'
            return rows
        workspace_store.update('tasks.json',mark_interrupted)
        draft=workspace_store.read('chat-draft.json',{})
        if isinstance(draft,dict) and isinstance(draft.get('text'),str) and not self.win._input.text():
            self.win._input.setText(draft['text'])
            if draft['text']:self.win._log.append_log('SYS: Saqlangan qoralama tiklandi.')

    def draft_changed(self):
        if self.persist:self.draft_timer.start()

    def save_draft(self):
        if self.persist:
            from core import workspace_store
            try:workspace_store.write('chat-draft.json',{'text':self.win._input.text()})
            except OSError:self.win._log.append_log('ERR: Qoralamani saqlab bo‘lmadi.')

    def save_message(self,text,stamp):
        prefix,separator,body=text.partition(':')
        kind=prefix.strip().casefold()
        if separator and kind=='you':
            import uuid
            self.current_task={'id':uuid.uuid4().hex,'request':body.strip(),'status':'Bajarilmoqda','steps':[],'result':'','at':stamp}
            self._task_started=time.monotonic()
            self.tasks.append(self.current_task);self.tasks=self.tasks[-100:];self.save_task()
        elif self.current_task and (kind in {'brave',self.win._assistant_name.casefold()} or (kind in {'err','error'} and self.current_task['status'] in {'Bajarilmoqda','Uzuldi'})):
            self.current_task['result']=body.strip()
            if self.current_task['status']!='Bekor qilindi':self.current_task['status']='Xato' if kind in {'err','error'} else 'Javob tayyor'
            self.current_task['duration']=round(time.monotonic()-getattr(self,'_task_started',time.monotonic()),1)
            self.save_task()
        if separator and kind in {'you','brave',self.win._assistant_name.casefold()}:
            try:
                self.store.append(self.chat_id,'user' if kind=='you' else 'assistant',body.strip(),stamp)
                runtime=getattr(self.win,'_local_chat',None)
                if kind!='you' and runtime and self.win._active_provider=='ollama' and runtime.last_request and runtime.last_request.get('status')=='completed' and runtime.history and runtime.history[-1]['content'].strip()==body.strip():
                    self.store.record_reply(self.chat_id,runtime.last_request)
                if kind=='you':
                    self.store.set_files(self.chat_id,self.store.count(self.chat_id)-1,[] if getattr(self.win,'_continuation_submission',False) else self.win._drop_zone.current_files())
                count=self.store.count(self.chat_id)
                if self.page_offset+60<count-1 or len(self.win._log._rows)>119:
                    self.page_offset=max(0,count-60)
                    rows=self.store.page(self.chat_id,self.page_offset,60)
                    self.win._log._history=[(('You' if role=='user' else self.win._assistant_name)+': '+value,at) for role,value,at in rows]
                    self.win._log.retheme()
            except Exception:
                if self.persist:
                    self.persist=False
                    self.win._log.append_log('ERR: Suhbatlar tarixini diskka saqlab bo‘lmadi.')
            self.update_page_controls()
            from brave_continuation import refresh
            refresh(self.win)

    def save_task(self):
        if self.persist and self.current_task:
            from core import workspace_store
            from copy import deepcopy
            row=deepcopy(self.current_task)
            workspace_store.update('tasks.json',lambda rows:([old for old in rows if old['id']!=row['id']]+[row])[-100:])

    def switch_chat(self,chat_id=None):
        if self.started is not None or (self.win.can_change_chat and not self.win.can_change_chat()):
            self.win._log.append_log('ERR: Avval joriy javob yoki vazifa tugashini kuting.')
            return False
        messages=self.store.messages(chat_id) if chat_id else []
        callback=self.win.on_chat_change
        if callback:
            callback(messages)
        self.drafts[self.chat_id]=self.win._input.text()
        new_created = chat_id is None
        self.chat_id=chat_id or HistoryStore.new_id()
        if new_created and hasattr(self.win, '_language_tutor'):
            self.win._language_tutor.on_new_chat_started(self.chat_id)
        self.win._log.clear()
        self.show_page(max(0,self.store.count(self.chat_id)-60))
        self.win._input.setText(self.drafts.get(self.chat_id,''))
        self.win._apply_state('CONNECTING')
        return True

    def show_page(self,offset):
        if self.started is not None:return
        count=self.store.count(self.chat_id)
        self.page_offset=max(0,min(offset,max(0,count-60)))
        rows=self.store.page(self.chat_id,self.page_offset,60)
        self.win._log._history=[(('You' if role=='user' else self.win._assistant_name)+': '+body,stamp) for role,body,stamp in rows]
        self.win._log.retheme();self.update_page_controls()

    def update_page_controls(self):
        count=self.store.count(self.chat_id);log=self.win._log
        log.page_bar.setVisible(count>60)
        log.older_page.setEnabled(self.started is None and self.page_offset>0)
        visible=sum(text.partition(':')[0].strip().casefold() in ('you','brave',self.win._assistant_name.casefold()) for text,_ in log._history)
        end=min(self.page_offset+visible,count)
        log.newer_page.setEnabled(self.started is None and end<count)
        log.page_caption.setText(f'{min(self.page_offset+1,count)}–{end} / {count}')

    def history(self):
        HistoryDialog(self).exec()

    def mode_changed(self):
        self.win._text_only=self.win._reply_mode.currentData()=='text'
        if self.persist:
            from memory.config_manager import _patch_config
            if self.win._active_provider=='ollama':
                _patch_config(local_voice_reply=not self.win._text_only)
            else:
                _patch_config(reply_mode='text' if self.win._text_only else 'voice')
        permissions=self.win._capabilities.policy['permissions'] if hasattr(self.win,'_capabilities') else {'microphone':True}
        self.win._mute_btn.setEnabled((self.win._active_provider=='ollama' or not self.win._text_only) and permissions['microphone'])
        self.win._style_mute_btn()
        if self.started is None:
            self.win._apply_state('LISTENING')
        if self.win._active_provider=='ollama':
            if self.win._text_only and getattr(self.win,'_local_voice',None):
                self.win._local_voice.cancel()
            self.win._log.append_log('SYS: '+t('Javoblarni lokal ovozda o‘qish o‘chirildi.' if self.win._text_only else 'Javoblar lokal ovozda o‘qiladi. Gapirish uchun mikrofon tugmasini bosing.'))
        else:
            self.win._log.append_log('SYS: '+('Matnli rejim: mikrofon uzatilmaydi, javob ovozi o‘chiq.' if self.win._text_only else 'Ovozli rejim yoqildi.'))
        if self.win.on_audio_device_change:self.win.on_audio_device_change()

    def state(self,state):
        if self.current_task and state in ('CONNECTING','BLOCKED') and self.current_task['status']=='Bajarilmoqda':
            self.current_task['status']='Uzuldi' if state=='CONNECTING' else 'Ruxsat o‘chiq';self.save_task()
        if state in ('THINKING','PROCESSING','SPEAKING','CANCEL_PENDING','APPROVAL'):
            if self.started is None:
                self.started=time.monotonic()
                self.detail('Natijani shu suhbatda ko‘rasiz.')
            self.stage=state
            if state=='CANCEL_PENDING':self.cancel_pending=True
            self.win._task_box.show()
        elif state in ('LISTENING','MUTED','CONNECTING','SLEEPING','BLOCKED'):
            self.started=None;self.cancel_pending=False;self.stage='idle'
            self.win._task_box.hide()
        self.refresh()

    def detail(self,text):
        self.win._task_detail.setText(t(text))
        if self.current_task and self.current_task['status']=='Bajarilmoqda':
            steps=self.current_task['steps']
            if not steps or steps[-1]!=text:steps.append(text);self.current_task['steps']=steps[-100:];self.save_task()

    def refresh(self):
        self.update_page_controls()
        from brave_continuation import refresh
        refresh(self.win)
        if self.cancel_pending:
            text='Bekor qilish so‘raldi. Boshlangan amal tugashi kutilmoqda.'
        else:
            text={'THINKING':'Javob tayyorlanmoqda…','PROCESSING':'Vazifa bajarilmoqda…','SPEAKING':'Javob berilmoqda…','APPROVAL':'Ruxsat kutilmoqda…'}.get(self.stage,'')
        self.win._task_label.setText(t(text))
        self.win._task_cancel.setEnabled(not self.cancel_pending)
        self.win._new_chat_btn.setEnabled(self.started is None)
        self.tick()
        runtime = getattr(self.win, '_local_chat', None)
        if runtime is not None and runtime.busy and not self.cancel_pending:
            runtime.refresh_progress()

    def tick(self):
        if self.started is not None:
            seconds=int(time.monotonic()-self.started)
            self.win._task_elapsed.setText(f'{seconds//60:02}:{seconds%60:02}')

    def cancel(self):
        self.win._do_interrupt()
        self.mark_cancelled()
        self.cancel_pending=self.started is not None
        self.refresh()

    def mark_cancelled(self):
        if self.current_task and self.current_task['status']=='Bajarilmoqda':
            self.current_task['status']='Bekor qilindi'
            self.current_task['duration']=round(time.monotonic()-getattr(self,'_task_started',time.monotonic()),1)
            self.save_task()


def build_features(win,layout):
    from brave_ui import colors,font,button_style,set_icon
    c=colors()
    win.on_chat_change=None
    from ui import _read_full_config
    win._text_only=win._active_provider=='ollama' or _read_full_config().get('reply_mode')=='text'
    row=QHBoxLayout()
    win._history_btn=QPushButton(t('Tarix'));set_icon(win._history_btn,'memory')
    win._new_chat_btn=QPushButton(t('Yangi'));set_icon(win._new_chat_btn,'plus')
    for button in (win._history_btn,win._new_chat_btn):
        button.setStyleSheet(button_style()+'QPushButton {padding:5px 8px;}')
        button.setFixedHeight(32);row.addWidget(button)
    from brave_chat_tools import export_chat,shortcut_help
    tools=QPushButton();set_icon(tools,'more');tools.setToolTip(t('Suhbat vositalari'));tools.setFixedSize(32,32)
    tools.setStyleSheet(button_style()+'QPushButton {padding:0;} QPushButton::menu-indicator {image:none;width:0px;}')
    tools.setObjectName('BraveChatTools');tools.setAccessibleName(t('Suhbat vositalari'))
    from brave_conversation import memory_dialog,branch_last
    menu=QMenu(tools)
    entries=[('Suhbatni eksport qilish',lambda:export_chat(win)),
             ('Suhbat ichida qidirish',lambda:__import__('brave_chat_search').open_search(win)),
             ('AI vazifalar navbati',lambda:__import__('brave_task_queue').open_queue(win)),
             ('Ikki modelni taqqoslash',lambda:__import__('brave_model_duel').open_duel(win)),
             ('Shaxsiy slash buyruqlar',lambda:__import__('brave_custom_commands').open_commands(win)),
             ('AI amallari',lambda:__import__('brave_text_actions').open_text_actions(win,win._input.text())),
             ('AI Studio',lambda:__import__('brave_ai_studio').open_studio(win)),
             ('Suhbat xotirasi',lambda:memory_dialog(win)),
             ('Oxirgi xabarni tahrirlash',lambda:branch_last(win,True)),
             ('Qayta javob olish',lambda:branch_last(win)),
             ('Suhbat versiyalari va faktlar',lambda:__import__('brave_conversation_inspector').open_inspector(win)),
             ('Lokal tahlil',lambda:__import__('brave_document_lab').open_analysis(win)),
             ('Offline ovoz',lambda:__import__('brave_local_voice').open_voice(win)),
             ('Klaviatura yordami',lambda:shortcut_help(win))]
    for title,callback in entries:menu.addAction(t(title),callback)
    tools.setMenu(menu);row.addWidget(tools)
    menu.aboutToShow.connect(lambda:[action.setText(t(title)) for action,(title,_) in zip(menu.actions(),entries)])
    menu.setStyleSheet(f'QMenu {{background:{c.PANEL};color:{c.TEXT};border:1px solid {c.BORDER};padding:5px;}} QMenu::item {{padding:9px 16px;}} QMenu::item:selected {{background:{c.PRI_GHO};color:{c.PRI};}}')
    for key,callback in [('Ctrl+F',lambda:__import__('brave_chat_search').open_search(win)),('Ctrl+L',lambda:win._input.setFocus()),('Ctrl+Shift+E',lambda:export_chat(win)),('F1',lambda:shortcut_help(win))]:
        shortcut=QShortcut(QKeySequence(key),win);shortcut.activated.connect(callback)
    win._reply_mode=QComboBox()
    win._reply_mode.setMaximumWidth(220)
    win._reply_mode.setFont(font(9))
    win._reply_mode.addItem(t('Ovoz + matn'),'voice');win._reply_mode.addItem(t('Faqat matn'),'text')
    win._reply_mode.setCurrentIndex(1 if win._text_only else 0)
    win._reply_mode.setToolTip(t('Javob rejimi'))
    arrow=(Path(__file__).resolve().parent/'assets'/'chevron.svg').as_posix()
    win._reply_mode.setStyleSheet(f'QComboBox {{color:{c.TEXT};background:{c.PANEL2};border:1px solid {c.BORDER};border-radius:8px;padding:6px 8px;}} QComboBox::drop-down {{width:18px;border:none;background:transparent;}} QComboBox::down-arrow {{image:url("{arrow}");width:10px;height:10px;}} QComboBox QAbstractItemView {{color:{c.TEXT};background:{c.PANEL2};selection-background-color:{c.PRI_GHO};}}')
    row.addStretch(1);row.addWidget(win._reply_mode);layout.addLayout(row)
    box=QFrame();win._task_box=box
    box.setStyleSheet(f'QFrame {{background:{c.PRI_GHO};border:none;border-radius:10px;}}')
    content=QVBoxLayout(box);content.setContentsMargins(10,8,10,8);content.setSpacing(4)
    top=QHBoxLayout();win._task_label=QLabel();win._task_label.setWordWrap(True);win._task_label.setFont(font(9,True));win._task_label.setStyleSheet(f'color:{c.TEXT};')
    top.addWidget(win._task_label,1);win._task_elapsed=QLabel('00:00');win._task_elapsed.setStyleSheet(f'color:{c.TEXT_MED};');top.addWidget(win._task_elapsed)
    content.addLayout(top)
    win._task_detail=QLabel(t('Natijani shu suhbatda ko‘rasiz.'));win._task_detail.setWordWrap(True);win._task_detail.setFont(font(8));win._task_detail.setStyleSheet(f'color:{c.TEXT_MED};');content.addWidget(win._task_detail)
    win._task_detail.setTextFormat(Qt.TextFormat.PlainText)
    win._task_cancel=QPushButton(t('Bekor qilish'));win._task_cancel.setStyleSheet(button_style());win._task_cancel.setFixedHeight(28);content.addWidget(win._task_cancel)
    box.hide();layout.addWidget(box)
    win._features=Features(win)
    win._history_btn.clicked.connect(win._features.history)
    win._new_chat_btn.clicked.connect(lambda:win._features.switch_chat())
    win._reply_mode.currentIndexChanged.connect(lambda:win._features.mode_changed())
    win._task_cancel.clicked.connect(win._features.cancel)
    from brave_control_center import Controls
    win._capabilities=Controls(win)
