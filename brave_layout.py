"""Local, debounced window layout preferences; no conversation data is stored."""
from PyQt6.QtCore import QObject, QRect, Qt, QTimer, pyqtSlot
from PyQt6.QtWidgets import QApplication

from core import workspace_store

FILENAME = 'ui-layout.json'


def parse_geometry(value):
    if not isinstance(value, list) or len(value) != 4:
        return None
    if any(type(number) is not int or abs(number) > 1_000_000 for number in value):
        return None
    x, y, width, height = value
    if not (300 <= width <= 20_000 and 250 <= height <= 20_000):
        return None
    return QRect(x, y, width, height)


def fit_geometry(rect, available):
    """Keep a remembered window reachable after a monitor is unplugged."""
    if not available:
        return QRect(rect)
    area = next((area for area in available if area.contains(rect.center())), None)
    if area is None:
        area = max(available, key=lambda candidate: max(0, candidate.intersected(rect).width()) * max(0, candidate.intersected(rect).height()))
    width, height = min(rect.width(), area.width()), min(rect.height(), area.height())
    x = max(area.left(), min(rect.x(), area.right()-width+1))
    y = max(area.top(), min(rect.y(), area.bottom()-height+1))
    return QRect(x, y, width, height)


class LayoutState(QObject):
    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.ready = False
        saved = workspace_store.read(FILENAME, {})
        self.saved = saved if isinstance(saved, dict) and type(saved.get('version')) is int and saved.get('version') == 1 else {}
        self.remember = self.saved.get('remember') is not False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(700)
        self.timer.timeout.connect(self.flush)
        QApplication.instance().aboutToQuit.connect(self.save_on_quit)

    def restore(self):
        from brave_chat import set_chat_focus
        self.timer.stop()
        self.ready = False
        if self.remember:
            set_chat_focus(self.win, self.saved.get('focus') is True, persist=False)
            rect = parse_geometry(self.saved.get('geometry'))
            if rect is not None:
                areas = [screen.availableGeometry() for screen in QApplication.screens()]
                self.apply_geometry(fit_geometry(rect, areas))
            if self.saved.get('maximized') is True:
                self.win.setWindowState((self.win.windowState() & ~Qt.WindowState.WindowFullScreen & ~Qt.WindowState.WindowMinimized) | Qt.WindowState.WindowMaximized)
        else:
            set_chat_focus(self.win, False, persist=False)
        QTimer.singleShot(0, self.finish_restore)

    def finish_restore(self):
        if self.remember and parse_geometry(self.saved.get('geometry')) is not None and not self.win.isMaximized() and not self.win.isFullScreen():
            frame = self.win.frameGeometry()
            fitted = fit_geometry(frame, [screen.availableGeometry() for screen in QApplication.screens()])
            if frame.topLeft() != fitted.topLeft():
                self.win.move(fitted.topLeft())
        self.ready = True
        self.sync_settings()

    def apply_geometry(self, rect):
        from ui import _MIN_W, _MIN_H
        # A smaller work area must not strand the remembered title bar outside
        # the display. Normal desktop screens retain the existing minimum size.
        self.win.setMinimumSize(min(_MIN_W, rect.width()), min(_MIN_H, rect.height()))
        self.win.setGeometry(rect)

    def schedule(self):
        if self.ready and not self.win.isMinimized():
            self.timer.start()

    def snapshot(self):
        data = {'version': 1, 'remember': self.remember}
        if self.remember:
            normal = self.win.normalGeometry() if self.win.isMaximized() or self.win.isFullScreen() else self.win.geometry()
            if not normal.isValid():
                normal = self.win.geometry()
            data.update(geometry=[normal.x(), normal.y(), normal.width(), normal.height()],
                maximized=self.win.isMaximized() or (self.win.isFullScreen() and getattr(self.win, '_pre_fullscreen_maximized', False)),
                focus=bool(getattr(self.win, '_chat_focus', False)))
        return data

    def flush(self, force=False):
        if not self.ready and not force:
            return False
        self.timer.stop()
        data = self.snapshot()
        try:
            workspace_store.write(FILENAME, data)
        except OSError:
            return False
        self.saved = data
        return True

    @pyqtSlot()
    def save_on_quit(self):
        self.flush(force=True)

    def set_remember(self, enabled):
        self.remember = bool(enabled)
        self.flush(force=True)
        self.sync_settings()

    def reset(self):
        from brave_chat import set_chat_focus
        from ui import _DEFAULT_W, _DEFAULT_H
        self.timer.stop()
        self.ready = False
        area = self.win.screen().availableGeometry()
        rect = QRect(0, 0, min(_DEFAULT_W, area.width()-32), min(_DEFAULT_H, area.height()-32))
        rect.moveCenter(area.center())
        self.win.showNormal()
        self.apply_geometry(fit_geometry(rect, [area]))
        set_chat_focus(self.win, False, persist=False)
        self.ready = True
        self.flush()
        self.sync_settings()

    def sync_settings(self):
        settings = getattr(self.win, '_quick_drawer', None)
        if hasattr(settings, 'sync_layout'):
            settings.sync_layout()
