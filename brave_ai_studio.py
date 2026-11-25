"""Native entry points for model advice, offline tools, meetings, review and speech terms."""
from dataclasses import replace
import json
from pathlib import Path
import threading

from PyQt6.QtCore import Qt,QTimer
from PyQt6.QtWidgets import (QCheckBox,QComboBox,QDialog,QFileDialog,QHBoxLayout,QLabel,
    QLineEdit,QPlainTextEdit,QPushButton,QScrollArea,QFrame,QTabWidget,QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget)

from brave_i18n import translate as t
from brave_local_jobs import Worker
from brave_ai_pipeline import AnalysisJob
from core.ollama_chat import Settings, provider
from core import offline_desktop, speech_dictionary


class TaskPage(QWidget):
    def __init__(self, studio):
        super().__init__(studio)
        self.studio=studio; self.win=studio.win
        self.layout=QVBoxLayout(self); self.layout.setSpacing(10)
        self.status=QLabel(''); self.status.setWordWrap(True); self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.worker=self.analysis=None; self.closed=False; self.revision=0; self.busy=False
        self.fields=[]; self.buttons=[]; self.answer=''; self.output_buttons=[]

    def note(self,text):
        label=QLabel(t(text)); label.setWordWrap(True); self.layout.addWidget(label)

    def row(self):
        row=QHBoxLayout(); self.layout.addLayout(row); return row

    def button(self,title,callback,row=None,busy=True):
        button=QPushButton(t(title)); button.setStyleSheet(self.studio.button_style)
        button.clicked.connect(callback); (row if row is not None else self.layout).addWidget(button)
        if busy:self.buttons.append(button)
        return button

    def footer(self):
        if hasattr(self,'output_row'):
            self.button('Bekor qilish',self.cancel,self.output_row,busy=False)
            self.layout.addWidget(self.status)
        else:
            row=self.row();row.addWidget(self.status,1)
            self.button('Bekor qilish',self.cancel,row,busy=False)

    def set_busy(self,value):
        self.busy=value
        for widget in self.buttons+self.fields:widget.setEnabled(not value)
        for button in self.output_buttons:button.setEnabled(not value and bool(self.answer))

    def work(self,operation,completed,progress=None):
        if self.busy or self.closed:return False
        self.revision+=1; revision=self.revision; self.set_busy(True)
        worker=Worker(self,operation); self.worker=worker
        def ready(result,error):
            if self.closed or revision!=self.revision:return
            self.worker=None; self.set_busy(False)
            if error or result is None:self.status.setText(t(error or 'Bekor qilindi.'))
            else:completed(result)
        worker.completed.connect(ready)
        def update(value):
            if not self.closed and revision==self.revision:
                if progress:progress(value)
                else:self.status.setText(t(value))
        worker.progress.connect(update); worker.start(); return True

    def add_output(self):
        self.result=QPlainTextEdit(); self.result.setReadOnly(True); self.layout.addWidget(self.result,1)
        row=self.row()
        self.output_row=row
        self.output_buttons=[self.button('Chatga qo‘yish',self.insert,row,busy=False),
                             self.button('Eksport',self.export,row,busy=False)]
        self.set_busy(False)

    def invalidate_output(self):
        self.answer='';self.result.clear();self.set_busy(self.busy)

    def analyze(self,sections,instruction,permissions=('files',),*,on_result=None,**options):
        if self.closed or self.busy:return
        if getattr(self.win,'_meeting_recording',False):
            self.status.setText(t('Avval jonli uchrashuv yozuvini tugating. Matningiz saqlandi.'));return
        if self.win._active_provider!='ollama':self.status.setText(t('Avval Ollama rejimini tanlang.'));return
        def allowed():
            return (not self.closed and self.win._active_provider=='ollama' and
                    all(self.win._capabilities.policy['permissions'].get(cap,False) for cap in permissions))
        if not allowed():self.status.setText(t('Tahlil uchun ruxsat o‘chiq yoki rejim o‘zgardi.'));return
        self.revision+=1; revision=self.revision; self.answer=''; self.result.clear(); self.set_busy(True)
        job=AnalysisJob(sections,instruction,self,authorize=allowed,**options); self.analysis=job
        job.progress.connect(lambda text:self.status.setText(t(text)))
        job.partial.connect(self.result.setPlainText)
        def done(text,error,cancelled):
            if self.analysis is job:self.analysis=None
            job.deleteLater()
            if self.closed or revision!=self.revision:return
            if error or cancelled:
                self.result.clear();self.status.setText(t(error or 'Bekor qilindi.'))
            else:
                self.answer=text; self.result.setPlainText(text)
                self.status.setText(t('Natija uzunlik chegarasiga yetdi. Matnni qismlarga bo‘lib qayta ishlang.'
                    if job.metrics.get('done_reason')=='length' or job.metrics.get('intermediate_length_limits')
                    else 'Tahlil tayyor. Natijani manba bilan tekshiring.')+' · '+job.settings.model)
            self.set_busy(False)
            if on_result and not error and not cancelled:on_result(text,job.metrics)
        job.finished.connect(done); job.start()

    def insert(self):
        if self.answer:
            before=self.win._input.text()
            self.win._input.setText(before+('\n\n' if before else '')+self.answer)
            self.status.setText(t('Natija qoralamaga qo‘shildi.'))

    def export(self):
        if not self.answer:return
        path,_=QFileDialog.getSaveFileName(self,t('Eksport'),'brave-analysis.md','Markdown (*.md);;Text (*.txt)')
        if path:
            try:Path(path).write_text(self.answer,encoding='utf-8')
            except OSError:self.status.setText(t('Faylni saqlab bo‘lmadi. Boshqa joy tanlang.'))

    def cancel(self):
        self.revision+=1
        if self.worker:self.worker.cancel();self.worker=None
        if self.analysis:self.analysis.cancel();self.analysis=None;self.answer='';self.result.clear()
        self.set_busy(False);self.status.setText(t('Bekor qilindi.'))

    def shutdown(self):self.closed=True;self.cancel()


