"""Event-driven internet-loss prompt and verified, user-selected local fallback."""
import threading

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtNetwork import QNetworkInformation
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from brave_i18n import translate as t
from core.ollama_chat import Settings, OllamaClient
from core.ollama_service import ensure_server


def network_information():
    try:
        if QNetworkInformation.instance() is None:
            QNetworkInformation.loadDefaultBackend()
        return QNetworkInformation.instance()
    except RuntimeError:
        return None


class OfflineFallback(QObject):
    cloud_failed = pyqtSignal(int)
    cloud_restored = pyqtSignal(int)
    checked = pyqtSignal(int, object, str)

    def __init__(self, manager):
        super().__init__(manager)
        self.manager = manager
        self.dialog = None
        self.offline = False
        self.offered = False
        self.closed = False
        self.attempt = 0
        self.cancelled = threading.Event()
        self.info = network_information()
        self.cloud_failed.connect(self.failed)
        self.cloud_restored.connect(self.restored)
        self.checked.connect(self.prepared)
        if self.info is not None:
            self.info.reachabilityChanged.connect(self.reachability_changed)
            QTimer.singleShot(0, self.read_current)

    def is_cloud(self):
        return (not self.closed and not self.manager.closed
                and getattr(self.manager.win, '_active_provider', None) == 'gemini'
                and self.manager.pending in (None, 'gemini'))

    def read_current(self):
        if not self.closed and self.info is not None:
            self.reachability_changed(self.info.reachability())

    def reachability_changed(self, value):
        if self.closed:
            return
        if value == QNetworkInformation.Reachability.Online:
            self.recovered()
        elif value in (QNetworkInformation.Reachability.Disconnected,
                       QNetworkInformation.Reachability.Local,
                       QNetworkInformation.Reachability.Site):
            self.offline = True
            self.offer()
        # Unknown is not evidence that the internet is disconnected.

    def failed(self, revision):
        if revision == self.manager.revision and self.is_cloud():
            self.offline = True
            self.offer()

    def restored(self, revision):
        if revision == self.manager.revision and self.is_cloud():
            self.recovered()

    def recovered(self):
        self.offline = False
        self.offered = False
        self.dismiss()

    def provider_changed(self, selected):
        if selected != 'gemini':
            self.dismiss()
        else:
            self.offered = False
            QTimer.singleShot(0, self.check_provider)

    def check_provider(self):
        if not self.is_cloud():
            return
        self.read_current()
        if self.offline:
            self.offer()

    def offer(self):
        if not self.is_cloud() or not self.offline or self.offered or self.dialog is not None:
            return
        from brave_ui import colors, font, button_style
        c = colors()
        self.offered = True
        dialog = QDialog(self.manager.win)
        self.dialog = dialog
        dialog.setObjectName('OfflineFallbackDialog')
        dialog.setWindowTitle(t('Internet aloqasi uzildi'))
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setFont(font(10))
        dialog.setMinimumWidth(440)
        dialog.setStyleSheet(f'QDialog {{background:{c.PANEL};color:{c.TEXT};}} QLabel {{color:{c.TEXT};background:transparent;}}')
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(16)
        title = QLabel(t('Offline rejimga o‘tamizmi?'))
        title.setFont(font(14, True))
        layout.addWidget(title)
        body = QLabel(t('Gemini bilan aloqa uzildi. Ollama orqali internetsiz davom etishingiz mumkin. Suhbat va qoralamangiz saqlanadi.'))
        body.setWordWrap(True)
        body.setMaximumWidth(480)
        layout.addWidget(body)
        self.status = QLabel('')
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setMaximumWidth(480)
        layout.addWidget(self.status)
        row = QHBoxLayout()
        layout.addLayout(row)
        self.later = QPushButton(t('Hozir emas'))
        self.later.setStyleSheet(button_style())
        self.later.clicked.connect(dialog.reject)
        row.addWidget(self.later)
        self.accept = QPushButton(t('Offline’ga o‘tish'))
        self.accept.setStyleSheet(button_style(accent=True))
        self.accept.setDefault(True)
        self.accept.clicked.connect(self.prepare)
        row.addWidget(self.accept)
        dialog.finished.connect(lambda _result: self.dialog_closed(dialog))
        dialog.open()

    def prepare(self):
        if self.dialog is None or not self.is_cloud() or not self.accept.isEnabled():
            return
        try:
            settings = Settings.read()
        except ValueError as exc:
            self.status.setText(t(str(exc)))
            return
        self.attempt += 1
        attempt = self.attempt
        self.cancelled.set()
        self.cancelled = cancelled = threading.Event()
        self.accept.setEnabled(False)
        self.status.setText(t('Ollama va lokal model tekshirilmoqda…'))
        def work():
            error = ''
            client = None
            try:
                if not ensure_server(settings.url, enabled=settings.autostart, cancelled=cancelled):
                    return
                if cancelled.is_set():
                    return
                client = OllamaClient(settings)
                client.verify()
            except (ValueError, RuntimeError) as exc:
                error = str(exc)
            except Exception:
                error = 'Ollama lokal modelini tekshirib bo‘lmadi. AI model sozlamalarini tekshiring.'
            finally:
                if client is not None:
                    client.close()
            if not cancelled.is_set():
                try:
                    self.checked.emit(attempt, settings, error)
                except RuntimeError:
                    pass
        threading.Thread(target=work, daemon=True, name='brave-offline-check').start()

    def prepared(self, attempt, settings, error):
        if (attempt != self.attempt or self.dialog is None or not self.is_cloud()
                or self.cancelled.is_set()):
            return
        if not error:
            try:
                settings.save('ollama')
                if self.manager.switch('ollama', interrupt=True):
                    self.dismiss()
                    return
                error = 'Offline rejimga o‘tib bo‘lmadi. Qayta urinib ko‘ring.'
            except (ValueError, OSError):
                error = 'Sozlamalarni saqlab bo‘lmadi.'
        self.status.setText(t(error))
        self.accept.setText(t('Qayta urinish'))
        self.accept.setEnabled(True)

    def dialog_closed(self, dialog):
        if self.dialog is dialog:
            self.dialog = None
            self.attempt += 1
            self.cancelled.set()
        dialog.deleteLater()

    def dismiss(self):
        self.cancelled.set()
        if self.dialog is not None:
            self.dialog.reject()

    def shutdown(self):
        self.closed = True
        self.dismiss()
        if self.info is not None:
            try:
                self.info.reachabilityChanged.disconnect(self.reachability_changed)
            except (TypeError, RuntimeError):
                pass
