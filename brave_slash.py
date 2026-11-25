"""Keyboard-accessible slash suggestions and explicit local action dispatch."""
from PyQt6.QtCore import QObject,QEvent,Qt,QPoint
from PyQt6.QtWidgets import QFrame,QVBoxLayout,QHBoxLayout,QListWidget,QListWidgetItem,QLabel,QToolButton,QApplication
from brave_i18n import translate as t
from core.slash_commands import get,parse,matches,example
from core import command_store


class SlashMenu(QObject):
    def __init__(self,win):
        super().__init__(win);self.win=win;self.editor=win._input
        self.popup=QFrame(win,Qt.WindowType.ToolTip);self.popup.setObjectName('SlashPopup')
        self.popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        layout=QVBoxLayout(self.popup);layout.setContentsMargins(7,7,7,7)
        label=QLabel(t('Buyruqlar · ↑↓ tanlash · Tab/Enter qo‘yish'));layout.addWidget(label)
        from brave_command_library import CATEGORIES
        self.category='all';self.filters={};bar=QHBoxLayout();layout.addLayout(bar)
        for key,title in CATEGORIES:
            button=QToolButton();button.setText(t(title));button.setCheckable(True);button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(lambda checked=False,k=key:self.filter(k));bar.addWidget(button);self.filters[key]=button
        self.list=QListWidget();self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus);layout.addWidget(self.list)
        self.list.itemClicked.connect(lambda item:self.choose())
        self.list.currentItemChanged.connect(self.describe)
        bottom=QHBoxLayout();layout.addLayout(bottom)
        self.detail=QLabel();self.detail.setWordWrap(True);self.detail.setTextFormat(Qt.TextFormat.PlainText);bottom.addWidget(self.detail,1)
        self.star=QToolButton();self.star.setFocusPolicy(Qt.FocusPolicy.NoFocus);self.star.setToolTip(t('Saralanganlar'));self.star.clicked.connect(self.favorite);bottom.addWidget(self.star)
        self.editor.installEventFilter(self);self.editor.textChanged.connect(self.refresh)

    def refresh(self):
        text=self.editor.text();prefs=command_store.preferences()
        rows=matches(text,self.category,prefs['favorites'],prefs['recent'])
        # A recognized token followed by whitespace is an argument, not a search.
        try:command,_,_=parse(text)
        except ValueError:command=None
        if not text.startswith('/') or (command and any(char.isspace() for char in text)) or not self.editor.isVisible():self.popup.hide();return
        from brave_ui import colors
        c=colors();self.popup.setStyleSheet(f'QFrame#SlashPopup {{background:{c.PANEL};border:1px solid {c.BORDER};border-radius:10px;}} QLabel {{color:{c.TEXT_MED};}} QListWidget {{background:{c.PANEL};color:{c.TEXT};border:none;}} QListWidget::item {{padding:8px;}} QListWidget::item:selected {{background:{c.PRI_GHO};color:{c.PRI};}} QToolButton {{background:{c.PANEL};color:{c.TEXT_MED};border:1px solid {c.BORDER};border-radius:5px;padding:5px;}} QToolButton:checked {{background:{c.PRI_GHO};color:{c.PRI};}}')
        selected=self.list.currentItem();selected=selected.data(Qt.ItemDataRole.UserRole) if selected else None
        for key,button in self.filters.items():button.setChecked(key==self.category)
        self.list.clear()
        for command in rows:
            item=QListWidgetItem('/'+command.name+'   '+t(command.description));item.setData(Qt.ItemDataRole.UserRole,command.name)
            if command.name in prefs['favorites']:
                from brave_ui import icon
                item.setIcon(icon('star-filled',c.PRI,14))
            self.list.addItem(item)
            if command.name==selected:self.list.setCurrentItem(item)
        if self.list.currentRow()<0 and rows:self.list.setCurrentRow(0)
        self.describe()
        screen=self.editor.screen().availableGeometry()
        self.popup.resize(min(screen.width()-16,680,max(550,self.editor.width())),min(screen.height()-64,370,150+max(1,len(rows))*35))
        point=self.editor.mapToGlobal(QPoint(0,0));screen=self.editor.screen().availableGeometry()
        x=max(screen.left(),min(point.x(),screen.right()-self.popup.width()))
        y=max(screen.top(),point.y()-self.popup.height()-8)
        self.popup.move(x,y);self.popup.show()

    def filter(self,key):self.category=key;self.refresh()

    def describe(self,*args):
        item=self.list.currentItem();row=get(item.data(Qt.ItemDataRole.UserRole)) if item else None
        self.detail.setText(example(row) if row else t('Mos buyruq topilmadi.'))
        from brave_ui import set_icon
        selected=row and row.name in command_store.preferences()['favorites']
        set_icon(self.star,'star-filled' if selected else 'star','PRI' if selected else 'TEXT_MED');self.star.setEnabled(row is not None)

    def favorite(self):
        item=self.list.currentItem()
        if not item:return
        try:command_store.favorite(item.data(Qt.ItemDataRole.UserRole))
        except (OSError,ValueError) as error:self.detail.setText(t(str(error)));return
        self.refresh()

    def choose(self):
        item=self.list.currentItem()
        if item:self.editor.setText('/'+item.data(Qt.ItemDataRole.UserRole)+' ')
        self.popup.hide();self.editor.setFocus()

    def eventFilter(self,obj,event):
        if (event.type()==QEvent.Type.ShortcutOverride and self.popup.isVisible()
                and event.key() in (Qt.Key.Key_Escape,Qt.Key.Key_Up,Qt.Key.Key_Down,Qt.Key.Key_Tab,Qt.Key.Key_Return,Qt.Key.Key_Enter)):
            event.accept();return True
        if event.type() in (QEvent.Type.Hide,QEvent.Type.FocusOut):self.popup.hide()
        if event.type()==QEvent.Type.KeyPress and self.popup.isVisible():
            key=event.key()
            if key in (Qt.Key.Key_Down,Qt.Key.Key_Up):
                if self.list.count():self.list.setCurrentRow((self.list.currentRow()+(1 if key==Qt.Key.Key_Down else -1))%self.list.count())
                return True
            if key in (Qt.Key.Key_Tab,Qt.Key.Key_Return,Qt.Key.Key_Enter):self.choose();return True
            if key==Qt.Key.Key_Escape:self.popup.hide();return True
        return False