class ModelsPage(TaskPage):
    def __init__(self,studio):
        super().__init__(studio)
        from core.ai_extensions import settings as extension_settings
        prefs=extension_settings()
        self.auto_route=QCheckBox(t('Vazifaga qarab modelni avtomatik tanlash'))
        self.auto_route.setChecked(prefs['auto_route']);self.layout.addWidget(self.auto_route)
        self.remember_images=QCheckBox(t('Suhbatdagi oxirgi rasmni eslab turish (faqat shu sessiya)'))
        self.remember_images.setChecked(prefs['remember_images']);self.layout.addWidget(self.remember_images)
        row=self.row();self.button('AI sozlamalarini saqlash',self.save_extensions,row)
        self.button('Rasm kontekstini unutish',self.forget_images,row,busy=False)
        self.note('Faqat o‘rnatilgan modellar tavsiya qilinadi. Tanlov siz tasdiqlagandan keyin saqlanadi.')
        self.task=QComboBox()
        for title,key in [('Matn','text'),('Kod','code'),('Rasm','vision')]:self.task.addItem(t(title),key)
        self.layout.addWidget(self.task);self.fields.append(self.task)
        self.table=QTableWidget(0,5); self.table.setHorizontalHeaderLabels([t('Model'),t('Imkoniyatlar'),'Disk GiB',t('O‘lchangan vaqt'),t('Izoh')])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True);self.layout.addWidget(self.table,1)
        self.rows=[];row=self.row();self.button('Tavsiya olish',self.refresh,row);self.button('Modelni tanlash',self.apply,row)
        self.button('Tezlikni o‘lchash',lambda:__import__('brave_local_lab').open_lab(self.win))
        self.note('Xotira bahosi taxminiy: disk hajmi ish paytidagi RAM yoki VRAM sarfi emas.')
        self.footer()

    def save_extensions(self):
        from core.ai_extensions import save
        save(auto_route=self.auto_route.isChecked(),remember_images=self.remember_images.isChecked())
        if not self.remember_images.isChecked():self.forget_images()
        self.status.setText(t('AI sozlamasi saqlandi. Keyingi so‘rovga qo‘llanadi.'))

    def forget_images(self):
        runtime=getattr(self.win,'_local_chat',None)
        if runtime:runtime.visual_context.clear()
        self.status.setText(t('Rasm konteksti unutildi.'))

    def refresh(self):
        try:settings=Settings.read()
        except ValueError as error:self.status.setText(t(str(error)));return
        task=self.task.currentData()
        def operation(cancel,progress):
            from core.model_recommender import recommend
            from core.ollama_service import ensure_server
            if settings.autostart:ensure_server(settings.url,cancelled=cancel)
            return recommend(settings,task,cancel,progress)
        def present(rows):
            from core.model_performance import estimates,measured_order
            effective=replace(settings,profile='balanced' if settings.profile=='auto' else settings.profile)
            measurements=estimates(effective,task);rows=measured_order(rows,effective,task)
            self.rows=rows;self.table.setRowCount(len(rows))
            for i,row in enumerate(rows):
                reason=t('Xotiraga sig‘ishi taxmin qilinadi' if row['fits_estimate'] else 'Xotira talabi yuqori yoki noma’lum')
                if row['code_name']:reason+=' · '+t('Kodga yo‘naltirilgan nom')
                sample=measurements.get(row['name']);timing=f"{sample['seconds']:.2f}s · n={sample['samples']}" if sample else '—'
                for j,value in enumerate((row['name'],', '.join(row['capabilities']) or '—',f"{row['size']/2**30:.1f}",timing,reason)):
                    self.table.setItem(i,j,QTableWidgetItem(value))
            self.table.resizeColumnsToContents()
            if rows:self.table.selectRow(0)
            self.status.setText(t('Tavsiya tayyor. Modelni tanlab saqlang.' if rows else 'Mos o‘rnatilgan model topilmadi.'))
        self.work(operation,present)

    def apply(self):
        index=self.table.currentRow()
        if not 0<=index<len(self.rows):return
        if self.win.can_change_chat and not self.win.can_change_chat():
            self.status.setText(t('Avval joriy vazifa tugashini kuting.'));return
        try:replace(Settings.read(),model=self.rows[index]['name']).save(provider())
        except (ValueError,OSError) as error:self.status.setText(t(str(error)));return
        form=getattr(getattr(self.win,'_quick_drawer',None),'forms',{}).get('ai')
        if form:form.model.setEditText(self.rows[index]['name'])
        self.status.setText(t('Model keyingi lokal so‘rov uchun saqlandi.'))


