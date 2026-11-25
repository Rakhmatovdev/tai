"""Qt permission boundary for the small offline desktop tool allowlist."""
from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QMessageBox
from brave_i18n import translate as t
from brave_local_jobs import Worker
from core import offline_desktop


def ask_permission(win,name,arguments,cancelled,active):
    if cancelled.is_set() or not active():return False
    from core.access_policy import preview
    box=QMessageBox(QMessageBox.Icon.Question,t('Offline amal'),preview(name,arguments),
                    QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,win)
    box.setDefaultButton(QMessageBox.StandardButton.No)
    timer=QTimer(box);timer.setInterval(25)
    def check():
        if cancelled.is_set() or not active():box.done(QMessageBox.StandardButton.No.value)
    timer.timeout.connect(check);timer.start()
    try:return box.exec()==QMessageBox.StandardButton.Yes.value
    finally:timer.stop();box.deleteLater()


def execute(win, name, arguments, cancelled, active=lambda:True):
    if cancelled.is_set() or not active():raise RuntimeError('Bekor qilindi.')
    policy = win._capabilities.policy
    offline_desktop.validate(name, arguments, policy)
    approved = False
    if name=='open_local_app' or policy['mode']=='ask':
        approved = ask_permission(win,name,arguments,cancelled,active)
        if not approved: raise ValueError('Amal tasdiqlanmadi.')
    offline_desktop.validate(name, arguments, policy)
    if cancelled.is_set() or not active(): raise RuntimeError('Bekor qilindi.')
    if name!='find_local_files':
        try:return offline_desktop.execute(name,arguments,policy,cancelled,approved=approved)
        except OSError as error:raise ValueError('Dastur ochilmadi. O‘rnatilishi va ruxsatlarni tekshiring.') from error
    loop = QEventLoop()
    results = []
    worker = Worker(win,lambda stop,progress:offline_desktop.execute(name,arguments,policy,stop))
    worker.completed.connect(lambda result,error:(results.append((result,error)),loop.quit()))
    timer = QTimer(); timer.setInterval(25)
    def check():
        if (cancelled.is_set() or not active() or not policy['permissions']['files']
                or not offline_desktop.settings().get('enabled')):
            worker.cancel(); loop.quit()
    timer.timeout.connect(check)
    deadline = QTimer(); deadline.setSingleShot(True)
    deadline.timeout.connect(lambda:(worker.cancel(),loop.quit()))
    timer.start(); deadline.start(5000); worker.start()
    loop.exec(); timer.stop(); deadline.stop()
    if not results: raise RuntimeError('Qidiruv bekor qilindi yoki vaqti tugadi.')
    value,error = results[0]
    if error: raise ValueError(error)
    if cancelled.is_set() or not active() or not policy['permissions']['files']: raise RuntimeError('Bekor qilindi.')
    return value
