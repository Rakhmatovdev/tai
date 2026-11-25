"""Local AI settings: measured comparisons, explicit OCR setup and application recovery."""
import json
import statistics
import time
from dataclasses import replace
from pathlib import Path
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QDialog,QWidget,QTabWidget,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPlainTextEdit,QPushButton,QCheckBox,QTableWidget,QTableWidgetItem,QFileDialog
from brave_control_center import style_dialog
from brave_i18n import translate as t
from brave_ollama_request import ChatRequest
from core.ollama_chat import Settings,local_model
from core.local_jobs import gate
from core import workspace_store
from memory.config_manager import load_api_keys,_patch_config


class LocalLab(QDialog):
    def __init__(self,win,form=None):
        super().__init__(win);self.win=win;self.form=form;self.job=None;self.ticket=None;self.queue=[];self.samples=[]
        self.style=style_dialog(self,'Lokal AI imkoniyatlari');self.resize(900,650)
        layout=QVBoxLayout(self);tabs=QTabWidget();layout.addWidget(tabs)
        tabs.addTab(self.benchmark_page(),t('Model taqqoslash'))
        tabs.addTab(self.ocr_page(),t('OCR sozlamalari'))
        tabs.addTab(self.recovery_page(),t('Ilova nusxasi'))
        self.timer=QTimer(self);self.timer.setInterval(100);self.timer.timeout.connect(self.next_sample)

    def button(self,title,callback,layout):
        button=QPushButton(t(title));button.setStyleSheet(self.style);button.clicked.connect(callback);layout.addWidget(button);return button

    def benchmark_page(self):
        page=QWidget();layout=QVBoxLayout(page)
        note=QLabel(t('Bir xil savol bilan 3 takror. Cold sinovi tanlangan modelni xotiradan bo‘shatadi. Sifatni javob namunalari orqali solishtiring.'))
        note.setWordWrap(True);layout.addWidget(note)
        self.models=QLineEdit(load_api_keys().get('ollama_model','llama3.2'))
        self.models.setPlaceholderText(t('Model nomlari · vergul bilan ajrating'));layout.addWidget(self.models)
        self.question=QPlainTextEdit('O‘zbek tilida javob bering: Ali 12 ta daftar oldi, 5 tasini berdi. Unda nechta daftar qoldi? Qisqa izohlang.')
        self.question.setMaximumHeight(85);layout.addWidget(self.question)
        self.cold=QCheckBox(t('Har takrorda Cold va Warm sinovi'));self.cold.setChecked(True);layout.addWidget(self.cold)
        self.table=QTableWidget(0,7);self.table.setHorizontalHeaderLabels(['Model','Run','State','TTFT s','Total s','tok/s','RAM / VRAM GiB'])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);layout.addWidget(self.table,1)
        self.table.resizeColumnsToContents();self.table.horizontalHeader().setStretchLastSection(True)
        QTimer.singleShot(0,self.table.resizeColumnsToContents)
        self.answers=QPlainTextEdit();self.answers.setReadOnly(True);self.answers.setMaximumHeight(120);layout.addWidget(self.answers)
        self.table.cellClicked.connect(self.show_answer)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        row=QHBoxLayout();layout.addLayout(row)
        self.start_button=self.button('Tekshirish',self.start,row)
        self.button('Bekor qilish',self.stop,row);self.button('Natijalarni eksport qilish',self.export,row)
        return page

    def start(self):
        if self.job or self.queue:return
        if getattr(self.win,'_meeting_recording',False):
            self.status.setText(t('Avval jonli uchrashuv yozuvini tugating. Matningiz saqlandi.'));return
        runtime=getattr(self.win,'_local_chat',None)
        if runtime and runtime.busy:self.status.setText(t('Avval joriy javob tugashini kuting.'));return
        try:
            settings=self.form.values() if self.form else Settings.read()
            settings=replace(settings,profile='balanced' if settings.profile=='auto' else settings.profile)
            names=list(dict.fromkeys(local_model(name.strip()) for name in self.models.text().split(',') if name.strip()))
            if not 1<=len(names)<=4 or not 1<=len(self.question.toPlainText())<=1000:raise ValueError('1–4 model va 1000 belgigacha savol tanlang.')
        except ValueError as exc:self.status.setText(t(str(exc)));return
        self.samples=[];self.table.setRowCount(0);self.answers.clear();self.start_button.setEnabled(False)
        self.prompt=self.question.toPlainText()
        self.queue=[(replace(settings,model=name),run,cold) for name in names for run in range(1,4)
                    for cold in ([True,False] if self.cold.isChecked() else [False])]
        self.started=time.monotonic();self.timer.start();self.status.setText(t('Resurs navbati kutilmoqda…'))

    def next_sample(self):
        if self.job:return
        if not self.queue:
            self.timer.stop();self.start_button.setEnabled(True);self.summary();return
        ticket=gate.try_acquire()
        if ticket is None:return
        self.ticket=ticket
        settings,run,cold=self.queue.pop(0)
        self.current=(settings,run,cold)
        self.job=ChatRequest(settings,[{'role':'user','content':self.prompt}],self,cold=cold,keep_alive='5m')
        self.job.finished.connect(self.sample_done)
        self.status.setText(f'{settings.model} · {run}/3 · '+('Cold' if cold else 'Warm / observed'))
        self.job.start()

    def sample_done(self,text,error,cancelled):
        from core.ollama_resources import sample_resources,GIB
        job,self.job=self.job,None
        if self.ticket is not None:gate.release(self.ticket);self.ticket=None
        if not job:return
        metrics=dict(job.metrics);job.deleteLater()
        if cancelled:return
        settings,run,cold=self.current
        if not error:
            from core.model_performance import record
            from core.model_router import task_for
            record(settings,task_for(self.prompt),metrics)
        resource=sample_resources()
        used_ram=(resource.ram_total-resource.ram_free)/GIB if resource.ram_total and resource.ram_free is not None else None
        used_gpu=(resource.gpu_total-resource.gpu_free)/GIB if resource.gpu_total and resource.gpu_free is not None else None
        sample={'model':settings.model,'profile':settings.profile,'run':run,'requested_cold':cold,
            'metrics':metrics,'answer':text,'error':error,'ram_used_gib':used_ram,'gpu_used_gib':used_gpu}
        self.samples.append(sample)
        def number(value):return f'{value:.2f}' if isinstance(value,(int,float)) else '—'
        row=self.table.rowCount();self.table.insertRow(row)
        state='Cold' if cold and metrics.get('residency')=='not_loaded' else metrics.get('residency','unknown')
        values=[settings.model,str(run),state,
            number(metrics.get('first_reply_s')),number(metrics.get('request_s')),number(metrics.get('tokens_per_second')),
            number(used_ram)+' / '+number(used_gpu)]
        for col,value in enumerate(values):self.table.setItem(row,col,QTableWidgetItem(value))
        self.table.resizeColumnsToContents()
        # Persist only numeric diagnostics/model identity. Prompt and answers stay in this dialog.
        workspace_store.append('local-benchmarks.json',{key:value for key,value in sample.items() if key not in ('answer','error')},limit=200)
        if error:self.status.setText(t(error))

    def show_answer(self,row,column):
        if row<len(self.samples):self.answers.setPlainText(self.samples[row]['error'] or self.samples[row]['answer'])

    def summary(self):
        parts=[]
        for name in dict.fromkeys(row['model'] for row in self.samples):
            rows=[r for r in self.samples if r['model']==name and not r['error']]
            groups={}
            for row in rows:
                residency=row['metrics'].get('residency','unknown')
                state='cold' if row['requested_cold'] and residency=='not_loaded' else residency
                value=row['metrics'].get('first_reply_s')
                if value is not None:groups.setdefault(state,[]).append(value)
            for state,values in groups.items():
                parts.append(f'{name} · {state}: median TTFT {statistics.median(values):.2f}s [{min(values):.2f}–{max(values):.2f}], n={len(values)}')
        self.status.setText('\n'.join(parts) or t('Natija yo‘q.'))

    def stop(self):
        self.queue=[];self.timer.stop()
        if self.job:self.job.cancel()
        if self.ticket is not None:gate.release(self.ticket);self.ticket=None
        self.start_button.setEnabled(True)

    def export(self):
        if not self.samples:return
        path,_=QFileDialog.getSaveFileName(self,t('Natijalarni eksport qilish'),'brave-benchmark.json','JSON (*.json)')
        if path:
            Path(path).write_text(json.dumps(self.samples,ensure_ascii=False,indent=2),encoding='utf-8')

    def ocr_page(self):
        cfg=load_api_keys();page=QWidget();layout=QVBoxLayout(page)
        note=QLabel(t('OCR shu qurilmada ishlaydi. Tesseract va tanlangan tillarning traineddata fayllari kerak.'))
        note.setWordWrap(True);layout.addWidget(note)
        self.ocr=QLineEdit(cfg.get('local_ocr_executable',''));self.ocr.setPlaceholderText('tesseract.exe');layout.addWidget(self.ocr)
        self.button('Dastur tanlash',self.choose_ocr,layout)
        self.languages=QLineEdit(cfg.get('local_ocr_languages','uzb+uzb_cyrl+eng+rus'));layout.addWidget(self.languages)
        self.button('Saqlash',self.save_ocr,layout)
        self.ocr_status=QLabel();self.ocr_status.setWordWrap(True);layout.addWidget(self.ocr_status);layout.addStretch()
        return page

    def choose_ocr(self):
        path,_=QFileDialog.getOpenFileName(self,t('Dastur tanlash'),'','Tesseract (tesseract.exe);;All files (*)')
        if path:self.ocr.setText(path)

    def save_ocr(self):
        import re
        path=self.ocr.text().strip();languages=self.languages.text().strip()
        if (path and not Path(path).is_file()) or not re.fullmatch(r'[a-z_]+(?:\+[a-z_]+)*',languages):
            self.ocr_status.setText(t('OCR dasturi yoki tillari noto‘g‘ri.'));return
        _patch_config(local_ocr_executable=path,local_ocr_languages=languages)
        self.ocr_status.setText(t('Sozlamalar saqlandi.'))

    def recovery_page(self):
        page=QWidget();layout=QVBoxLayout(page)
        note=QLabel(t('Chatlar, xotira va lokal sozlamalar nusxasi. API kalitlari va katta model fayllari kiritilmaydi. Tiklashdan keyin ilovani qayta oching.'))
        note.setWordWrap(True);layout.addWidget(note)
        self.button('Ilova nusxasini saqlash',self.backup,layout)
        self.button('Nusxadan tiklashni tayyorlash',self.restore,layout)
        self.recovery_status=QLabel();self.recovery_status.setWordWrap(True);layout.addWidget(self.recovery_status);layout.addStretch();return page

    def backup(self):
        from core.app_recovery import backup
        if not self.win._capabilities.policy['permissions']['files']:
            self.recovery_status.setText(t('Fayllarga ruxsat o‘chiq.'));return
        path,_=QFileDialog.getSaveFileName(self,t('Ilova nusxasini saqlash'),'brave-backup.zip','ZIP (*.zip)')
        if path:
            try:backup(path,self.win._features.store.db);self.recovery_status.setText(t('Nusxa saqlandi.'))
            except (ValueError,OSError) as exc:self.recovery_status.setText(t(str(exc)))

    def restore(self):
        from core.app_recovery import stage_restore
        if not self.win._capabilities.policy['permissions']['files']:
            self.recovery_status.setText(t('Fayllarga ruxsat o‘chiq.'));return
        path,_=QFileDialog.getOpenFileName(self,t('Nusxadan tiklashni tayyorlash'),'','ZIP (*.zip)')
        if path:
            try:stage_restore(path);self.recovery_status.setText(t('Tiklash tayyor. Ilovani qayta oching. Oldingi ma’lumotlar nusxasi saqlanadi.'))
            except (ValueError,OSError) as exc:self.recovery_status.setText(t(str(exc)))

    def done(self,result):self.stop();super().done(result)


def open_lab(win,form=None):LocalLab(win,form).exec()