class DesktopPage(TaskPage):
    def __init__(self,studio):
        super().__init__(studio)
        self.note('Offline chat dastur ochishi, tanlangan papkada fayl nomini qidirishi va tizim holatini o‘qishi mumkin.')
        cfg=offline_desktop.settings()
        self.enabled=QCheckBox(t('Chatda offline amallarni yoqish'));self.enabled.setChecked(bool(cfg.get('enabled')))
        self.layout.addWidget(self.enabled)
        self.root=QLineEdit(cfg.get('root',''));self.root.setReadOnly(True);self.layout.addWidget(self.root)
        row=self.row();self.button('Papka tanlash',self.choose,row);self.button('Saqlash',self.save,row)
        self.app=QComboBox()
        for key,title in offline_desktop.APPS.items():self.app.addItem(title,key)
        self.layout.addWidget(self.app)
        row=self.row();self.button('Dastur ochish',lambda:self.perform('open_local_app',{'app':self.app.currentData()}),row)
        self.button('Tizim holati',lambda:self.perform('local_system_status',{}),row)
        self.query=QLineEdit();self.query.setPlaceholderText(t('Fayl nomidan qidirish'));self.layout.addWidget(self.query)
        self.button('Qidirish',lambda:self.perform('find_local_files',{'query':self.query.text()}))
        self.fields += [self.enabled,self.app,self.query]
        self.add_output();self.footer()

    def choose(self):
        path=QFileDialog.getExistingDirectory(self,t('Papka tanlash'),self.root.text())
        if path:self.root.setText(path)

    def save(self):
        try:
            offline_desktop.save(self.enabled.isChecked(),self.root.text())
            if self.enabled.isChecked():
                from memory.config_manager import _patch_config
                _patch_config(local_tools_enabled=True)
                form=getattr(getattr(self.win,'_quick_drawer',None),'forms',{}).get('ai')
                if form:form.local_tools.setChecked(True)
            self.status.setText(t('Offline amallar sozlamasi saqlandi.'))
        except (ValueError,OSError) as error:self.status.setText(t(str(error)))

    def perform(self,name,args):
        if self.busy:return
        from brave_offline_actions import execute
        self.revision+=1;revision=self.revision
        self.action_cancel=threading.Event()
        self.invalidate_output()
        self.set_busy(True)
        try:
            value=execute(self.win,name,args,self.action_cancel,
                          active=lambda:not self.closed and revision==self.revision)
            if revision!=self.revision:return
            self.answer=json.dumps(value,ensure_ascii=False,indent=2);self.result.setPlainText(self.answer)
            self.status.setText(t('Amal bajarildi.'))
        except (ValueError,RuntimeError,OSError) as error:
            if revision==self.revision:self.status.setText(t(str(error)))
        finally:
            if revision==self.revision:self.set_busy(False)

    def cancel(self):
        if hasattr(self,'action_cancel'):self.action_cancel.set()
        super().cancel()


