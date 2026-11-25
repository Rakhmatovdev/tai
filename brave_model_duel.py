"""Fair input, sequential local model comparison using the shared inference gate."""
from dataclasses import replace
import time
from PyQt6.QtCore import Qt,QTimer
from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QPlainTextEdit,
    QPushButton,QSplitter,QWidget,QFileDialog,QApplication,QMessageBox)
from brave_i18n import translate as t
from core.ollama_chat import Settings,PROFILES,local_model,OllamaClient
from brave_ai_pipeline import AnalysisJob
from brave_local_jobs import Worker
from core import comparison_store


class ModelDuel(QDialog):
    def __init__(self,win):
        super().__init__(win);self.win=win;self.job=None;self.worker=None;self.revision=0;self.closed=False;self.busy=False
        self.results=['',''];self.metrics=[{},{}];self.durations=[0,0];self.current=0;self.models=[];self.question=''
        self.errors=['',''];self.record_id=None;self.created='';self.result_profile='balanced';self.save_error=''
        from brave_control_center import style_dialog
        self.style=style_dialog(self,'Ikki modelni taqqoslash');screen=win.screen().availableGeometry()
        self.resize(min(1020,screen.width()-40),min(730,screen.height()-64))
        layout=QVBoxLayout(self)
        history=QHBoxLayout();layout.addLayout(history)
        self.history=QComboBox();self.history.setProperty('brave_literal_text',True);self.history.setMinimumContentsLength(15)
        self.history.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);history.addWidget(self.history,1)
        self.history_open=QPushButton(t('Saqlangan natijani ochish'));self.history_open.clicked.connect(self.restore);history.addWidget(self.history_open)
        self.history_delete=QPushButton(t('Saqlangan natijani o‘chirish'));self.history_delete.clicked.connect(self.delete_saved);history.addWidget(self.history_delete)
        for button in (self.history_open,self.history_delete):button.setStyleSheet(self.style);button.setAutoDefault(False)
        self.history.currentIndexChanged.connect(self.history_selection)
        note=QLabel(t('Bir xil savol va profil. Modellar ketma-ket ishlaydi; sovuq/issiq yuklanish vaqtga ta’sir qiladi.'));note.setWordWrap(True);layout.addWidget(note)
        row=QHBoxLayout();layout.addLayout(row);self.pickers=[]
        for _ in range(2):
            picker=QComboBox();picker.setEditable(True);picker.setProperty('brave_literal_text',True);row.addWidget(picker,1);self.pickers.append(picker)
        try:self.pickers[0].setEditText(Settings.read().model)
        except ValueError:pass
        self.pickers[1].lineEdit().setPlaceholderText(t('Ikkinchi model'))
        self.profile=QComboBox()
        for key in ('economy','balanced','quality'):self.profile.addItem(key.capitalize(),key)
        self.profile.setCurrentIndex(1);row.addWidget(self.profile)
        self.load=QPushButton(t('Modellarni yangilash'));self.load.clicked.connect(self.refresh_models);layout.addWidget(self.load)
        self.prompt=QPlainTextEdit();self.prompt.setPlaceholderText(t('Ikkala modelga yuboriladigan savol…'));self.prompt.setMaximumHeight(115);layout.addWidget(self.prompt)
        split=QSplitter();layout.addWidget(split,1);self.outputs=[];self.statuses=[]
        for side in range(2):
            panel=QWidget();column=QVBoxLayout(panel);label=QLabel();label.setWordWrap(True);label.setTextFormat(Qt.TextFormat.PlainText);column.addWidget(label);self.statuses.append(label)
            output=QPlainTextEdit();output.setReadOnly(True);column.addWidget(output,1);self.outputs.append(output)
            bar=QHBoxLayout();column.addLayout(bar)
            for title,handler in [('Nusxalash',lambda checked=False,n=side:self.copy(n)),('Qoralamaga qo‘yish',lambda checked=False,n=side:self.insert(n))]:
                button=QPushButton(t(title));button.setStyleSheet(self.style);button.clicked.connect(handler);bar.addWidget(button)
            split.addWidget(panel)
        self.status=QLabel();self.status.setWordWrap(True);self.status.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(self.status)
        bar=QHBoxLayout();layout.addLayout(bar);self.buttons={}
        for key,title,handler in [('start','Taqqoslash',self.start),('cancel','Bekor qilish',self.cancel),('export','Taqqoslashni eksport qilish',self.export),('close','Yopish',self.reject)]:
            button=QPushButton(t(title));button.setStyleSheet(self.style);button.setAutoDefault(False);button.clicked.connect(handler);bar.addWidget(button);self.buttons[key]=button
        self.load.setStyleSheet(self.style)
        self.timer=QTimer(self);self.timer.setInterval(200);self.timer.timeout.connect(self.check)
        self.reload_history();self.set_busy(False)

    def allowed(self):return not self.closed and self.win._active_provider=='ollama' and not getattr(self.win,'_meeting_recording',False)

    def set_busy(self,value):
        self.busy=value
        for widget in (*self.pickers,self.profile,self.prompt,self.load):widget.setEnabled(not value and not self.worker)
        self.buttons['start'].setEnabled(not value and not self.worker);self.buttons['cancel'].setEnabled(value or bool(self.worker))
        self.buttons['export'].setEnabled(not value and any(self.results))
        self.history.setEnabled(not value and not self.worker);self.history_selection()

    def history_selection(self,*args):
        enabled=not self.busy and not self.worker and bool(self.history.currentData())
        self.history_open.setEnabled(enabled);self.history_delete.setEnabled(enabled)

    def reload_history(self):
        selected=self.record_id or self.history.currentData();self.history.blockSignals(True);self.history.clear()
        self.history.addItem(t('Saqlangan taqqoslashlar · oxirgi 20 ta'),None)
        for row in comparison_store.rows():
            self.history.addItem(row['created'][:16].replace('T',' ')+' UTC · '+' '.join(row['question'].split())[:75],row['id'])
        self.history.setCurrentIndex(max(0,self.history.findData(selected)));self.history.blockSignals(False);self.history_selection()

    def persist_result(self):
        if not any(self.results):return
        try:
            comparison_store.save(dict(id=self.record_id,created=self.created,question=self.question,profile=self.result_profile,
                models=self.models,results=self.results,errors=self.errors,durations=self.durations,metrics=self.metrics))
            self.save_error='';self.reload_history()
        except (OSError,ValueError) as error:self.save_error=t('Natijani tarixga saqlab bo‘lmadi. Eksport qilishingiz mumkin.')+' '+str(error)

    def restore(self):
        if self.busy or self.worker:return
        row=next((row for row in comparison_store.rows() if row['id']==self.history.currentData()),None)
        if not row:return
        if self.prompt.toPlainText().strip() and self.prompt.toPlainText().strip()!=row['question']:
            if QMessageBox.question(self,t('Saqlanmagan o‘zgarishlar'),t('Joriy savol saqlangan taqqoslash bilan almashtirilsinmi?'),QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        self.record_id=row['id'];self.created=row['created'];self.question=row['question'];self.result_profile=row['profile'];self.save_error=''
        self.models=row['models'];self.results=row['results'];self.metrics=row['metrics'];self.durations=row['durations'];self.errors=row['errors']
        self.prompt.setPlainText(self.question);self.profile.setCurrentIndex(self.profile.findData(self.result_profile))
        for side in range(2):
            self.pickers[side].setEditText(self.models[side]);self.render_side(side)
        self.set_busy(False);self.status.setText(t('Saqlangan natija ochildi. Model ishga tushirilmadi.'))

    def delete_saved(self):
        identity=self.history.currentData()
        if self.busy or self.worker or not identity:return
        if QMessageBox.question(self,t('Saqlangan natijani o‘chirish'),t('Bu taqqoslash tarixdan o‘chirilsinmi?'),QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        try:comparison_store.delete(identity)
        except OSError as error:self.status.setText(str(error));return
        if self.record_id==identity:self.record_id=None
        self.reload_history();self.status.setText(t('Saqlangan natija o‘chirildi.'))

    def refresh_models(self):
        if self.busy or self.worker:return
        try:settings=Settings.read()
        except ValueError as error:self.status.setText(t(str(error)));return
        def operation(cancel,progress):
            client=OllamaClient(settings)
            try:return client.models()
            finally:client.close()
        worker=Worker(self,operation);self.worker=worker;revision=self.revision;self.set_busy(False)
        def done(result,error):
            if self.closed or revision!=self.revision:return
            self.worker=None
            if error or result is None:self.status.setText(t(error or 'Bekor qilindi.'))
            else:
                for side,picker in enumerate(self.pickers):
                    previous=picker.currentText();picker.clear();picker.addItems(result)
                    if previous:picker.setEditText(previous)
                    elif side==1:picker.setCurrentIndex(next((i for i,name in enumerate(result) if name!=self.pickers[0].currentText()),-1))
                self.status.setText(t('Modellar ro‘yxati tayyor.'))
            self.set_busy(False)
        worker.completed.connect(done);worker.start()

    def start(self):
        if self.busy or self.worker:return
        try:
            if not self.allowed():raise ValueError('Taqqoslash uchun Ollama rejimini tanlang va jonli yozuvni tugating.')
            settings=Settings.read();models=[local_model(picker.currentText().strip()) for picker in self.pickers]
            if models[0].removesuffix(':latest')==models[1].removesuffix(':latest'):raise ValueError('Ikki xil model tanlang.')
            question=self.prompt.toPlainText().strip();profile=self.profile.currentData()
            if not question:raise ValueError('Savolni yozing.')
            if len(question)>PROFILES[profile]['chars']:raise ValueError('Xabar juda uzun. Uni qisqartiring yoki Sifat profilini tanlang.')
        except ValueError as error:self.status.setText(t(str(error)));return
        self.revision+=1;self.models=models;self.question=question;self.settings=replace(settings,profile=profile)
        self.results=['',''];self.metrics=[{},{}];self.durations=[0,0];self.current=0
        self.errors=['',''];self.record_id=comparison_store.new_id();self.created=comparison_store.now();self.result_profile=profile;self.save_error=''
        for output in self.outputs:output.clear()
        for side,label in enumerate(self.statuses):label.setText(models[side]+' · '+t('Navbatda'))
        self.set_busy(True);self.timer.start();self.run_side()

    def run_side(self):
        if not self.allowed():self.cancel();return
        side=self.current;revision=self.revision;self.started=time.monotonic()
        from core.model_router import task_for
        settings=replace(self.settings,model=self.models[side]);job=AnalysisJob([('Question',self.question)],'',self,
            authorize=self.allowed,settings=settings,direct=True,task=task_for(self.question))
        self.job=job
        job.partial.connect(lambda text:self.outputs[side].setPlainText(text) if self.busy and revision==self.revision else None)
        job.progress.connect(lambda text:self.status.setText(t(text)) if revision==self.revision else None)
        job.finished.connect(lambda text,error,cancelled:self.finished_side(job,side,revision,text,error,cancelled));job.start()

    def finished_side(self,job,side,revision,text,error,cancelled):
        if self.closed or revision!=self.revision:return
        self.job=None;self.durations[side]=time.monotonic()-self.started;self.metrics[side]=dict(job.metrics)
        self.results[side]=text if not error and not cancelled else '';self.errors[side]=error or ('Bekor qilindi.' if cancelled else '')
        self.render_side(side);self.persist_result();job.deleteLater()
        if side==0 and not cancelled and self.allowed():self.current=1;self.run_side()
        else:
            self.timer.stop();self.set_busy(False);self.status.setText(self.save_error or t('Taqqoslash tugadi. Javob sifatini o‘zingiz baholang.'))

    def render_side(self,side):
        self.outputs[side].setPlainText(self.results[side] or t(self.errors[side] or 'Natija olinmadi.'))
        detail=t('Tugallandi') if self.results[side] else t('Xato' if self.errors[side] else 'Natija olinmadi.');duration=f'{self.durations[side]:.2f}s'
        metrics=self.metrics[side]
        if metrics.get('done_reason')=='length':detail+=' · '+t('Javob uzunlik chegarasiga yetdi.')
        timing=[]
        if isinstance(metrics.get('first_reply_s'),(int,float)):timing.append('TTFT '+f"{metrics['first_reply_s']:.2f}s")
        if isinstance(metrics.get('tokens_per_second'),(int,float)):timing.append(f"{metrics['tokens_per_second']:.1f} tok/s")
        if timing:detail+='\n'+' · '.join(timing)
        self.statuses[side].setText(self.models[side]+' · '+detail+' · '+duration)

    def check(self):
        if not self.allowed():self.cancel()
        elif self.busy:self.statuses[self.current].setText(self.models[self.current]+' · '+f'{time.monotonic()-self.started:.1f}s')

    def cancel(self):
        self.revision+=1;self.timer.stop()
        if self.worker:self.worker.cancel();self.worker=None
        job,self.job=self.job,None
        if job:job.cancel();job.deleteLater()
        if self.busy and not self.results[self.current]:
            self.outputs[self.current].clear();self.statuses[self.current].setText(t('Bekor qilindi.'))
            self.errors[self.current]='Bekor qilindi.';self.durations[self.current]=time.monotonic()-self.started;self.persist_result()
        self.set_busy(False);self.status.setText(self.save_error or t('Bekor qilindi.'))

    def copy(self,side):
        if self.results[side]:self.win._clipboard_self_value=self.results[side];QApplication.clipboard().setText(self.results[side])

    def insert(self,side):
        if self.results[side]:
            from brave_command_library import insert_draft
            insert_draft(self.win,self.results[side])

    def export(self):
        if self.busy or not any(self.results):return
        path,_=QFileDialog.getSaveFileName(self,t('Taqqoslashni eksport qilish'),'brave-comparison.md','Markdown (*.md)')
        if not path:return
        rows=['# Brave model comparison','',self.question,'']
        for side in range(2):
            rows.extend(['## '+self.models[side],f'{self.durations[side]:.2f}s · '+self.result_profile,'',self.results[side] or t(self.errors[side] or 'Natija olinmadi.'),''])
        try:
            from core.text_export import write
            write(path,'\n'.join(rows))
            self.status.setText(t('Saqlandi.'))
        except OSError as error:self.status.setText(str(error))

    def done(self,result):self.cancel();self.closed=True;super().done(result)


def open_duel(win):
    dialog=getattr(win,'_model_duel',None)
    if dialog is None:
        dialog=ModelDuel(win);win._model_duel=dialog;dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.finished.connect(lambda _:setattr(win,'_model_duel',None))
    dialog.show();dialog.raise_();dialog.activateWindow();return dialog
