"""Native permission controls, project context, reminders and a mini composer."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import threading

from PyQt6.QtCore import Qt,QDateTime,QTimer,pyqtSignal
from PyQt6.QtGui import QKeySequence,QShortcut
from PyQt6.QtWidgets import (QAbstractItemView,QCheckBox,QComboBox,QDateTimeEdit,QDialog,
    QFileDialog,QGridLayout,QHBoxLayout,QLabel,QLineEdit,QListWidget,QListWidgetItem,QPlainTextEdit,
    QPushButton,QTabWidget,QVBoxLayout,QWidget)
from brave_i18n import translate as t
from core import access_policy,project_context,workspace_store

TZ=timezone(timedelta(hours=5))


def style_dialog(dialog,title):
    from brave_ui import colors,font,button_style
    c=colors();dialog.setWindowTitle(t(title));dialog.setFont(font(10))
    from pathlib import Path
    arrow=(Path(__file__).resolve().parent/'assets'/'chevron.svg').as_posix()
    dialog.setStyleSheet(f'QDialog {{background:{c.PANEL};color:{c.TEXT};}} QWidget {{font-family:"Segoe UI";font-size:13px;color:{c.TEXT};}} QLineEdit,QPlainTextEdit,QListWidget,QComboBox,QDateTimeEdit {{background:{c.BG};color:{c.TEXT};border:1px solid {c.BORDER};border-radius:8px;padding:8px;}} QComboBox::drop-down {{width:22px;border:none;background:transparent;}} QComboBox::down-arrow {{image:url("{arrow}");width:10px;height:10px;}} QCheckBox {{color:{c.TEXT};spacing:8px;padding:5px;}} QTabWidget::pane {{border:1px solid {c.BORDER};border-radius:10px;}} QTabBar::tab {{color:{c.TEXT_MED};background:{c.PANEL2};padding:12px;}} QTabBar::tab:selected {{color:{c.PRI};}}')
    dialog.setStyleSheet(dialog.styleSheet()+f'QListWidget::item {{padding:5px;border-radius:5px;}} QListWidget::item:selected {{background:{c.PRI_GHO};color:{c.PRI};}} QScrollBar:vertical {{background:transparent;width:8px;margin:0;}} QScrollBar::handle:vertical {{background:{c.BORDER};border-radius:4px;min-height:24px;}} QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{height:0;}} QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {{background:transparent;}}')
    dialog.setStyleSheet(dialog.styleSheet()+f'QSpinBox {{background:{c.BG};color:{c.TEXT};border:1px solid {c.BORDER};border-radius:8px;padding:8px;}} QTabBar QToolButton {{background:{c.PANEL2};color:{c.TEXT};border:1px solid {c.BORDER};}}')
    dialog.setStyleSheet(dialog.styleSheet()+f'QCheckBox::indicator {{width:14px;height:14px;border:1px solid {c.TEXT_DIM};border-radius:3px;background:{c.BG};}} QCheckBox::indicator:checked {{background:{c.PRI};border-color:{c.PRI};}} QCheckBox::indicator:hover {{border-color:{c.TEXT};}}')
    dialog.setStyleSheet(dialog.styleSheet()+f'QTableWidget {{background:{c.BG};alternate-background-color:{c.PANEL2};color:{c.TEXT};gridline-color:{c.BORDER};border:1px solid {c.BORDER};selection-background-color:{c.PRI_GHO};}} QHeaderView {{background:{c.PANEL2};}} QHeaderView::section {{background:{c.PANEL2};color:{c.TEXT_MED};padding:7px;border:1px solid {c.BORDER};}} QTableCornerButton::section {{background:{c.PANEL2};border:1px solid {c.BORDER};}}')
    return button_style()


class Controls:
    def __init__(self,win):
        self.win=win;self.persist=False;self.hotkey=None;self.mini=None
        from ui import _read_full_config
        config=_read_full_config()
        raw=config.get('access_policy',{})
        raw_perms=raw.get('permissions',{})
        self.policy={'mode':raw.get('mode','smart'),'turbo':bool(raw.get('turbo')),
                     'permissions':{key:raw_perms.get(key,access_policy.DEFAULT_POLICY['permissions'].get(key,True)) is True for key in access_policy.CAPABILITIES},
                     'educational_filter':bool(raw.get('educational_filter',True))}
        if self.policy['mode'] not in ('ask','smart','full'):self.policy['mode']='smart'
        if not all(self.policy['permissions'].values()) and self.policy['mode']=='full':
            self.policy['mode']='smart';self.policy['turbo']=False
        self.restore=config.get('turbo_restore',{})
        self.shortcuts=QShortcut(QKeySequence('Ctrl+Alt+F8'),win)
        self.shortcuts.activated.connect(self.open_mini)
        self.refresh_header()

    def refresh_header(self):
        from brave_ui import colors,button_style,set_icon
        c=colors();full=self.policy['mode']=='full'
        self.win._hub_btn.setText(t('Turbo' if self.policy['turbo'] else 'Markaz'))
        self.win._hub_btn.setToolTip(t({'ask':'Har safar so‘rash','smart':'Avtomatik tasdiqlash','full':'To‘liq kirish'}[self.policy['mode']]))
        self.win._hub_btn.setStyleSheet(button_style()+(f'QPushButton {{color:{c.PRI};background:{c.PRI_GHO};}}' if full else ''))
        set_icon(self.win._hub_btn,'spark' if self.policy['turbo'] else 'sliders','PRI' if full else 'TEXT_MED')

    def enable(self):
        self.persist=True
        self.win._style_mute_btn()
        self.win._mute_btn.setEnabled((self.win._active_provider=='ollama' or not self.win._text_only) and self.policy['permissions']['microphone'])
        if not self.hotkey:
            from core.hotkey import PushToTalk
            self.hotkey=PushToTalk(lambda held:self.win._mini_sig.emit() if held else None,('ctrl','alt','f8'))
            if self.hotkey.start()=='global':self.shortcuts.setEnabled(False)
            from PyQt6.QtWidgets import QApplication
            QApplication.instance().aboutToQuit.connect(self.hotkey.stop)

    def save(self,extra=None):
        if self.persist:
            from memory.config_manager import _patch_config
            _patch_config(access_policy=deepcopy(self.policy),turbo_restore=self.restore,**(extra or {}))
        self.win._style_mute_btn()
        self.win._mute_btn.setEnabled((self.win._active_provider=='ollama' or not self.win._text_only) and self.policy['permissions']['microphone'])
        self.win._refresh_talk_btns()
        voice=getattr(self.win,'_local_voice',None)
        if voice and not self.policy['permissions']['microphone']:voice.cancel()
        self.refresh_header()
        callback=self.win.on_access_change
        if callback:callback()

    def turbo(self,enabled):
        if enabled and not self.policy['turbo']:
            from ui import _read_full_config
            config=_read_full_config()
            self.restore={'policy':deepcopy(self.policy),'media_resolution':config.get('media_resolution','medium'),
                          'thinking_enabled':config.get('thinking_enabled',False)}
            self.policy={'mode':'full','turbo':True,'permissions':{key:True for key in access_policy.CAPABILITIES},'educational_filter':False}
            self.save({'media_resolution':'high','thinking_enabled':True})
        elif not enabled and self.policy['turbo']:
            self.policy=deepcopy(self.restore.get('policy',access_policy.DEFAULT_POLICY))
            self.policy['turbo']=False
            self.save({'media_resolution':self.restore.get('media_resolution','medium'),
                       'thinking_enabled':self.restore.get('thinking_enabled',False)})

    def open(self):
        self.win._close_setup()
        self.win._close_controls()
        ControlCenter(self).exec()

    def open_mini(self):
        if self.mini is None:self.mini=MiniWindow(self.win)
        if self.mini.isVisible():self.mini.hide()
        else:
            self.mini.show();self.mini.raise_();self.mini.activateWindow();self.mini.input.setFocus()


class MiniWindow(QDialog):
    def __init__(self,win):
        super().__init__(win,Qt.WindowType.Tool|Qt.WindowType.WindowStaysOnTopHint)
        self.win=win;self.syncing=False
        style=style_dialog(self,'Brave · Mini');self.resize(470,370)
        layout=QVBoxLayout(self)
        self.status=QLabel(t('Ctrl+Alt+F8 · Mini oyna'));layout.addWidget(self.status)
        self.reply=QPlainTextEdit();self.reply.setReadOnly(True);self.reply.setPlaceholderText(t('Javob shu yerda ko‘rinadi.'));layout.addWidget(self.reply,1)
        from brave_chat import ComposerEdit
        self.input=ComposerEdit();self.input.setFixedHeight(80);self.input.setPlaceholderText(t('Savolingizni yozing…'));layout.addWidget(self.input)
        self.send=QPushButton(t('Yuborish'));self.send.setStyleSheet(style);self.send.clicked.connect(win._send);layout.addWidget(self.send)
        self.input.returnPressed.connect(win._send)
        self.input.textChanged.connect(lambda:self.sync(self.input,win._input))
        win._input.textChanged.connect(lambda:self.sync(win._input,self.input))
        self.input.setText(win._input.text())
        win._log.messageAdded.connect(self.message)
        win._state_sig.connect(lambda _:self.status.setText(win._chat_status_lbl.text()))

    def sync(self,source,target):
        if self.syncing:return
        self.syncing=True
        try:target.setText(source.text())
        finally:self.syncing=False

    def message(self,text,stamp):
        prefix,_,body=text.partition(':')
        if prefix.casefold() in ('brave',self.win._assistant_name.casefold(),'err','error'):
            self.reply.setPlainText(body.strip())


class ControlCenter(QDialog):
    scanReady=pyqtSignal(object)
    reminderReady=pyqtSignal(str)

    def __init__(self,controller):
        super().__init__(controller.win)
        self.controller=controller;self.win=controller.win;self.root=None;self.refreshing=False
        self.button_style=style_dialog(self,'Brave markazi');self.resize(860,690)
        layout=QVBoxLayout(self)
        from brave_ui import colors,current_theme
        from brave_brand import logo_pixmap
        header=QHBoxLayout();logo=QLabel();logo.setProperty('brave_logo_size',40);logo.setPixmap(logo_pixmap(40,current_theme(),2));header.addWidget(logo)
        title=QLabel(t('Brave markazi'));title.setStyleSheet(f'font-size:22px;font-weight:600;color:{colors().WHITE};');header.addWidget(title,1);layout.addLayout(header)
        tabs=QTabWidget();self.tabs=tabs;layout.addWidget(tabs,1)
        tabs.addTab(self.security(),t('Xavfsizlik'));tabs.addTab(self.projects(),t('Loyiha'));tabs.addTab(self.reminders(),t('Eslatmalar'))
        from brave_knowledge import KnowledgePage
        tabs.addTab(KnowledgePage(self),t('Bilim kutubxonasi'))
        from brave_companion import memory_page,conversation_page,routines_page,tasks_page
        for title,factory in [('Suhbat',conversation_page),('Xotira',memory_page),('Ssenariylar',routines_page),('Vazifalar',tasks_page)]:
            tabs.addTab(factory(self),t(title))
        from brave_workbench import usage_page,RecoveryPage,VoicePage
        for title,factory in [('Sarflanish',usage_page),('Tiklash',RecoveryPage),('Ovoz sinovi',VoicePage)]:tabs.addTab(factory(self),t(title))
        tabs.setUsesScrollButtons(True)
        mini=QPushButton(t('Mini oynani ochish · Ctrl+Alt+F8'));mini.setStyleSheet(self.button_style)
        mini.clicked.connect(lambda:(self.accept(),controller.open_mini()));layout.addWidget(mini)
        self.scanReady.connect(self.show_files);self.reminderReady.connect(self.reminder_result)

    def security(self):
        page=QWidget();layout=QVBoxLayout(page);layout.setSpacing(12)
        self.edu_filter=QCheckBox(t("🎓 Ta'limiy cheklov (Faqat YouTube va ta'limiy saytlar)"))
        self.edu_filter.setChecked(self.controller.policy.get('educational_filter',True))
        self.edu_filter.setToolTip(t("Ingliz tili o‘rganish xavfsizligi: faqat YouTube, lug‘atlar va tasdiqlangan ta’lim manbalariga ruxsat beradi."))
        layout.addWidget(self.edu_filter)
        edu_note=QLabel(t("Ingliz tili o‘rganish xavfsizligi: Faqat YouTube, Cambridge/Oxford lug‘atlari, TED va ta’limiy manbalarga ruxsat beriladi. Chalg‘ituvchi va xavfli saytlar to‘siladi."))
        edu_note.setWordWrap(True);layout.addWidget(edu_note)
        self.edu_filter.toggled.connect(self.apply_permissions)
        self.turbo=QCheckBox(t('Turbo · barcha imkoniyatlar'));self.turbo.setChecked(self.controller.policy['turbo']);layout.addWidget(self.turbo)
        note=QLabel(t('Turbo barcha ruxsatlarni yoqadi, amallarni avtomatik tasdiqlaydi va yuqori media sifatini tanlaydi. OS ruxsatlari va Gemini kvotalari saqlanadi.'))
        note.setWordWrap(True);layout.addWidget(note)
        layout.addWidget(QLabel(t('Kirish darajasi')))
        self.mode=QComboBox()
        for text,value in [('Har safar so‘rash','ask'),('Avtomatik tasdiqlash','smart'),('To‘liq kirish','full')]:self.mode.addItem(t(text),value)
        self.mode.setCurrentIndex(self.mode.findData(self.controller.policy['mode']));layout.addWidget(self.mode)
        explain=QLabel(t('Avtomatik rejim xavfli amallarga tasdiq so‘raydi. To‘liq kirishda amallar so‘rovsiz bajariladi.'))
        explain.setWordWrap(True);layout.addWidget(explain)
        self.permissions={};grid=QGridLayout();grid.setVerticalSpacing(4);layout.addLayout(grid)
        titles={'network':'Internet','microphone':'Mikrofon','screen':'Ekran','camera':'Kamera','files':'Fayllar','code':'Kod bajarish','system':'Kompyuterni boshqarish'}
        for index,key in enumerate(access_policy.CAPABILITIES):
            check=QCheckBox(t(titles[key]));check.setChecked(self.controller.policy['permissions'][key]);grid.addWidget(check,index//2,index%2);self.permissions[key]=check
            if key=='code':check.setToolTip(t('Kod sandboxsiz, sizning OS huquqlaringiz bilan ishlaydi.'))
            check.toggled.connect(self.apply_permissions)
        self.mode.currentIndexChanged.connect(self.apply_permissions)
        self.turbo.toggled.connect(self.apply_turbo)
        note=QLabel(t('Ruxsatlar yordamchi amallariga tatbiq etiladi. Boshlangan amal tugashi mumkin.'))
        note.setWordWrap(True);layout.addWidget(note)
        self.audit=QPlainTextEdit();self.audit.setReadOnly(True);self.audit.setMaximumHeight(110)
        self.audit.setPlaceholderText(t('Amallar tarixi shu yerda ko‘rinadi.'))
        rows=workspace_store.read('action-audit.json',[]) if self.controller.persist else []
        self.audit.setPlainText('\n'.join(f"{row['at']} · {row['tool']} · {row['decision']}" for row in rows[-40:]));layout.addWidget(self.audit)
        return page

    def apply_permissions(self,*args):
        if self.refreshing:return
        was_turbo=self.controller.policy['turbo']
        mode=self.mode.currentData()
        permissions={key:check.isChecked() for key,check in self.permissions.items()}
        self.refreshing=True
        if self.sender() is self.mode and mode=='full':
            permissions={key:True for key in self.permissions}
            for check in self.permissions.values():check.setChecked(True)
        elif mode=='full' and not all(permissions.values()):
            mode='smart';self.mode.setCurrentIndex(self.mode.findData(mode))
        self.refreshing=False
        edu_val=self.edu_filter.isChecked() if hasattr(self,'edu_filter') else True
        self.controller.policy={'mode':mode,'turbo':False,'permissions':permissions,'educational_filter':edu_val}
        self.refreshing=True;self.turbo.setChecked(False);self.refreshing=False
        extra={'media_resolution':self.controller.restore.get('media_resolution','medium'),
               'thinking_enabled':self.controller.restore.get('thinking_enabled',False)} if was_turbo else None
        self.controller.save(extra)

    def apply_turbo(self,enabled):
        if self.refreshing:return
        self.controller.turbo(enabled)
        self.refreshing=True
        self.mode.setCurrentIndex(self.mode.findData(self.controller.policy['mode']))
        for key,check in self.permissions.items():check.setChecked(self.controller.policy['permissions'][key])
        self.refreshing=False

    def projects(self):
        page=QWidget();layout=QVBoxLayout(page)
        profiles=QHBoxLayout();self.profile=QComboBox();profiles.addWidget(self.profile,1)
        for label,callback in [('Profilni saqlash',self.save_profile),('Profilni qo‘llash',self.apply_profile),('O‘chirish',self.delete_profile)]:
            button=QPushButton(t(label));button.setStyleSheet(self.button_style);button.clicked.connect(callback);profiles.addWidget(button)
        layout.addLayout(profiles);self.refresh_profiles()
        self.project_context=QLineEdit();self.project_context.setPlaceholderText(t('Loyiha konteksti: maqsad, uslub, talablar…'));layout.addWidget(self.project_context)
        row=QHBoxLayout();self.project_path=QLineEdit();self.project_path.setReadOnly(True);row.addWidget(self.project_path,1)
        choose=QPushButton(t('Papka tanlash'));choose.setStyleSheet(self.button_style);choose.clicked.connect(self.choose_project);row.addWidget(choose);layout.addLayout(row)
        self.project_search=QLineEdit();self.project_search.setPlaceholderText(t('Fayllarni qidirish…'));self.project_search.textChanged.connect(self.filter_files);layout.addWidget(self.project_search)
        self.files=QListWidget();self.files.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection);layout.addWidget(self.files,1)
        note=QLabel(t('Fayllar lokal o‘qiladi. Faqat tanlangan matn savol yuborilganda Gemini’ga jo‘natiladi. Maxfiy sozlamalar avtomatik qo‘shilmaydi.'))
        note.setWordWrap(True);layout.addWidget(note)
        self.question=QPlainTextEdit();self.question.setMaximumHeight(100);self.question.setPlaceholderText(t('Loyiha haqida savol yozing…'));layout.addWidget(self.question)
        self.project_send=QPushButton(t('Tanlangan fayllar bilan so‘rash'));self.project_send.setEnabled(False);self.project_send.setStyleSheet(self.button_style);self.project_send.clicked.connect(self.send_project);layout.addWidget(self.project_send)
        self.question.textChanged.connect(self.update_project_send);self.files.itemSelectionChanged.connect(self.update_project_send)
        return page

    def choose_project(self):
        root=QFileDialog.getExistingDirectory(self,t('Papka tanlash'))
        if not root:return
        self.load_project(root)

    def load_project(self,root):
        self.root=root;self.project_path.setText(root);self.files.clear();self.project_send.setEnabled(False)
        def work():
            try:result=project_context.scan(root)
            except Exception:result=[]
            try:self.scanReady.emit((root,result))
            except RuntimeError:pass
        threading.Thread(target=work,daemon=True).start()

    def refresh_profiles(self):
        self.profile.clear();self.profile.addItem(t('Loyiha profili'),None)
        for row in workspace_store.read('project-profiles.json',[]):self.profile.addItem(row['name'],row)

    def save_profile(self):
        if not self.root:return
        from PyQt6.QtWidgets import QInputDialog
        from core import companion
        import uuid
        old=self.profile.currentData();name,ok=QInputDialog.getText(self,t('Profilni saqlash'),t('Profil nomi'),text=old['name'] if old else '')
        if not ok or not name.strip():return
        row={'id':old['id'] if old else uuid.uuid4().hex,'name':name.strip(),'root':self.root,'context':self.project_context.text(),
             'policy':deepcopy(self.controller.policy),'routines':companion.routines(),'restore':deepcopy(self.controller.restore)}
        from ui import _read_full_config
        cfg=_read_full_config();row['settings']={key:cfg.get(key,default) for key,default in [('media_resolution','medium'),('thinking_enabled',False)]}
        workspace_store.update('project-profiles.json',lambda rows:[r for r in rows if r['id']!=row['id']]+[row]);self.refresh_profiles()
        self.profile.setCurrentIndex(self.profile.findText(row['name']))

    def apply_profile(self):
        row=self.profile.currentData()
        if not row:return
        from pathlib import Path
        if not Path(row['root']).is_dir():self.win._log.append_log('ERR: Profil papkasi topilmadi.');return
        self.controller.policy=deepcopy(row['policy']);self.controller.restore=deepcopy(row.get('restore',{}))
        workspace_store.write('routines.json',row.get('routines',[]))
        self.project_context.setText(row.get('context',''));self.load_project(row['root']);self.controller.save(row.get('settings',{}))
        self.refreshing=True;self.turbo.setChecked(self.controller.policy['turbo']);self.mode.setCurrentIndex(self.mode.findData(self.controller.policy['mode']))
        for key,check in self.permissions.items():check.setChecked(self.controller.policy['permissions'][key])
        self.refreshing=False

    def delete_profile(self):
        row=self.profile.currentData()
        if row:workspace_store.update('project-profiles.json',lambda rows:[r for r in rows if r['id']!=row['id']]);self.refresh_profiles()

    def show_files(self,result):
        root,files=result
        if root!=self.root:return
        self.files.clear();self.files.addItems(files);self.filter_files()

    def filter_files(self):
        query=self.project_search.text().casefold()
        for index in range(self.files.count()):
            item=self.files.item(index);item.setHidden(query not in item.text().casefold())
        if hasattr(self,'project_send'):self.update_project_send()

    def update_project_send(self):
        self.project_send.setEnabled(bool(self.root and self.question.toPlainText().strip() and any(not item.isHidden() for item in self.files.selectedItems())))

    def send_project(self):
        files=[item.text() for item in self.files.selectedItems() if not item.isHidden()]
        question=self.question.toPlainText().strip()
        if not self.root or not files or not question:return
        text=project_context.context(self.root,files,question,self.controller.policy['turbo'])
        if self.project_context.text():text='User project context: '+self.project_context.text()+'\n\n'+text
        if self.win._input.text().strip():
            self.win._log.append_log('ERR: Avval yozilayotgan xabarni yuboring yoki tozalang.')
            return
        self.win._input.setText(text);self.accept();self.win._send()

    def reminders(self):
        page=QWidget();layout=QVBoxLayout(page)
        self.reminder_text=QLineEdit();self.reminder_text.setPlaceholderText(t('Nimani eslatish kerak?'));layout.addWidget(self.reminder_text)
        self.when=QDateTimeEdit(QDateTime.currentDateTimeUtc().addSecs(5*3600+300));self.when.setCalendarPopup(True);self.when.setDisplayFormat('yyyy-MM-dd HH:mm');layout.addWidget(self.when)
        layout.addWidget(QLabel(t('Vaqt: Toshkent · UTC+5')))
        self.reminder_add=QPushButton(t('Eslatma qo‘shish'));self.reminder_add.setStyleSheet(self.button_style);self.reminder_add.clicked.connect(self.add_reminder);layout.addWidget(self.reminder_add)
        self.reminder_status=QLabel(t('Brave yopiq bo‘lsa ham tizim eslatmani chiqaradi.'));self.reminder_status.setWordWrap(True);layout.addWidget(self.reminder_status)
        self.reminder_list=QListWidget();layout.addWidget(self.reminder_list,1)
        cancel=QPushButton(t('Tanlangan eslatmani bekor qilish'));cancel.setStyleSheet(self.button_style);cancel.clicked.connect(self.cancel_reminder);layout.addWidget(cancel)
        self.refresh_reminders();return page

    def refresh_reminders(self):
        self.reminder_list.clear()
        rows=workspace_store.read('reminders.json',[]) if self.controller.persist else []
        now=datetime.now(TZ)
        for row in rows:
            try:
                due=datetime.fromisoformat(row['at'])
                if row.get('cancelled') or due<=now:continue
            except (KeyError,ValueError,TypeError,AttributeError):continue
            item=QListWidgetItem(row['at'][:16].replace('T',' ')+' · '+row['message']);item.setData(Qt.ItemDataRole.UserRole,row['task']);self.reminder_list.addItem(item)

    def add_reminder(self):
        message=self.reminder_text.text().strip()
        if not message:return
        value=self.when.dateTime();target=datetime(value.date().year(),value.date().month(),value.date().day(),value.time().hour(),value.time().minute(),tzinfo=TZ)
        if target<=datetime.now(TZ):self.reminder_status.setText(t('Kelajakdagi vaqtni tanlang.'));return
        local=target.astimezone().replace(tzinfo=None)
        self.reminder_add.setEnabled(False);self.reminder_status.setText(t('Eslatma rejalashtirilmoqda…'))
        def work():
            from actions.reminder import reminder
            try:result=reminder({'date':local.strftime('%Y-%m-%d'),'time':local.strftime('%H:%M'),'message':message})
            except Exception:result='failed'
            try:self.reminderReady.emit(result)
            except RuntimeError:pass
        threading.Thread(target=work,daemon=True).start()

    def reminder_result(self,result):
        self.reminder_add.setEnabled(True)
        self.reminder_status.setText(t('Eslatma qo‘shildi.' if result.startswith('Reminder set') else ('Eslatma bekor qilindi.' if result.startswith('Reminder cancelled') else 'Tizim eslatmani ro‘yxatdan o‘tkazmadi. Boshqa vaqt tanlang yoki tizim ruxsatini tekshiring.')))
        self.refresh_reminders()

    def cancel_reminder(self):
        item=self.reminder_list.currentItem()
        if not item:return
        from actions.reminder import cancel_reminder
        task=item.data(Qt.ItemDataRole.UserRole)
        def work():
            try:ok=cancel_reminder(task)
            except Exception:ok=False
            try:self.reminderReady.emit('Reminder cancelled' if ok else 'failed')
            except RuntimeError:pass
        threading.Thread(target=work,daemon=True).start()


def show_permission(win,name,args,future):
    if future.done():return
    dialog=QDialog(win);style=style_dialog(dialog,'Amalni tekshiring');dialog.resize(680,460)
    layout=QVBoxLayout(dialog)
    title=QLabel(t('Brave quyidagi amalni bajarishni so‘rayapti.'));title.setWordWrap(True);layout.addWidget(title)
    preview=QPlainTextEdit();preview.setReadOnly(True);preview.setPlainText(access_policy.preview(name,args));layout.addWidget(preview,1)
    row=QHBoxLayout()
    approve=QPushButton(t('Ruxsat berish'));reject=QPushButton(t('Bekor qilish'))
    for button in (approve,reject):button.setStyleSheet(style);row.addWidget(button)
    layout.addLayout(row)
    def resolve(value):
        if future.done():return
        future.set_result(value)
        dialog.done(QDialog.DialogCode.Accepted if value else QDialog.DialogCode.Rejected)
    approve.clicked.connect(lambda:resolve(True));reject.clicked.connect(lambda:resolve(False));dialog.rejected.connect(lambda:resolve(False))
    timer=QTimer(dialog);timer.setInterval(250);timer.timeout.connect(lambda:dialog.close() if future.done() else None);timer.start()
    dialog.finished.connect(timer.stop)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    win._permission_dialog=dialog
    win._apply_state('APPROVAL')
    dialog.setModal(True);dialog.open()
    dialog.raise_();dialog.activateWindow()