class MeetingPage(TaskPage):
    def __init__(self,studio):
        super().__init__(studio)
        self.note('Audio yozuvni lokal matnga aylantiring, keyin xulosa, qarorlar va vazifalarni ajrating. Avval offline nutq modeli o‘rnatilgan bo‘lishi kerak.')
        self.path=QLineEdit();self.path.setReadOnly(True);self.layout.addWidget(self.path)
        row=self.row();self.button('Audio tanlash',self.choose,row);self.button('Matnga aylantirish',self.transcribe,row)
        self.speech_options=QWidget();options=QVBoxLayout(self.speech_options);options.setContentsMargins(0,0,0,0)
        self.button('Til va nutq sozlamalari',lambda:self.speech_options.setVisible(not self.speech_options.isVisible()),row,busy=False)
        self.layout.addWidget(self.speech_options);self.speech_options.hide()
        language_row=QHBoxLayout();options.addLayout(language_row)
        self.language=QComboBox()
        for title,key in [('Auto','auto'),('O‘zbekcha','uz'),('English','en'),('Русский','ru')]:self.language.addItem(title,key)
        language_row.addWidget(self.language);self.fields.append(self.language)
        self.speech_quality=QComboBox()
        self.speech_quality.addItem(t('Aniqroq nutq · gap tugashini kutish'),'accurate')
        self.speech_quality.addItem(t('Tez nutq · 8 soniyalik qismlar'),'fast')
        language_row.addWidget(self.speech_quality);self.fields.append(self.speech_quality)
        self.diarize=QCheckBox(t('Gapiruvchilarni ajratish (taxminiy Speaker 1, 2…)'))
        options.addWidget(self.diarize);self.fields.append(self.diarize)
        model_row=QHBoxLayout();options.addLayout(model_row)
        self.button('Gapiruvchi modelini tayyorlash · 26.5 MB',self.prepare_speakers,model_row)
        row=self.row()
        self.button('Jonli uchrashuvni boshlash',self.start_live,row)
        self.stop_live_button=self.button('Yozuvni tugatish',self.stop_live,row,busy=False)
        self.stop_live_button.setEnabled(False);self.live_stop=None
        self.note('Jonli yozuv faqat mikrofondan olinadi. Audio saqlanmaydi. Speaker yorliqlari shaxsni aniqlamaydi; ustma-ust nutqda xato bo‘lishi mumkin.')
        self.transcript=QPlainTextEdit();self.transcript.setPlaceholderText(t('Transkriptni shu yerda tekshiring yoki matn kiriting.'))
        self.layout.addWidget(self.transcript,1);self.fields.append(self.transcript)
        self.number_review=QLabel();self.number_review.setWordWrap(True);self.number_review.setTextFormat(Qt.TextFormat.PlainText)
        self.layout.addWidget(self.number_review);self.number_review.hide()
        self.transcript.textChanged.connect(self.review_numbers)
        row=self.row();self.button('Xulosa va vazifalar',self.summarize,row);self.button('Transkriptni saqlash',self.export_transcript,row)
        self.button('Jonli vazifalarni yangilash',self.update_live_notes,row,busy=False)
        self.notes_job=None
        self.notes_status=QLabel(t('Jonli qaydlar oxirgi yangilashdagi transkriptga tegishli.'));self.notes_status.setWordWrap(True)
        self.notes_status.hide();self.layout.addWidget(self.notes_status)
        self.live_notes=QPlainTextEdit();self.live_notes.setReadOnly(True);self.live_notes.setMaximumHeight(150)
        self.live_notes.hide();self.layout.addWidget(self.live_notes)
        corrections=self.row()
        self.old_term=QLineEdit();self.old_term.setPlaceholderText(t('Noto‘g‘ri ism yoki raqam'))
        self.new_term=QLineEdit();self.new_term.setPlaceholderText(t('To‘g‘ri shakli'))
        corrections.addWidget(self.old_term);corrections.addWidget(self.new_term)
        self.button('Transkriptda tuzatish',self.correct_transcript,corrections)
        self.add_output();self.footer()
        self.transcript.textChanged.connect(self.invalidate_output)
        self.session_id=None;self.loading_draft=False
        self.autosave=QTimer(self);self.autosave.setSingleShot(True);self.autosave.setInterval(500)
        self.autosave.timeout.connect(self.save_draft)
        for signal in (self.transcript.textChanged,self.live_notes.textChanged,self.result.textChanged):
            signal.connect(self.draft_changed)
        self.language.currentIndexChanged.connect(self.draft_changed);self.diarize.toggled.connect(self.draft_changed)
        self.draft_box=QWidget();draft_layout=QVBoxLayout(self.draft_box);draft_layout.setContentsMargins(0,0,0,0)
        self.session_picker=QComboBox();draft_layout.addWidget(self.session_picker)
        controls=QHBoxLayout();draft_layout.addLayout(controls)
        self.button('Uchrashuvni tiklash',self.restore_draft,controls)
        self.button('Yangi uchrashuv',self.new_meeting,controls)
        self.button('Saqlangan uchrashuvni o‘chirish',self.delete_draft,controls)
        toggle=QPushButton(t('Saqlangan uchrashuvlar'));toggle.setStyleSheet(self.studio.button_style)
        toggle.clicked.connect(lambda:self.draft_box.setVisible(not self.draft_box.isVisible()))
        self.layout.insertWidget(0,toggle);self.layout.insertWidget(1,self.draft_box);self.draft_box.hide()
        self.save_status=QLabel(t('Transkript va qaydlar shu qurilmada avtomatik saqlanadi.'))
        self.save_status.setWordWrap(True);self.layout.insertWidget(2,self.save_status)
        self.reload_sessions()
        if self.session_picker.count():self.restore_draft()

    def draft_changed(self,*args):
        if not self.loading_draft and not self.closed:self.autosave.start()

    def review_numbers(self):
        from core.meeting_review import numbers
        values=numbers(self.transcript.toPlainText())
        self.number_review.setText(t('Raqamlarni audio bilan tekshiring')+': '+', '.join(values))
        self.number_review.setVisible(bool(values))

    def reload_sessions(self):
        from core.meeting_sessions import sessions
        from datetime import datetime
        self.session_picker.clear()
        for row in reversed(sessions()):
            title=datetime.fromtimestamp(row.get('updated',0)).strftime('%Y-%m-%d %H:%M')
            self.session_picker.addItem(title+' · '+row['transcript'].split('\n')[0][:45],row['id'])
        index=self.session_picker.findData(self.session_id)
        if index>=0:self.session_picker.setCurrentIndex(index)

    def save_draft(self):
        if self.loading_draft:return
        text=self.transcript.toPlainText()
        if not text.strip() and not self.session_id:return
        if not self.win._capabilities.policy['permissions']['files']:
            self.save_status.setText(t('Fayl ruxsati o‘chiq: qoralama saqlanmadi.'));return
        from core.meeting_sessions import save
        try:
            self.session_id=save(self.session_id,text,language=self.language.currentData(),diarize=self.diarize.isChecked(),
                notes=self.live_notes.toPlainText(),answer=self.answer,path=self.path.text(),recording=self.live_stop is not None)
            self.save_status.setText(t('Uchrashuv qoralamasi shu qurilmada saqlandi.'));self.reload_sessions()
        except (OSError,ValueError) as error:self.save_status.setText(t(str(error)))

    def restore_draft(self):
        if self.busy or not self.win._capabilities.policy['permissions']['files']:return
        from core.meeting_sessions import sessions
        selected=self.session_picker.currentData()
        # Save current work before restoring a different draft.
        self.autosave.stop()
        if self.session_id and self.session_id!=selected:self.save_draft()
        row=next((row for row in sessions() if row['id']==selected),None)
        if not row:return
        self.loading_draft=True
        try:
            self.session_id=row['id'];self.path.setText(row.get('path',''))
            self.language.setCurrentIndex(max(0,self.language.findData(row.get('language','auto'))))
            self.diarize.setChecked(bool(row.get('diarize')));self.transcript.setPlainText(row['transcript'])
            self.live_notes.setPlainText(row.get('notes',''));self.live_notes.setVisible(bool(row.get('notes')))
            self.notes_status.setVisible(bool(row.get('notes')))
            self.answer=row.get('answer','');self.result.setPlainText(self.answer);self.set_busy(False)
            self.save_status.setText(t('Qoralama tiklandi. Mikrofon avtomatik yoqilmaydi.'))
        finally:self.loading_draft=False

    def new_meeting(self):
        if self.busy:return
        self.save_draft();self.autosave.stop();self.loading_draft=True
        self.session_id=None;self.path.clear();self.transcript.clear();self.live_notes.clear();self.invalidate_output()
        self.loading_draft=False

    def delete_draft(self):
        if self.busy or not self.win._capabilities.policy['permissions']['files']:return
        from PyQt6.QtWidgets import QMessageBox
        identity=self.session_picker.currentData()
        if not identity:return
        if QMessageBox.question(self,t('O‘chirish'),t('Tanlangan uchrashuv qoralamasi o‘chirilsinmi?'))!=QMessageBox.StandardButton.Yes:return
        from core.meeting_sessions import delete
        self.autosave.stop();delete(identity)
        if identity==self.session_id:
            self.session_id=None;self.loading_draft=True;self.transcript.clear();self.live_notes.clear();self.invalidate_output();self.loading_draft=False
        self.reload_sessions()

    def shutdown(self):
        self.autosave.stop();self.save_draft();super().shutdown()

    def choose(self):
        path,_=QFileDialog.getOpenFileName(self,t('Audio tanlash'),'','Audio (*.wav *.mp3 *.m4a *.flac *.ogg *.aac *.mp4 *.webm)')
        if path and path!=self.path.text():self.new_meeting();self.path.setText(path)

    def correct_transcript(self):
        if self.busy:return
        from core.meeting_review import correct
        before,after=self.old_term.text().strip(),self.new_term.text().strip()
        if not before or not after:return
        text=self.transcript.toPlainText()
        corrected,count=correct(text,before,after)
        if count:self.transcript.setPlainText(corrected);self.save_draft()
        self.status.setText(t('Tuzatilgan joylar')+f': {count}')

    def transcribe(self):
        if self.busy:return
        if not self.win._capabilities.policy['permissions']['files']:
            self.status.setText(t('Fayl ruxsati o‘chiq.'));return
        from memory.config_manager import load_api_keys
        from core.offline_voice import model_directory
        cfg=load_api_keys(); model=cfg.get('local_stt_path') or str(model_directory())
        path,language=self.path.text(),self.language.currentData()
        diarize=self.diarize.isChecked()
        quality=self.speech_quality.currentData()
        if not path:self.status.setText(t('Audio tanlang.'));return
        self.status.setText(t('Audio lokal tanilmoqda…'));self.transcript.clear()
        def operation(cancel,progress):
            from core.meeting_audio import transcribe_file
            def update(text):
                if not self.win._capabilities.policy['permissions']['files']:cancel.set();return
                progress(text)
            return transcribe_file(path,model,language,cancel,update,
                                   allowed=lambda:self.win._capabilities.policy['permissions']['files'],diarize=diarize,quality=quality)
        def done(text):self.transcript.setPlainText(text);self.status.setText(t('Transkript tayyor. Matnni tekshirib tahlil qiling.'))
        self.work(operation,done,progress=self.transcript.setPlainText)

    def prepare_speakers(self):
        if not self.win._capabilities.policy['permissions']['network']:
            self.status.setText(t('Modelni yuklash uchun internet ruxsatini yoqing.'));return
        from core.speaker_labels import prepare
        self.work(lambda cancel,progress:prepare(cancel,progress,
                  allowed=lambda:not self.closed and self.win._capabilities.policy['permissions']['network']),
                  lambda _:self.status.setText(t('Gapiruvchi modeli tayyor. Keyingi tahlil offline ishlaydi.')))

    def start_live(self):
        if self.busy:return
        if self.win._active_provider!='ollama' or not self.win._capabilities.policy['permissions']['microphone']:
            self.status.setText(t('Ollama rejimini va mikrofon ruxsatini yoqing.'));return
        runtime=getattr(self.win,'_local_chat',None)
        voice=getattr(self.win,'_local_voice',None)
        if getattr(self.win,'_meeting_recording',False) or (runtime and runtime.busy) or (voice and (voice.busy or voice.speaking)):
            self.status.setText(t('Avval joriy chat yoki ovoz vazifasini tugating.'));return
        from memory.config_manager import load_api_keys
        from core.offline_voice import model_directory
        cfg=load_api_keys();model=cfg.get('local_stt_path') or str(model_directory())
        language=self.language.currentData();diarize=self.diarize.isChecked();quality=self.speech_quality.currentData()
        if hasattr(self,'capture_finished') and not self.capture_finished.is_set():
            self.status.setText(t('Oldingi yozuv yopilishini kuting.'));return
        previous=self.transcript.toPlainText().strip()
        def combined(text):return previous+('\n\n[Davom]\n'+text if text else '') if previous else text
        self.status.setText(t('Jonli yozuv: mikrofon yoqilgan. Matn nutq qismlari tanilganda yangilanadi.'))
        self.live_stop=threading.Event();stop=self.live_stop
        self.capture_finished=threading.Event();finished=self.capture_finished
        self.win._meeting_recording=True
        def allowed():return not self.closed and self.win._active_provider=='ollama' and self.win._capabilities.policy['permissions']['microphone']
        def operation(cancel,progress):
            from core.live_meeting import run
            try:return run(model,language,stop,cancel,allowed,progress,diarize=diarize,quality=quality)
            finally:finished.set()
        def done(text):
            self.transcript.setPlainText(combined(text));self.save_draft();self.status.setText(t('Yozuv tugadi. Transkriptni tekshiring va xulosa oling.'))
        self.work(operation,done,progress=lambda text:self.transcript.setPlainText(combined(text)))
        self.stop_live_button.setEnabled(True)

    def set_busy(self,value):
        super().set_busy(value)
        if not value and getattr(self,'live_stop',None) is not None:
            self.live_stop.set();self.live_stop=None;self.win._meeting_recording=False
            self.stop_live_button.setEnabled(False)

    def stop_live(self):
        if self.live_stop:
            self.live_stop.set();self.stop_live_button.setEnabled(False)
            self.status.setText(t('Yozuv yopilmoqda. Oxirgi nutq tanilmoqda…'))

    def cancel(self):
        if getattr(self,'notes_job',None):
            job=self.notes_job;self.notes_job=None;job.cancel()
        self.stop_live();super().cancel()

    def update_live_notes(self):
        if self.closed or self.notes_job:return
        source=self.transcript.toPlainText().strip()
        if not source:self.status.setText(t('Avval transkript kiriting yoki jonli yozuvni boshlang.'));return
        capability='microphone' if self.live_stop is not None else 'files'
        def allowed():return not self.closed and self.win._active_provider=='ollama' and self.win._capabilities.policy['permissions'][capability]
        if not allowed():self.status.setText(t('Tahlil uchun ruxsat o‘chiq yoki rejim o‘zgardi.'));return
        self.live_notes.clear();self.live_notes.show();self.notes_status.show()
        self.notes_status.setText(t('Jonli qaydlar tayyorlanmoqda…'))
        job=AnalysisJob([('Transcript snapshot',source)],
            'Extract explicit decisions and action items with owner and deadline. Use unknown for missing details. '
            'Keep exact numbers and never infer a speaker identity from an anonymous speaker label.',self,authorize=allowed,request_ms=30000)
        self.notes_job=job
        def ready(text,error,cancelled):
            job.deleteLater()
            if self.notes_job is not job or self.closed:return
            self.notes_job=None
            self.live_notes.setPlainText('' if error or cancelled else text)
            self.notes_status.setText(t(error or ('Bekor qilindi.' if cancelled else 'Jonli qaydlar oxirgi yangilashdagi transkriptga tegishli.')))
        job.finished.connect(ready);job.start()

    def summarize(self):
        self.analyze([('Meeting transcript',self.transcript.toPlainText())],
            'Produce a concise meeting summary, explicit decisions, and an action-item table with task, owner and deadline. '
            'Preserve explicit budgets and numeric constraints in the summary. '
            'Use unknown when an action owner or deadline is not explicit. '
            'Do not add agenda, attendee, location or date sections unless explicitly supplied. '
            'Never invent speakers or assignments. Preserve timestamps when useful.')

    def export_transcript(self):
        text=self.transcript.toPlainText()
        if not text:return
        path,_=QFileDialog.getSaveFileName(self,t('Transkriptni saqlash'),'meeting-transcript.txt','Text (*.txt)')
        if path:
            try:Path(path).write_text(text,encoding='utf-8')
            except OSError:self.status.setText(t('Faylni saqlab bo‘lmadi. Boshqa joy tanlang.'))


