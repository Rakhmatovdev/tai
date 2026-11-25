"""Explicit push-to-talk dialog with editable transcription and local playback."""
import threading
from pathlib import Path
from PyQt6.QtCore import QObject,pyqtSignal,Qt
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,QPlainTextEdit,QComboBox,QCheckBox,QFileDialog,QInputDialog,QScrollArea,QWidget
from brave_i18n import translate as t
from memory.config_manager import load_api_keys,_patch_config
from core import offline_voice,uzbek_tts


class LocalVoice(QObject):
    result=pyqtSignal(int,str,str)
    status=pyqtSignal(str)
    prepared=pyqtSignal(str,str)
    availableVoices=pyqtSignal(object)
    tts_prepared=pyqtSignal(str,str)
    partial=pyqtSignal(int,str)
    amp_signal=pyqtSignal(float)
    playback_done=pyqtSignal()

    def __init__(self,win):
        super().__init__(win);self.win=win;self.revision=0;self.busy=False;self.recording=False
        self.speaking=False
        self.cancelled=threading.Event();self.stop_record=threading.Event()
        self.direct_chat=None
        self.result.connect(self.completed)
        self.status.connect(self.show_chat_status)
        self.amp_signal.connect(self.update_amp)
        self.playback_done.connect(self.on_playback_done)

    def update_amp(self,val):
        try:
            self.win.hud.amp=float(val)
        except Exception:
            pass

    def can_listen_continuously(self):
        if getattr(self.win,'_meeting_recording',False):return False
        if self.win._active_provider!='ollama':return False
        from memory.config_manager import get_push_to_talk_enabled
        if get_push_to_talk_enabled():return False
        if getattr(self.win,'_text_only',False):return False
        if getattr(self.win,'_muted',False):return False
        if hasattr(self.win,'_capabilities') and not self.win._capabilities.policy['permissions']['microphone']:return False
        runtime=getattr(self.win,'_local_chat',None)
        if not runtime or runtime.closed or runtime.busy:return False
        return True

    def on_playback_done(self):
        self.speaking=False
        self.update_amp(0.0)
        if self.win._active_provider!='ollama':return
        self.refresh_controls()
        if self.can_listen_continuously():
            self.win._apply_state('LISTENING')
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(200, lambda: self.start_listening() if self.can_listen_continuously() else None)
        else:
            self.win._apply_state('MUTED' if self.win._muted else 'LISTENING')

    def start_listening(self):
        if not self.can_listen_continuously() or self.busy or self.speaking:return
        cfg=load_api_keys()
        model_path=cfg.get('local_stt_path',str(offline_voice.model_directory()))
        language=cfg.get('local_stt_language','auto')
        self.record(model_path,language,auto_stop=True,chat_id=self.win._features.chat_id)

    def show_chat_status(self,text):
        if text=='Lokal ovozni ijro qilib bo‘lmadi.':
            self.win._log.append_log('ERR: '+t(text))
            return
        if self.direct_chat is not None:
            if text=='Nutq lokal tanilmoqda…':
                self.recording=False
                self.refresh_controls()
            self.win._log.append_log('SYS: '+t(text))

    def refresh_controls(self):
        self.win._style_mute_btn()
        self.win._refresh_talk_btns()
        self.win.hud.update()

    def toggle_chat(self):
        """Toggle listening or mute in offline mode."""
        if self.speaking:
            self.cancel()
            return
        if self.busy:
            if self.recording:self.stop_record.set()
            else:self.cancel()
            return
        if self.win._input.text().strip() or self.win._drop_zone.current_files():
            self.win._log.append_log('SYS: '+t('Avval chatdagi qoralamani yuboring yoki tozalang.'))
            return
        cfg=load_api_keys()
        self.record(cfg.get('local_stt_path',str(offline_voice.model_directory())),
                    cfg.get('local_stt_language','auto'),auto_stop=True,
                    chat_id=self.win._features.chat_id)

    def record(self,path,language,live=False,auto_stop=False,*,chat_id=None,allow_any_provider=False):
        if getattr(self.win,'_meeting_recording',False):return
        if self.busy or self.speaking:return
        self.direct_chat=chat_id
        runtime=getattr(self.win,'_local_chat',None)
        if not allow_any_provider and (self.win._active_provider!='ollama' or not runtime or runtime.busy):
            if chat_id is None:self.status.emit('Avval Ollama rejimini tanlang va joriy javobni tugating.')
            return
        if not self.win._capabilities.policy['permissions']['microphone']:
            if chat_id is None:self.status.emit('Mikrofon ruxsati o‘chiq.')
            return
        resolved_path=Path(path).expanduser().resolve()
        if not (resolved_path/'model.bin').is_file():
            auto_dir=offline_voice.model_directory()
            if (auto_dir/'model.bin').is_file():
                resolved_path=auto_dir
            else:
                if chat_id is None:self.status.emit('Avval offline ovoz modelini tayyorlang yoki model papkasini tanlang.')
                return
        self.cancel(keep_state=True)
        self.direct_chat=chat_id
        self.busy=True;self.recording=True;self.revision+=1;revision=self.revision
        self.cancelled=threading.Event();cancelled=self.cancelled
        self.stop_record=threading.Event();stop=self.stop_record
        if chat_id is not None:
            self.win._apply_state('LISTENING')
        else:
            self.status.emit('Yozilmoqda… To‘xtatishni bosing. Eng ko‘pi 30 soniya.')
        self.refresh_controls()
        preview_busy=threading.Event()
        def preview(audio):
            if preview_busy.is_set() or cancelled.is_set():return
            preview_busy.set()
            def recognize():
                try:
                    text=offline_voice.transcribe(audio,resolved_path,language,cancelled)
                    if not cancelled.is_set():self.partial.emit(revision,text)
                except Exception:pass
                finally:preview_busy.clear()
            threading.Thread(target=recognize,daemon=True,name='brave-stt-preview').start()
        def on_mic_amp(amp):
            if not cancelled.is_set():
                try:self.amp_signal.emit(amp)
                except Exception:pass
        def work():
            text,error='',''
            try:
                capture_options={'preview':preview if live else None,'auto_stop':auto_stop,'on_amp':on_mic_amp,'silence_limit':1.1} if live or auto_stop else {'on_amp':on_mic_amp}
                audio=offline_voice.capture(stop,cancelled,lambda:(not self.speaking and self.win._capabilities.policy['permissions']['microphone']),**capture_options)
                if not cancelled.is_set() and audio is not None and len(audio):
                    if chat_id is not None:
                        try:self.win._apply_state('THINKING')
                        except Exception:pass
                    else:
                        self.status.emit('Nutq lokal tanilmoqda…')
                    text=offline_voice.transcribe(audio,resolved_path,language,cancelled)
            except Exception:
                error='Ovoz tanilmadi. Model, mikrofon va kutubxonalarni tekshiring.'
            try:self.result.emit(revision,text,error)
            except RuntimeError:pass
        threading.Thread(target=work,daemon=True,name='brave-local-stt').start()

    def completed(self,revision,text,error):
        if revision!=self.revision:return
        chat_id=self.direct_chat
        self.busy=False;self.recording=False
        self.refresh_controls()
        self.update_amp(0.0)
        self.direct_chat=None
        if chat_id is None:
            self.status.emit(error or (('Nutq tayyor. Tekshiring va Yuborishni bosing.') if text else 'Nutq topilmadi. Qayta urinib ko‘ring.'))
            return
        if self.cancelled.is_set() or self.win._active_provider!='ollama' or self.win._features.chat_id!=chat_id or not self.win._capabilities.policy['permissions']['microphone']:
            return
        if not text.strip():
            # Sukut yoki bo'sh ovoz bo'lsa, uzluksiz suhbat rejimida darhol yana tinglashga qaytamiz
            if self.can_listen_continuously():
                self.win._apply_state('LISTENING')
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(100, lambda: self.start_listening() if self.can_listen_continuously() else None)
            return
        # Matn tanildi
        if self.win._input.text().strip() or self.win._drop_zone.current_files():
            self.win._log.append_log('SYS: '+t('Nutq yuborilmadi; chatdagi qoralama saqlandi.')+' '+text)
            return
        runtime=getattr(self.win,'_local_chat',None)
        if not runtime or runtime.closed or runtime.busy:return
        self.status.emit('Nutq lokal modelga yuborilmoqda.')
        self.win._input.setText(text)
        self.win._send()

    def cancel(self,keep_state=False):
        self.revision+=1;self.cancelled.set();self.stop_record.set();self.busy=False;self.recording=False
        self.direct_chat=None
        self.update_amp(0.0)
        if not keep_state:
            self.refresh_controls()

    def say(self,text,*,voice_id=None,force=False,style=None):
        """Javobni ovozda o‘qiydi. O‘zbek TTS yoki Windows tizim ovozidan foydalanadi."""
        cfg=load_api_keys()
        if not force and self.win._active_provider!='ollama':return
        selected_voice=cfg.get('local_voice_id','') if voice_id is None else voice_id
        has_uzbek=uzbek_tts.ready()
        if not force and not cfg.get('local_voice_reply') and not has_uzbek:
            # Agar ovoz chiqarilmasa, to'g'ridan to'g'ri tinglashga qaytish
            self.on_playback_done()
            return
        self.cancel(keep_state=True)
        self.speaking=True
        self.cancelled=threading.Event();cancelled=self.cancelled
        if has_uzbek and not selected_voice:
            selected_voice=uzbek_tts.VOICE_ID
        try:
            self.win._apply_state('SPEAKING')
        except Exception:
            pass
        self.refresh_controls()
        def on_speak_amp(amp):
            if not cancelled.is_set():
                try:self.amp_signal.emit(amp)
                except Exception:pass
        def work():
            try:
                if style is not None:
                    offline_voice.speak(text,cancelled,selected_voice,on_speak_amp,style=style)
                else:
                    offline_voice.speak(text,cancelled,selected_voice,on_speak_amp)
            except Exception:
                try:self.status.emit('Lokal ovozni ijro qilib bo‘lmadi.')
                except RuntimeError:pass
            finally:
                self.speaking=False
                try:self.playback_done.emit()
                except RuntimeError:pass
        threading.Thread(target=work,daemon=True,name='brave-local-tts').start()