def run_action(win,action,body):
    """Explicit UI actions keep their existing permissions and approvals."""
    if body and action not in ('screen','history','settings','help','find'):
        raise ValueError('Bu buyruq qo‘shimcha matn olmaydi. /help orqali misolni ko‘ring.')
    if action in ('new','retry','edit','memory'):
        from brave_navigation import action_enabled
        if not action_enabled(win,'new-chat') or getattr(win,'_meeting_recording',False):
            raise ValueError('Avval joriy javob tugashini kuting.')
    if action=='duel':
        from brave_model_duel import open_duel
        open_duel(win)
    elif action=='continue':
        from brave_continuation import continue_answer
        return continue_answer(win)
    elif action=='commands':
        from brave_custom_commands import open_commands
        open_commands(win)
    elif action=='queue':
        from brave_task_queue import open_queue
        open_queue(win)
    elif action=='find':
        from brave_chat_search import open_search
        open_search(win,body)
    elif action=='cancel':win._do_interrupt()
    elif action=='forget':
        runtime=getattr(win,'_local_chat',None)
        if runtime:runtime.visual_context.clear(win._features.chat_id)
        win._log.append_log('SYS: '+t('Rasm konteksti unutildi.'))
    elif action in ('help','snippets'):
        from brave_command_library import open_library
        open_library(win,snippets=action=='snippets',query=body)
    elif action=='new':return win._features.switch_chat()
    elif action in ('history','folders'):
        from brave_features import HistoryDialog
        dialog=getattr(win,'_slash_history',None)
        if dialog is None:
            dialog=HistoryDialog(win._features);win._slash_history=dialog
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            dialog.finished.connect(lambda _:setattr(win,'_slash_history',None))
        dialog.search.setText(body);dialog.timer.stop();dialog.refresh();dialog.open();dialog.raise_()
    elif action=='export':
        if not win._features.store.count(win._features.chat_id):raise ValueError('Avval suhbat boshlang.')
        from brave_chat_tools import export_chat
        export_chat(win)
    elif action=='copy':
        answer=win._features.store.last_answer(win._features.chat_id)
        if not answer:raise ValueError('Bu suhbatda tugallangan javob yo‘q.')
        win._clipboard_self_value=answer;QApplication.clipboard().setText(answer)
        win._log.append_log('SYS: '+t('Oxirgi javob nusxalandi.'))
    elif action in ('retry','edit'):
        from brave_conversation import branch_last
        if not any(row[0]=='user' for row in win._features.store.messages(win._features.chat_id)):raise ValueError('Avval suhbat boshlang.')
        return branch_last(win,edit=action=='edit')
    elif action=='memory':
        from brave_conversation import memory_dialog
        memory_dialog(win)
    elif action in ('knowledge','project','permissions'):
        from brave_control_center import ControlCenter
        dialog=getattr(win,'_slash_center',None)
        if dialog is None:
            dialog=ControlCenter(win._capabilities);win._slash_center=dialog
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            dialog.finished.connect(lambda _:setattr(win,'_slash_center',None))
        dialog.tabs.setCurrentIndex({'permissions':0,'project':1,'knowledge':3}[action]);dialog.open();dialog.raise_()
    elif action=='settings':
        from brave_navigation import SECTIONS
        section=body.lower() or None
        if section and section not in {row[0] for row in SECTIONS}:raise ValueError('Bo‘lim: ai, appearance, audio, profile, plugins, system.')
        from brave_settings import open_settings
        open_settings(win,section)
    elif action=='diagnostics':
        from brave_diagnostics import open_diagnostics
        open_diagnostics(win)
    elif action=='focus':
        from brave_chat import toggle_chat_focus
        toggle_chat_focus(win)
    elif action=='fullscreen':win._toggle_fullscreen()
    elif action=='attach':win._drop_zone._browse()
    elif action=='totext':
        from brave_text_import import open_import
        open_import(win,win._drop_zone.current_files())
    elif action=='test':
        from brave_test_runner import open_runner
        open_runner(win)
    elif action=='voice':
        from brave_local_voice import open_voice
        open_voice(win)
    elif action=='benchmark':
        from brave_local_lab import open_lab
        open_lab(win)
    else:
        from brave_ai_studio import open_studio
        key='screen' if action=='warmup' else action
        page=open_studio(win,key).pages[key]
        if action=='warmup':page.warmup()
        elif body and hasattr(page,'question'):page.question.setText(body)
    return True