class ReviewPage(TaskPage):
    def __init__(self,studio):
        super().__init__(studio)
        self.note('Kod yoki Git diff tahlili. Tuzatish alohida diff oynasida tasdiqlangach qo‘llanadi; zaxira nusxadan qaytarish mumkin.')
        self.path=QLineEdit();self.path.setReadOnly(True);self.layout.addWidget(self.path)
        row=self.row();self.button('Kod fayli',self.choose_file,row);self.button('Git papkasi',self.choose_git,row)
        self.button('Bir nechta kod fayli',self.choose_many,row)
        self.selected_paths=[]
        self.mode='file';self.sections=[]
        self.preview=QPlainTextEdit();self.preview.setReadOnly(True);self.layout.addWidget(self.preview,1)
        row=self.row();self.button('Manbani ko‘rish',self.load,row);self.button('Kodni tekshirish',self.review,row)
        self.fix_instruction=QLineEdit();self.fix_instruction.setPlaceholderText(t('Qanday tuzatish kerak? Masalan: nolga bo‘lishni tekshirish'))
        self.layout.addWidget(self.fix_instruction);self.fields.append(self.fix_instruction)
        row=self.row();self.button('AI tuzatish tayyorlash',self.propose_fix,row)
        self.button('Diff bilan tahrirlash',self.edit_file,row)
        self.button('Oxirgi tuzatishni qaytarish',self.undo_edit,row)
        self.button('Test bajarish',self.open_tests)
        self.last_backup=None;self.last_backups=[]
        self.add_output();self.footer()

    def choose_file(self):
        path,_=QFileDialog.getOpenFileName(self,t('Kod fayli'),'','Code (*.py *.js *.ts *.tsx *.jsx *.go *.rs *.java *.cpp *.cs *.sql *.json *.md);;All files (*)')
        if path:self.path.setText(path);self.mode='file';self.selected_paths=[];self.sections=[];self.preview.clear();self.answer='';self.result.clear();self.set_busy(False)

    def choose_many(self):
        paths,_=QFileDialog.getOpenFileNames(self,t('Bir nechta kod fayli'),'','Code files (*)')
        if not paths:return
        if len(paths)>8:self.status.setText(t('1–8 ta kod faylini tanlang.'));return
        self.selected_paths=paths;self.mode='multi';self.path.setText(' · '.join(Path(path).name for path in paths))
        self.sections=[];self.preview.clear();self.invalidate_output()

    def open_tests(self):
        from brave_test_runner import open_runner
        path=self.selected_paths[0] if self.mode=='multi' and self.selected_paths else self.path.text()
        root=path if self.mode=='git' else str(Path(path).parent) if path else ''
        open_runner(self.win,root)

    def choose_git(self):
        path=QFileDialog.getExistingDirectory(self,t('Git papkasi'))
        if path:self.path.setText(path);self.mode='git';self.sections=[];self.preview.clear();self.answer='';self.result.clear();self.set_busy(False)

    def load(self,then_review=False):
        if self.busy:return
        if not all(self.win._capabilities.policy['permissions'][cap] for cap in ('files','code')):
            self.status.setText(t('Kod va fayl ruxsatlarini yoqing.'));return
        path,mode=self.path.text(),self.mode
        if not path:self.status.setText(t('Kod fayli yoki Git papkasini tanlang.'));return
        self.sections=[];self.preview.clear();self.invalidate_output()
        def operation(cancel,progress):
            from core.code_review import file_sections,diff_sections
            if mode=='multi':return [section for path in self.selected_paths for section in file_sections(path)]
            return diff_sections(path,cancel) if mode=='git' else file_sections(path)
        def done(sections):
            self.sections=sections;self.preview.setPlainText('\n\n'.join(label+'\n'+text for label,text in sections))
            self.status.setText(t('Manba tayyor.'))
            if then_review:self.run_review()
        self.work(operation,done)

    def run_review(self):
        self.analyze(self.sections,'Review code for concrete correctness, security and reliability bugs. '
            'For each supported finding give severity, exact file/line or diff hunk, trigger, impact and a proposed fix. '
            'Line-number prefixes are reference labels, not executable code: never put them in suggested code blocks. '
            'Keep severity and impact proportional to demonstrated behavior; do not speculate about data loss or security. '
            'Propose a fix for the underlying cause, without inventing a new API contract or merely hiding errors. '
            'Do not claim to run tests. If no concrete bug is supported, say so. Avoid style-only findings.',('files','code'),task='code')

    def review(self):self.load(then_review=True)

    def edit_file(self):
        self.propose_fix(manual=True)

    def propose_fix(self,manual=False):
        if self.busy:return
        if self.mode=='multi':return self.propose_many(manual)
        if self.mode!='file':self.status.setText(t('Tuzatish uchun alohida kod faylini tanlang.'));return
        if not all(self.win._capabilities.policy['permissions'][cap] for cap in ('files','code')):
            self.status.setText(t('Kod va fayl ruxsatlarini yoqing.'));return
        from core.code_changes import snapshot,replacement,validate
        try:source=snapshot(self.path.text())
        except (ValueError,OSError) as error:self.status.setText(t(str(error)));return
        def show(text,metrics):
            if metrics.get('done_reason')=='length' or metrics.get('intermediate_length_limits'):
                self.status.setText(t('Tuzatish tugallanmagan. Sifat profilini tanlang yoki qo‘lda tahrirlang.'));return
            try:
                new_text=source.text if manual else replacement(text)
                if not manual:validate(source,new_text)
            except ValueError as error:self.status.setText(t(str(error)));return
            from brave_code_editor import CodeEditDialog
            dialog=CodeEditDialog(self,source,new_text);self.editor=dialog;dialog.open()
        if manual:show('',{});return
        try:
            from core.ollama_chat import PROFILES
            settings=Settings.read();profile='balanced' if settings.profile=='auto' else settings.profile
            if len(source.text)>PROFILES[profile]['chars']-500:
                raise ValueError('AI tuzatish uchun fayl katta. Sifat profilini yoki diff bilan qo‘lda tahrirlashni tanlang.')
        except ValueError as error:self.status.setText(t(str(error)));return
        instruction=self.fix_instruction.text().strip() or 'Fix concrete correctness bugs, preserve existing behavior and APIs.'
        self.analyze([(source.path,source.text)],
            'Return ONLY the complete corrected file, in one code block, with no explanation or line-number prefixes. '
            'Do not omit unchanged code, add placeholders, or execute code. Task: '+instruction,
            ('files','code'),on_result=show,task='code',force_route=True)

    def undo_edit(self):
        if self.last_backups:
            if not all(self.win._capabilities.policy['permissions'][cap] for cap in ('files','code')):
                self.status.setText(t('Kod va fayl ruxsatlarini yoqing.'));return
            from core.file_backups import restore,digest
            from core import workspace_store
            rows=workspace_store.read('file-backups.json',[])
            try:
                for identity in self.last_backups:
                    record=next((row for row in rows if row['id']==identity),None)
                    if not record or record.get('restored') or digest(record['path'])!=record['after']:
                        raise ValueError('Fayl keyinroq o‘zgargan. Guruh qaytarilmadi.')
                for identity in reversed(self.last_backups):restore(identity)
                self.last_backups=[];self.status.setText(t('Oldingi kod tiklandi.'))
            except (ValueError,OSError) as error:self.status.setText(t(str(error)))
            return
        if not self.last_backup:return
        if not all(self.win._capabilities.policy['permissions'][cap] for cap in ('files','code')):
            self.status.setText(t('Kod va fayl ruxsatlarini yoqing.'));return
        from core.file_backups import restore
        try:
            restore(self.last_backup);self.last_backup=None
            self.status.setText(t('Oldingi kod tiklandi.'))
        except (ValueError,OSError) as error:self.status.setText(t(str(error)))

    def propose_many(self,manual=False):
        if not all(self.win._capabilities.policy['permissions'][cap] for cap in ('files','code')):
            self.status.setText(t('Kod va fayl ruxsatlarini yoqing.'));return
        from core.code_changes import snapshot,search_replace
        from brave_code_editor import MultiCodeEditDialog
        try:
            sources=[snapshot(path) for path in self.selected_paths]
            if not sources:raise ValueError('Kod fayllarini tanlang.')
            if len({Path(source.path).name for source in sources})!=len(sources):raise ValueError('Tanlangan fayl nomlari takrorlanmasin.')
            if manual:
                self.editor=MultiCodeEditDialog(self,[(source,source.text) for source in sources]);self.editor.open();return
            settings=Settings.read();profile='balanced' if settings.profile=='auto' else settings.profile
            from core.ollama_chat import PROFILES
            if sum(len(source.text)+len(Path(source.path).name) for source in sources)>PROFILES[profile]['chars']-700:
                raise ValueError('AI uchun kod katta. Kamroq fayl, Sifat profili yoki qo‘lda diff tahririni tanlang.')
        except (ValueError,OSError) as error:self.status.setText(t(str(error)));return
        def ready(text,metrics):
            try:
                if metrics.get('done_reason')=='length' or metrics.get('intermediate_length_limits'):raise ValueError('Tuzatish JSON tugallanmagan.')
                changes=search_replace(sources,text)
                if not changes:raise ValueError('O‘zgarish yo‘q.')
                self.editor=MultiCodeEditDialog(self,changes);self.editor.open()
            except ValueError as error:self.status.setText(t(str(error)))
        self.analyze([(Path(source.path).name,source.text) for source in sources],
            'Return ONLY JSON with schema {"edits":[{"file":"selected basename","search":"exact existing substring",'
            '"replace":"replacement substring"}]}. Every search must match exactly once. Use only supplied filenames. '
            'Include leading indentation in search and replacement; keep Python nested blocks valid. '
            'Every referenced symbol must exist or be explicitly defined/imported. Never reference a symbol from another file without an import. '
            'Keep unchanged code. Do not execute anything. Task: '+(self.fix_instruction.text().strip() or 'Fix concrete correctness bugs.'),
            ('files','code'),on_result=ready,task='code',force_route=True)


