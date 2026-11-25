"""Qt-owned worker results; callbacks run in the GUI thread, work never touches widgets."""
import threading
from PyQt6.QtCore import QObject, pyqtSignal


class Worker(QObject):
    completed=pyqtSignal(object,str)
    progress=pyqtSignal(str)

    def __init__(self,parent,operation):
        super().__init__(parent)
        self.cancelled=threading.Event();self.operation=operation
        self.completed.connect(self.deleteLater)

    def start(self):
        def work():
            result,error=None,''
            try:result=self.operation(self.cancelled,self.progress.emit)
            except Exception as exc:error=str(exc) if isinstance(exc,(ValueError,RuntimeError,OSError)) else 'Lokal amal bajarilmadi. Sozlamalarni tekshiring.'
            try:self.completed.emit(None if self.cancelled.is_set() else result,error)
            except RuntimeError:pass
        threading.Thread(target=work,daemon=True,name='brave-local-job').start()

    def cancel(self):self.cancelled.set()
