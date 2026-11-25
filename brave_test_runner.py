"""Human-reviewed test runner. No AI suggestion is executed automatically."""
import shlex
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QComboBox,QSpinBox,QPlainTextEdit,QPushButton,QFileDialog,QCheckBox
from brave_local_jobs import Worker
from brave_i18n import translate as t
from core.test_execution import command,run


class TestRunner(QDialog):
    def __init__(self,win,root=''):
        super().__init__(win);self.win=win;self.worker=None;self.closed=False
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        from brave_control_center import style_dialog
        style=style_dialog(self,'Test bajarish');self.resize(850,620)
        layout=QVBoxLayout(self)
        note=QLabel(t('Test loyiha kodi sifatida kompyuteringizda bajariladi. Buyruq va papkani tekshirib tasdiqlang. Bu OS sandbox emas.'))
        note.setWordWrap(True);layout.addWidget(note)
        self.root=QLineEdit(str(root));layout.addWidget(self.root)
        choose=QPushButton(t('Loyiha papkasini tanlash'));choose.clicked.connect(self.choose);layout.addWidget(choose)
        row=QHBoxLayout();layout.addLayout(row);self.kind=QComboBox()
        for name,key in [('Python unittest','unittest'),('Python pytest','pytest'),('Node.js tests','node')]:self.kind.addItem(name,key)
        row.addWidget(self.kind);self.timeout=QSpinBox();self.timeout.setRange(1,300);self.timeout.setValue(60);self.timeout.setSuffix(' s');row.addWidget(self.timeout)
        self.args=QLineEdit('discover -s tests');layout.addWidget(self.args)
        self.preview=QPlainTextEdit();self.preview.setReadOnly(True);self.preview.setMaximumHeight(75);layout.addWidget(self.preview)
        self.approved=QCheckBox(t('Ko‘rsatilgan buyruqni shu papkada bajarishga roziman'));layout.addWidget(self.approved)
        self.output=QPlainTextEdit();self.output.setReadOnly(True);layout.addWidget(self.output,1)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        row=QHBoxLayout();layout.addLayout(row)
        self.start_button=QPushButton(t('Testni boshlash'));self.start_button.clicked.connect(self.start)
        self.cancel_button=QPushButton(t('To‘xtatish'));self.cancel_button.clicked.connect(self.cancel)
        close=QPushButton(t('Yopish'));close.clicked.connect(self.reject)
        for button in (choose,self.start_button,self.cancel_button,close):button.setStyleSheet(style)
        for button in (self.start_button,self.cancel_button,close):row.addWidget(button)
        self.root.textChanged.connect(self.refresh);self.args.textChanged.connect(self.refresh)
        self.kind.currentIndexChanged.connect(self.change_kind);self.timeout.valueChanged.connect(lambda:self.approved.setChecked(False))
        self.refresh()

    def choose(self):
        path=QFileDialog.getExistingDirectory(self,t('Loyiha papkasini tanlash'),self.root.text())
        if path:self.root.setText(path)

    def change_kind(self):
        self.args.setText('discover -s tests' if self.kind.currentData()=='unittest' else '-q' if self.kind.currentData()=='pytest' else '')
        self.refresh()

    def values(self):
        if not self.root.text().strip():raise ValueError('Loyiha papkasini tanlang.')
        # shlex is a tokenizer only; argv is never passed through a shell.
        args=shlex.split(self.args.text(),posix=True)
        root,argv=command(self.root.text(),self.kind.currentData(),args)
        return root,args,argv

    def refresh(self,*args):
        self.approved.setChecked(False)
        try:
            root,_,argv=self.values();self.preview.setPlainText(str(root)+'\n'+__import__('subprocess').list2cmdline(argv))
        except (ValueError,OSError) as error:self.preview.setPlainText(t(str(error)))

    def start(self):
        if self.worker or not self.approved.isChecked():return
        allowed=lambda:not self.closed and all(self.win._capabilities.policy['permissions'].get(cap,False) for cap in ('files','code','system'))
        if not allowed():self.status.setText(t('Test uchun fayl, kod va tizim ruxsatlarini yoqing.'));return
        try:root,args,argv=self.values()
        except (ValueError,OSError) as error:self.status.setText(t(str(error)));return
        kind=self.kind.currentData();timeout=self.timeout.value();self.output.clear()
        self.set_busy(True);self.status.setText(t('Test bajarilmoqda…'))
        worker=Worker(self,lambda cancel,progress:run(root,kind,args,cancel,progress,timeout=timeout,allowed=allowed))
        self.worker=worker;worker.progress.connect(self.output.setPlainText)
        def done(result,error):
            if self.closed or self.worker is not worker:return
            self.worker=None;self.set_busy(False)
            if error or result is None:self.status.setText(t(error or 'Bekor qilindi.'));return
            self.output.setPlainText(result['output']);self.last_result=result
            label=t('Testlar o‘tdi.' if result['passed'] else 'Test muvaffaqiyatsiz yoki to‘xtatilgan.')
            self.status.setText(label+f" exit={result['exit_code']} · {result['elapsed_s']:.2f}s · {result['reason']}")
        worker.completed.connect(done);worker.start()

    def set_busy(self,value):
        for widget in (self.root,self.args,self.kind,self.timeout,self.approved,self.start_button):widget.setEnabled(not value)
        if not value:self.approved.setChecked(False)

    def cancel(self):
        if self.worker:self.worker.cancel();self.status.setText(t('Test to‘xtatilmoqda…'))

    def done(self,result):self.closed=True;self.cancel();super().done(result)


def open_runner(win,root=''):
    dialog=TestRunner(win,root);win._test_runner=dialog;dialog.open();return dialog