class DictionaryPage(TaskPage):
    def __init__(self,studio):
        super().__init__(studio)
        self.note('Atama — to‘g‘ri yozuv. Tanilish varianti — ovozdan xato eshitiladigan shakl. Talaffuz — ovoz chiqarishda aytiladigan shakl.')
        self.table=QTableWidget(0,3);self.table.setHorizontalHeaderLabels([t('Atama'),t('Tanilish varianti'),t('Talaffuz')])
        self.table.horizontalHeader().setStretchLastSection(True);self.layout.addWidget(self.table,1)
        for row in speech_dictionary.load():self.add(row)
        line=self.row();self.button('Qo‘shish',lambda:self.add(),line);self.button('O‘chirish',self.remove,line);self.button('Saqlash',self.save,line)
        self.sample=QLineEdit();self.sample.setPlaceholderText(t('Sinov matni'));self.layout.addWidget(self.sample)
        self.button('Lug‘atni tekshirish',self.test)
        self.preview=QPlainTextEdit();self.preview.setReadOnly(True);self.layout.addWidget(self.preview,1)
        self.note('Bu shaxsiy tuzatishlar va talaffuz lug‘ati; nutq modeli qayta o‘qitilmaydi.')
        self.footer()

    def add(self,value=None):
        value=value or {};index=self.table.rowCount();self.table.insertRow(index)
        for j,name in enumerate(('term','recognized','pronunciation')):self.table.setItem(index,j,QTableWidgetItem(value.get(name,'')))

    def rows(self):
        rows=[]
        for i in range(self.table.rowCount()):
            row={name:(self.table.item(i,j).text() if self.table.item(i,j) else '') for j,name in enumerate(('term','recognized','pronunciation'))}
            if any(row.values()):rows.append(row)
        return speech_dictionary.validate(rows)

    def remove(self):
        if self.table.currentRow()>=0:self.table.removeRow(self.table.currentRow())

    def save(self):
        try:speech_dictionary.save(self.rows());self.status.setText(t('Lug‘at saqlandi. Keyingi nutq va ovozga qo‘llanadi.'))
        except (ValueError,OSError) as error:self.status.setText(t(str(error)))

    def test(self):
        try:
            rows=self.rows();text=self.sample.text()
            self.preview.setPlainText(t('Tanilish')+': '+speech_dictionary.correct(text,rows)+'\n'+t('Talaffuz')+': '+speech_dictionary.pronounce(text,rows))
        except ValueError as error:self.status.setText(t(str(error)))