class VoiceDialog(QDialog):
    def __init__(self,win):
        super().__init__(win);self.win=win
        from brave_control_center import style_dialog
        style=style_dialog(self,'Offline ovoz');self.resize(680,720)
        if not getattr(win,'_local_voice',None):win._local_voice=LocalVoice(win)
        self.voice=win._local_voice;cfg=load_api_keys();outer=QVBoxLayout(self)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        from brave_ui import colors
        host=QWidget();host.setObjectName('BraveVoiceBody');host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True)
        host.setStyleSheet(f'QWidget#BraveVoiceBody {{background:{colors().PANEL};}}')
        scroll.setStyleSheet(f'QScrollArea {{background:{colors().PANEL};border:none;}}')
        scroll.viewport().setStyleSheet(f'background:{colors().PANEL};')
        layout=QVBoxLayout(host);scroll.setWidget(host);outer.addWidget(scroll)
        note=QLabel(t('Mikrofon faqat Yozishni bosganda ochiladi. Nutq va javob shu qurilmada ishlanadi.'));note.setWordWrap(True);layout.addWidget(note)
        row=QHBoxLayout();layout.addLayout(row)
        self.path=QLineEdit(cfg.get('local_stt_path',str(offline_voice.model_directory())));row.addWidget(self.path,1)
        browse=QPushButton(t('Papka'));row.addWidget(browse)
        browse.clicked.connect(lambda:self.choose_path())
        self.prepare=QPushButton(t('Nutq modelini yuklash'));self.prepare.clicked.connect(self.prepare_model)
        self.prepare.setEnabled(not getattr(self.voice,'preparing',False));layout.addWidget(self.prepare)
        self.size=QComboBox()
        for size in ('tiny','base','small','medium'):self.size.addItem(size,size)
        self.size.setCurrentIndex(max(0,self.size.findData(cfg.get('local_stt_size','base'))));layout.addWidget(self.size)
        self.size.currentIndexChanged.connect(lambda:self.path.setText(str(offline_voice.model_directory(self.size.currentData()))))
        self.live=QCheckBox(t('Yozish vaqtida qisman transkript'));self.live.setChecked(bool(cfg.get('local_stt_preview')));layout.addWidget(self.live)
        self.auto_stop=QCheckBox(t('Sukutdan keyin yozishni to‘xtatish'));self.auto_stop.setChecked(bool(cfg.get('local_stt_auto_stop')));layout.addWidget(self.auto_stop)
        self.language=QComboBox()
        for title,value in [('Avtomatik','auto'),('O‘zbekcha','uz'),('English','en'),('Русский','ru')]:self.language.addItem(t(title),value)
        self.language.setCurrentIndex(max(0,self.language.findData(cfg.get('local_stt_language','auto'))));layout.addWidget(self.language)
        layout.addWidget(QLabel(t('Javob ovozi')))
        self.tts=QComboBox();self.tts.addItem(t(uzbek_tts.VOICE_NAME),uzbek_tts.VOICE_ID)
        self.tts.addItem(t('Tizim ovozi'),'');layout.addWidget(self.tts)
        voice_actions=QHBoxLayout();layout.addLayout(voice_actions)
        self.prepare_tts=QPushButton(t('O‘zbekcha ovozni yuklash'))
        self.prepare_tts.setEnabled(not getattr(self.voice,'tts_preparing',False))
        self.prepare_tts.clicked.connect(self.prepare_tts_model)
        self.test_tts=QPushButton(t('Ovozni eshitish'));self.test_tts.clicked.connect(self.preview_voice)
        self.dialect_studio_btn=QPushButton(t('🎙️ Sheva va Hissiy Ohang…'))
        self.dialect_studio_btn.clicked.connect(lambda:__import__('brave_voice_dialect').open_voice_dialect_studio(self.win,self))
        for button in (self.prepare_tts,self.test_tts,self.dialect_studio_btn):
            button.setStyleSheet(style);voice_actions.addWidget(button)
        self.reply=QCheckBox(t('Javoblarni lokal ovozda o‘qish'));self.reply.setChecked(bool(cfg.get('local_voice_reply')));layout.addWidget(self.reply)
        self.text=QPlainTextEdit();self.text.setPlaceholderText(t('Tanilgan nutqni shu yerda tuzatishingiz mumkin.'));layout.addWidget(self.text)
        self.status=QLabel(t('O‘zbekcha AI ovozi bir marta yuklanadi, keyin internetsiz ishlaydi.'));self.status.setWordWrap(True);layout.addWidget(self.status)
        actions=QHBoxLayout();layout.addLayout(actions)
        self.record=QPushButton(t('Yozish'));self.record.clicked.connect(self.toggle_record)
        stop=QPushButton(t('Bekor qilish'));stop.clicked.connect(self.stop)
        send=QPushButton(t('Yuborish'));send.clicked.connect(self.send)
        save=QPushButton(t('Saqlash'));save.clicked.connect(self.save)
        for button in (browse,self.prepare,self.record,stop,send,save):button.setStyleSheet(style)
        for button in (self.record,stop,send,save):actions.addWidget(button)
        self.voice.status.connect(self.show_status);self.voice.result.connect(self.transcribed)
        self.voice.partial.connect(self.preview_text)
        self.preview_label=QLabel();self.preview_label.setWordWrap(True);layout.addWidget(self.preview_label)
        test=QPushButton(t('Nutq sifatini tekshirish'));test.setStyleSheet(style);test.clicked.connect(self.test_audio);layout.addWidget(test)
        self.voice.prepared.connect(self.model_prepared);self.voice.availableVoices.connect(self.voices_loaded)
        self.voice.tts_prepared.connect(self.tts_model_prepared)
        self.tts_download_cancel=threading.Event()
        def enumerate_voices():
            try:rows=offline_voice.voices()
            except Exception:rows=[]
            try:self.voice.availableVoices.emit(rows)
            except RuntimeError:pass
        threading.Thread(target=enumerate_voices,daemon=True,name='brave-system-voices').start()

    def voices_loaded(self,rows):
        selected=load_api_keys().get('local_voice_id','')
        for name,key in rows:
            if self.tts.findData(key)<0:self.tts.addItem(t(name),key)
        self.tts.setCurrentIndex(max(0,self.tts.findData(selected)))

    def prepare_tts_model(self):
        if not self.win._capabilities.policy['permissions']['network']:
            self.show_status('Yuklash uchun internet ruxsatini yoqing.');return
        if getattr(self.voice,'tts_preparing',False):return
        self.voice.tts_preparing=True;self.prepare_tts.setEnabled(False)
        self.tts_download_cancel=threading.Event();cancelled=self.tts_download_cancel
        self.show_status('O‘zbekcha ovoz modeli yuklanmoqda…')
        def work():
            path,error='',''
            try:path=uzbek_tts.prepare_model(cancelled) or ''
            except Exception:error='Ovoz modeli yuklanmadi. Internetni tekshirib, qayta urinib ko‘ring.'
            self.voice.tts_preparing=False
            if not cancelled.is_set():
                try:self.voice.tts_prepared.emit(path,error)
                except RuntimeError:pass
        threading.Thread(target=work,daemon=True,name='brave-uzbek-voice-download').start()

    def tts_model_prepared(self,path,error):
        self.prepare_tts.setEnabled(True)
        if path:
            self.tts.setCurrentIndex(self.tts.findData(uzbek_tts.VOICE_ID))
            self.show_status('O‘zbekcha ovoz tayyor. Eshitib ko‘ring va Saqlashni bosing.')
        else:self.show_status(error)

    def preview_voice(self):
        if self.voice.busy:return
        key=self.tts.currentData()
        if key==uzbek_tts.VOICE_ID and not uzbek_tts.ready():
            self.show_status('Avval o‘zbekcha ovoz modelini yuklang.');return
        runtime=getattr(self.win,'_local_chat',None)
        if runtime and runtime.busy:
            self.show_status('Avval joriy javob tugashini kuting.');return
        self.voice.say('Assalomu alaykum! Men sizning o‘zbekcha ovozli yordamchingizman.',voice_id=key,force=True)

    def choose_path(self):
        path=QFileDialog.getExistingDirectory(self,t('Nutq modeli papkasi'),self.path.text())
        if path:self.path.setText(path)

    def show_status(self,text):self.status.setText(t(text))

    def toggle_record(self):
        if self.voice.recording:
            self.voice.stop_record.set();self.record.setText(t('Yozish'));return
        self.voice.record(self.path.text(),self.language.currentData(),self.live.isChecked(),self.auto_stop.isChecked())
        if self.voice.recording:self.record.setText(t('To‘xtatish'))

    def transcribed(self,revision,text,error):
        if revision!=self.voice.revision:return
        self.record.setText(t('Yozish'))
        if text:self.text.setPlainText(text)

    def preview_text(self,revision,text):
        if revision==self.voice.revision and self.voice.recording:self.preview_label.setText(text[-300:])

    def test_audio(self):
        if self.voice.busy:return
        if not self.win._capabilities.policy['permissions']['files']:
            self.show_status('Fayllarga ruxsat o‘chiq.');return
        path,_=QFileDialog.getOpenFileName(self,t('Test audioni tanlang'),'','WAV (*.wav)')
        if not path:return
        expected,ok=QInputDialog.getMultiLineText(self,t('Kutilgan transkript'),t('Audiodagi aniq matn'))
        if not ok or not expected.strip():return
        from brave_local_jobs import Worker
        model=self.path.text();language=self.language.currentData();policy=self.win._capabilities.policy
        def operation(cancel,progress):
            if not policy['permissions']['files']:raise ValueError('Fayllarga ruxsat o‘chiq.')
            import numpy as np
            import soundfile as sf
            with sf.SoundFile(path) as source:
                if source.frames/source.samplerate>30:raise ValueError('Test audio 30 soniyadan oshmasin.')
                rate=source.samplerate;audio=source.read(dtype='float32',always_2d=True).mean(axis=1)
            if rate!=16000:audio=np.interp(np.arange(int(len(audio)*16000/rate))*rate/16000,np.arange(len(audio)),audio).astype('float32')
            text=offline_voice.transcribe(audio,model,language,cancel)
            return text,offline_voice.word_error_rate(expected,text)
        self.test_job=Worker(self.win,operation)
        def done(result,error):
            if self.test_job.cancelled.is_set():return
            if result:self.text.setPlainText(result[0]);self.status.setText(f'WER: {result[1]*100:.1f}% · '+t('Past qiymat yaxshiroq. Bu faqat tanlangan audio natijasi.'))
            elif error:self.show_status(error)
        self.test_job.completed.connect(done);self.test_job.start()

    def stop(self):
        self.voice.cancel();self.record.setText(t('Yozish'))
        self.tts_download_cancel.set()
        self.prepare_tts.setEnabled(True)

    def save(self):
        _patch_config(local_stt_path=self.path.text(),local_stt_language=self.language.currentData(),
                      local_voice_reply=self.reply.isChecked(),local_voice_id=self.tts.currentData() or '',
                      local_stt_size=self.size.currentData(),local_stt_preview=self.live.isChecked(),local_stt_auto_stop=self.auto_stop.isChecked())
        if self.win._active_provider=='ollama':
            self.win._reply_mode.setCurrentIndex(self.win._reply_mode.findData('voice' if self.reply.isChecked() else 'text'))
        self.status.setText(t('Sozlamalar saqlandi.'))

    def send(self):
        if self.voice.busy or self.win._active_provider!='ollama':return
        runtime=getattr(self.win,'_local_chat',None)
        if not runtime or runtime.busy:return
        text=self.text.toPlainText().strip()
        if not text:return
        if self.win._input.text().strip():
            self.status.setText(t('Avval chatdagi qoralamani yuboring yoki tozalang.'));return
        self.save();self.win._input.setText(text);self.win._send();self.accept()

    def prepare_model(self):
        if not self.win._capabilities.policy['permissions']['network']:
            self.status.setText(t('Yuklash uchun internet ruxsatini yoqing.'));return
        if getattr(self.voice,'preparing',False):return
        self.voice.preparing=True;self.prepare.setEnabled(False)
        size=self.size.currentData()
        self.status.setText(t('Nutq modeli yuklanmoqda. Bu bir marta internet talab qiladi.'))
        def work():
            path,error='',''
            try:path=offline_voice.prepare_model(size)
            except Exception:error='Nutq modeli yuklanmadi. Internet va faster-whisper kutubxonasini tekshiring.'
            self.voice.preparing=False
            try:self.voice.prepared.emit(path,error)
            except RuntimeError:pass
        threading.Thread(target=work,daemon=True,name='brave-stt-download').start()

    def model_prepared(self,path,error):
        self.prepare.setEnabled(True)
        if path:self.path.setText(path)
        self.status.setText(t(error or 'Nutq modeli tayyor. Offline yozishingiz mumkin.'))

    def done(self,result):
        self.stop()
        if getattr(self,'test_job',None):self.test_job.cancel()
        for signal,callback in [(self.voice.status,self.show_status),(self.voice.result,self.transcribed),
                                (self.voice.prepared,self.model_prepared),(self.voice.availableVoices,self.voices_loaded),
                                (self.voice.tts_prepared,self.tts_model_prepared)]:
            try:signal.disconnect(callback)
            except (TypeError,RuntimeError):pass
        try:self.voice.partial.disconnect(self.preview_text)
        except (TypeError,RuntimeError):pass
        super().done(result)


def open_voice(win):
    if win._active_provider!='ollama':
        win._log.append_log('SYS: '+t('Offline ovoz uchun Sozlamalarda Ollama rejimini tanlang.'));return
    VoiceDialog(win).exec()
