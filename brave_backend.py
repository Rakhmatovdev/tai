"""Backend lifecycle: close the old runtime completely before starting another."""
import asyncio
import threading
from PyQt6.QtCore import QObject,QTimer,pyqtSignal
from PyQt6.QtWidgets import QApplication
from brave_i18n import translate as t


CALLBACKS=('on_text_command','can_send_text','can_change_chat','on_chat_change','on_interrupt',
           'get_diagnostics','on_access_change','is_task_cancelled','on_remote_clicked',
           'on_voice_change','on_audio_device_change','get_plugins','get_plugin_settings',
           'on_wake_toggle','on_wake_manual','wake_get_state','on_push_to_talk','ptt_hold','request_say')


class GuardedUI:
    def __init__(self,ui,connection_lost=None,connection_restored=None):
        object.__setattr__(self,'target',ui);object.__setattr__(self,'active',True)
        object.__setattr__(self,'connection_lost',connection_lost)
        object.__setattr__(self,'connection_restored',connection_restored)
    def notify_connection_lost(self):
        if self.active and self.connection_lost:self.connection_lost()
    def notify_connection_restored(self):
        if self.active and self.connection_restored:self.connection_restored()
    def __getattr__(self,name):
        value=getattr(self.target,name)
        if callable(value):
            return lambda *args,**kwargs:value(*args,**kwargs) if self.active else None
        return value
    def __setattr__(self,name,value):
        if name=='active':object.__setattr__(self,name,value)
        elif self.active:
            if callable(value):
                callback=value
                value=lambda *args,**kwargs:callback(*args,**kwargs) if self.active else None
            setattr(self.target,name,value)


class BackendManager(QObject):
    stopped=pyqtSignal(int,str)
    started=pyqtSignal(int)
    def __init__(self,ui,factory):
        super().__init__(ui._win);self.ui=ui;self.win=ui._win;self.factory=factory
        self.engine=None;self.loop=None;self.task=None;self.proxy=None;self.thread=None
        self.busy=False;self.closed=False;self.revision=0;self.pending=None
        self.stopped.connect(self.did_stop);self.started.connect(self.did_start)
        from brave_connectivity import OfflineFallback
        self.connectivity=OfflineFallback(self)
        QApplication.instance().aboutToQuit.connect(self.shutdown)

    def can_switch(self):
        return not self.busy and not self.closed and not (
            self.win.can_change_chat and not self.win.can_change_chat())

    def switch(self,selected,refresh=False,*,interrupt=False):
        if self.closed:return False
        if selected==getattr(self.win,'_active_provider',None) and not refresh and self.win._runtime_started:
            return True
        if not interrupt and not self.can_switch():return False
        self.busy=True;self.pending=selected
        if getattr(self.win,'_local_voice',None):self.win._local_voice.cancel()
        if self.proxy:self.proxy.active=False
        if getattr(self.win,'_local_chat',None):
            self.win._local_chat.shutdown();self.win._local_chat.deleteLater();self.win._local_chat=None
        self.win._apply_ptt_shortcut(False)
        for name in CALLBACKS:setattr(self.win,name,None)
        self.win.can_send_text=lambda:False;self.win.can_change_chat=lambda:False
        self.win._apply_state('CONNECTING')
        if self.thread and self.thread.is_alive():
            self.request_stop()
        else:self.activate(selected)
        return True

    def request_stop(self):
        loop,task=self.loop,self.task
        if loop and task:
            try:loop.call_soon_threadsafe(task.cancel)
            except RuntimeError:pass

    def activate(self,selected):
        if self.closed:return
        self.pending=None
        self.revision+=1;revision=self.revision
        self.win._runtime_started=True;self.win._active_provider=selected
        from brave_chat import refresh_image_mode
        refresh_image_mode(self.win)
        self.connectivity.provider_changed(selected)
        self.win.hud._tmr.setInterval(33)
        self.win._reply_mode.setEnabled(selected=='gemini')
        self.win._mute_btn.setEnabled(selected=='gemini')
        if selected=='ollama':
            from brave_local_chat import LocalChat
            self.win._local_chat=LocalChat(self.win)
            self.win._local_chat.change_chat(self.win._features.store.messages(self.win._features.chat_id))
            self.busy=False;self.pending=None
        else:
            from memory.config_manager import load_api_keys
            text_only=load_api_keys().get('reply_mode')=='text'
            self.win._text_only=text_only
            self.win._reply_mode.blockSignals(True)
            self.win._reply_mode.setCurrentIndex(self.win._reply_mode.findData('text' if text_only else 'voice'))
            self.win._reply_mode.blockSignals(False)
            self.win._log.append_log('SYS: '+t('Gemini rejimi ochilmoqda. Lokal suhbat tarixi avtomatik yuborilmaydi.'))
            self.proxy=GuardedUI(self.ui,
                lambda:self.connectivity.cloud_failed.emit(revision),
                lambda:self.connectivity.cloud_restored.emit(revision));proxy=self.proxy
            def work():
                error=''
                async def run():
                    self.loop=asyncio.get_running_loop()
                    self.engine=self.factory(proxy)
                    if self.closed or not proxy.active:
                        if hasattr(self.engine,'stop_hooks'):self.engine.stop_hooks()
                        return
                    self.task=asyncio.create_task(self.engine.run())
                    self.started.emit(revision)
                    try:await self.task
                    except asyncio.CancelledError:pass
                    finally:
                        if hasattr(self.engine,'stop_hooks'):self.engine.stop_hooks()
                try:asyncio.run(run())
                except Exception as exc:
                    from core.connectivity import connection_failure
                    if connection_failure(exc):proxy.notify_connection_lost()
                    error='Gemini rejimini ochib bo‘lmadi. Ulanish va API kalitini tekshiring.'
                finally:
                    self.loop=None;self.task=None;self.engine=None
                    try:self.stopped.emit(revision,error)
                    except RuntimeError:pass
            self.thread=threading.Thread(target=work,daemon=True,name='brave-gemini-live');self.thread.start()
        self.win._refresh_wake_btns();self.win._refresh_talk_btns()

    def did_start(self,revision):
        if (revision==self.revision and not self.closed and self.pending is None
                and self.proxy and self.proxy.active):
            self.busy=False;self.pending=None

    def did_stop(self,revision,error):
        if self.closed or revision!=self.revision:return
        if self.proxy:self.proxy.active=False
        self.thread=None
        if self.pending:self.activate(self.pending)
        else:
            self.busy=False
            self.win.can_change_chat=lambda:True
            self.win.can_send_text=lambda:False
            if error:self.win._log.append_log('ERR: '+t(error))

    def shutdown(self):
        self.closed=True
        self.connectivity.shutdown()
        if self.proxy:self.proxy.active=False
        if getattr(self.win,'_local_chat',None):self.win._local_chat.shutdown()
        if getattr(self.win,'_local_voice',None):self.win._local_voice.cancel()
        self.request_stop()