class AIStudio(QDialog):
    def __init__(self,win,tab='models'):
        super().__init__(win)
        from brave_control_center import style_dialog
        self.win=win;self.button_style=style_dialog(self,'AI Studio')
        screen=win.screen().availableGeometry()
        self.resize(max(780,min(980,screen.width()-40)),max(560,min(720,screen.height()-64)))
        self.setMinimumSize(780,560);self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        layout=QVBoxLayout(self);self.tabs=QTabWidget();self.tabs.setUsesScrollButtons(True);layout.addWidget(self.tabs)
        self.pages={};self.tab_widgets={}
        from brave_screen_page import ScreenPage
        for key,title,factory in [('models','Model tavsiyasi',ModelsPage),('desktop','Offline amallar',DesktopPage),
                                  ('screen','Ekran tahlili',ScreenPage),('meeting','Uchrashuv',MeetingPage),('review','Kod tahlili',ReviewPage),('dictionary','Shaxsiy lug‘at',DictionaryPage)]:
            page=factory(self);self.pages[key]=page
            from brave_ui import colors
            page.setObjectName('AIStudioPage');page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True)
            page.setStyleSheet(f'QWidget#AIStudioPage {{background:{colors().PANEL};}}')
            area=QScrollArea();area.setWidgetResizable(True);area.setFrameShape(QFrame.Shape.NoFrame)
            area.setStyleSheet(f'QScrollArea {{background:{colors().PANEL};border:none;}}')
            area.setWidget(page);self.tab_widgets[key]=area;self.tabs.addTab(area,t(title))
        self.select_tab(tab)
        close=QPushButton(t('Yopish'));close.setStyleSheet(self.button_style);close.clicked.connect(self.accept);layout.addWidget(close)

    def done(self,result):
        for page in self.pages.values():page.shutdown()
        super().done(result)

    def select_tab(self,key):self.tabs.setCurrentWidget(self.tab_widgets.get(key,self.tab_widgets['models']))


def open_studio(win,tab='models'):
    existing=getattr(win,'_ai_studio',None)
    if existing is not None:
        existing.select_tab(tab)
        existing.raise_();return existing
    dialog=AIStudio(win,tab);win._ai_studio=dialog
    dialog.finished.connect(lambda _:setattr(win,'_ai_studio',None))
    dialog.open();return dialog