def prepare_send(win,text):
    """Return text to send, or None when an action/error consumes this click."""
    try:command,body,instruction=parse(text)
    except ValueError as error:win._log.append_log('ERR: '+t(str(error)));return None
    if command is None:return text
    if command.template and not win._capabilities.policy['permissions']['files']:
        win._log.append_log('ERR: '+t('Fayllarga ruxsat o‘chiq.'));return None
    action=command.action
    if action:
        draft=win._input.text()
        if draft.strip()==text:win._input.clear()
        try:
            if run_action(win,action,body) is False:
                if not win._input.text():win._input.setText(draft)
            else:command_store.used(command.name)
        except (ValueError,OSError) as error:
            if not win._input.text():win._input.setText(draft)
            win._log.append_log('ERR: '+t(str(error)))
        return None
    if not body and not command.template:
        if command.name in ('translate','summarize','explain','rewrite'):
            from brave_text_actions import open_text_actions
            dialog=open_text_actions(win,'')
            # Existing dialog actions use these stable keys.
            key={'summarize':'summary','translate':'translate','explain':'explain','rewrite':'rewrite'}[command.name]
            index=dialog.action.findData(key)
            if index>=0:dialog.action.setCurrentIndex(index)
            if command.name=='translate':
                parts=text.split(None,2)
                if len(parts)>1:
                    index=dialog.target.findData(parts[1].lower())
                    if index>=0:dialog.target.setCurrentIndex(index)
            win._input.clear()
        else:win._log.append_log('SYS: '+t('Buyruqdan keyin savol yoki topshiriq yozing.'))
        return None
    if body=='@last':
        answer=win._features.store.last_answer(win._features.chat_id)
        if not answer:win._log.append_log('ERR: '+t('Bu suhbatda tugallangan javob yo‘q.'));return None
        body=answer;text=text[:text.rfind('@last')]+answer
    if command.name=='vision' and hasattr(win,'_image_mode'):
        win._image_mode.setCurrentIndex(win._image_mode.findData('vision'))
    if win._active_provider=='ollama':return text
    if command.template and (command.model or command.profile):
        win._log.append_log('ERR: '+t('Shaxsiy model/profil uchun Ollama rejimini tanlang.'));return None
    if command.name in ('fast','think'):
        win._log.append_log('SYS: '+t('Fast/Think model rejimlari uchun Ollama’ni tanlang.'));return None
    from core.custom_commands import render
    try:return instruction+'\n\n'+render(command,body)
    except ValueError as error:win._log.append_log('ERR: '+t(str(error)));return None
