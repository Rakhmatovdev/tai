"""Internet-loss dialogs and local fallback without changing real networking."""
import asyncio
import errno
import os
from pathlib import Path
import socket
import sys
import threading
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_ollama as fixtures
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QNetworkInformation
from PyQt6.QtTest import QTest

from brave_backend import BackendManager
from core.connectivity import connection_failure
from core.ollama_chat import Settings
from memory import config_manager


class NetworkInfo(QObject):
    reachabilityChanged = pyqtSignal(object)

    def __init__(self, value=QNetworkInformation.Reachability.Online):
        super().__init__()
        self.value = value

    def reachability(self):
        return self.value

    def change(self, value):
        self.value = value
        self.reachabilityChanged.emit(value)


class ErrorTests(unittest.TestCase):
    def test_only_transport_failures_offer_offline(self):
        for error in (ConnectionResetError(), socket.gaierror(),
                      OSError(errno.ENETUNREACH, 'unreachable'),
                      ExceptionGroup('tasks', [ConnectionRefusedError()])):
            self.assertTrue(connection_failure(error))
        for error in (RuntimeError('429 RESOURCE_EXHAUSTED'),
                      RuntimeError('403 invalid API key'),
                      OSError('PortAudio device unavailable'), ValueError('bad input')):
            self.assertFalse(connection_failure(error))


class FallbackTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.LocalUITests.setUpClass.__func__)
    wait_for = fixtures.LocalUITests.wait_for

    def setUp(self):
        fixtures.LocalUITests.setUp(self)
        self.info = NetworkInfo()
        self.network_patch = patch('brave_connectivity.network_information', return_value=self.info)
        self.network_patch.start()
        self.engine_stopped = threading.Event()
        win = self.win
        stopped = self.engine_stopped
        class Adapter:
            def __init__(self): object.__setattr__(self, '_win', win)
            def __getattr__(self, name): return getattr(win, name)
            def __setattr__(self, name, value): setattr(win, name, value)
            def write_log(self, text): win._log.append_log(text)
        class Live:
            def __init__(self, bridge):
                bridge.can_change_chat = lambda: True
                bridge.can_send_text = lambda: True
            async def run(self):
                try: await asyncio.Event().wait()
                finally: stopped.set()
        self.manager = BackendManager(Adapter(), Live)
        win._backend_manager = self.manager
        self.monitor = self.manager.connectivity

    def tearDown(self):
        self.manager.shutdown()
        QTest.qWait(40)
        self.network_patch.stop()
        fixtures.LocalUITests.tearDown(self)

    def cloud(self):
        config_manager._patch_config(chat_provider='gemini', gemini_api_key='test-key',
                                     ollama_autostart=False)
        self.manager.activate('gemini')
        self.wait_for(lambda: not self.manager.busy)

    def disconnect(self):
        self.info.change(QNetworkInformation.Reachability.Disconnected)
        self.assertIsNotNone(self.monitor.dialog)
        self.assertTrue(self.monitor.dialog.isVisible())

    def test_prompt_is_immediate_once_per_outage_and_decline_does_not_switch(self):
        self.cloud()
        self.disconnect()
        dialog = self.monitor.dialog
        self.info.change(QNetworkInformation.Reachability.Local)
        self.assertIs(self.monitor.dialog, dialog)
        self.monitor.later.click()
        self.info.change(QNetworkInformation.Reachability.Disconnected)
        self.assertIsNone(self.monitor.dialog)
        self.assertEqual(self.win._active_provider, 'gemini')
        self.info.change(QNetworkInformation.Reachability.Online)
        self.disconnect()

    def test_accept_verifies_model_stops_busy_cloud_and_preserves_chat_and_draft(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url, 'local', autostart=False).save('gemini')
            self.cloud()
            chat = self.win._features.chat_id
            for role, text in [('user', 'Remember budget 42.'), ('assistant', 'Saved.')]:
                self.win._features.store.append(chat, role, text, '12:00')
            self.win._input.setText('private unsent draft')
            self.win.can_change_chat = lambda: False  # interrupted response
            self.disconnect()
            old_proxy = self.manager.proxy
            self.monitor.accept.click()
            self.wait_for(lambda: self.win._active_provider == 'ollama' and not self.manager.busy)
            self.assertTrue(self.engine_stopped.is_set())
            self.assertIsNone(self.monitor.dialog)
            self.assertEqual(self.win._features.chat_id, chat)
            self.assertEqual(self.win._input.text(), 'private unsent draft')
            self.assertEqual([row['content'] for row in self.win._local_chat.history],
                             ['Remember budget 42.', 'Saved.'])
            self.assertEqual(config_manager.load_api_keys()['chat_provider'], 'ollama')
            self.assertEqual(config_manager.load_api_keys()['gemini_api_key'], 'test-key')
            self.assertNotIn('/api/chat', [path for path, _ in server.requests])
            old_proxy.notify_connection_lost()
            QTest.qWait(20)
            self.assertIsNone(self.monitor.dialog)
            self.info.change(QNetworkInformation.Reachability.Online)
            self.assertEqual(self.win._active_provider, 'ollama')

    def test_missing_model_stays_online_with_retry_and_never_downloads(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url, 'missing', autostart=False).save('gemini')
            self.cloud()
            self.disconnect()
            self.monitor.accept.click()
            self.wait_for(lambda: self.monitor.accept.isEnabled())
            self.assertIn('Model topilmadi', self.monitor.status.text())
            self.assertEqual(self.win._active_provider, 'gemini')
            self.assertEqual(config_manager.load_api_keys()['chat_provider'], 'gemini')
            self.assertNotIn('/api/pull', [path for path, _ in server.requests])

    def test_recovery_or_dismissal_during_model_check_ignores_late_result(self):
        for recover in (True, False):
            with self.subTest(recover=recover), fixtures.FakeOllama() as server:
                Settings(server.url, 'local', autostart=False).save('gemini')
                if self.win._active_provider != 'gemini': self.cloud()
                self.info.change(QNetworkInformation.Reachability.Online)
                self.disconnect()
                release = threading.Event()
                with patch('brave_connectivity.OllamaClient.verify',
                           side_effect=lambda: release.wait(1)):
                    self.monitor.accept.click()
                    if recover: self.info.change(QNetworkInformation.Reachability.Online)
                    else: self.monitor.later.click()
                    release.set()
                    QTest.qWait(100)
                self.assertIsNone(self.monitor.dialog)
                self.assertEqual(self.win._active_provider, 'gemini')
                self.assertEqual(config_manager.load_api_keys()['chat_provider'], 'gemini')

    def test_already_local_and_unknown_reachability_do_not_prompt(self):
        self.info.change(QNetworkInformation.Reachability.Disconnected)
        self.assertIsNone(self.monitor.dialog)
        self.info.change(QNetworkInformation.Reachability.Online)
        self.cloud()
        self.info.change(QNetworkInformation.Reachability.Unknown)
        self.assertIsNone(self.monitor.dialog)

    def test_current_offline_status_is_detected_when_cloud_starts(self):
        self.info.change(QNetworkInformation.Reachability.Disconnected)
        self.cloud()
        self.wait_for(lambda: self.monitor.dialog is not None)

    def test_transport_failure_signal_is_guarded_by_backend_revision(self):
        self.cloud()
        self.monitor.failed(self.manager.revision-1)
        self.assertIsNone(self.monitor.dialog)
        self.manager.proxy.notify_connection_lost()
        self.wait_for(lambda: self.monitor.dialog is not None)
        self.manager.proxy.notify_connection_restored()
        self.wait_for(lambda: self.monitor.dialog is None)

    def test_popup_renders_in_all_themes_and_languages(self):
        import brave_ui
        from brave_i18n import translate
        self.cloud()
        for theme in ('dark', 'light', 'hacker'):
            for lang in ('uz', 'en', 'ru'):
                brave_ui.set_theme(self.win, theme, persist=False)
                brave_ui.set_language(self.win, lang, persist=False)
                self.info.change(QNetworkInformation.Reachability.Online)
                self.disconnect()
                self.assertEqual(self.monitor.dialog.windowTitle(), translate('Internet aloqasi uzildi'))
                self.assertEqual(self.monitor.accept.text(), translate('Offline’ga o‘tish'))
                target = os.environ.get('BRAVE_CONNECTIVITY_PREVIEWS')
                if target:
                    root = Path(target)
                    root.mkdir(parents=True, exist_ok=True)
                    QTest.qWait(20)
                    self.monitor.dialog.grab().save(str(root/f'offline-{theme}-{lang}.png'))


if __name__ == '__main__':
    unittest.main()
