"""Offline protocol and Qt integration checks; no real models or cloud calls."""
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock, patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from core.ollama_chat import (Settings, OllamaClient, PROFILES, bounded_messages,
                              local_url, local_model, provider)
from memory import config_manager


class FakeOllama:
    def __enter__(self):
        self.requests = []
        self.names = ['local:latest', 'other:small', 'remote:cloud']
        self.show = {}
        self.running = []
        self.catalog_rows = None
        self.before_headers = {}
        self.overrides = {}
        self.chunks = [{'message': {'content': 'Salom '}, 'done': False},
                       {'message': {'content': 'dunyo'}, 'done': True}]
        self.pause = None
        self.pull_chunks=[{'status':'pulling manifest'},{'status':'pulling layer','total':100,'completed':40},{'status':'success'}]
        self.chat_handler=None
        self.post_overrides={}
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                owner.requests.append((self.path, None))
                if self.path in owner.before_headers:
                    owner.before_headers[self.path].wait(3)
                status, data, headers = owner.overrides.get(self.path, (200,
                    {'models': owner.running} if self.path == '/api/ps' else
                    {'models': owner.catalog_rows if owner.catalog_rows is not None else [{'name': n} for n in owner.names]}, {}))
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.end_headers()
                try:
                    self.wfile.write(json.dumps(data).encode())
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
                owner.requests.append((self.path, payload))
                if self.path in owner.before_headers:
                    owner.before_headers[self.path].wait(3)
                if self.path in owner.post_overrides:
                    status,data,headers=owner.post_overrides[self.path]
                    self.send_response(status)
                    for key,value in headers.items():self.send_header(key,value)
                    self.end_headers()
                    try:self.wfile.write(json.dumps(data).encode())
                    except OSError:pass
                    return
                self.send_response(200)
                self.end_headers()
                if self.path == '/api/show':
                    try:
                        self.wfile.write(json.dumps(owner.show).encode())
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        pass
                elif self.path in ('/api/chat','/api/pull'):
                    try:
                        chunks=owner.pull_chunks if self.path=='/api/pull' else owner.chat_handler(payload) if owner.chat_handler else owner.chunks
                        for index, chunk in enumerate(chunks):
                            self.wfile.write(chunk if isinstance(chunk, bytes) else json.dumps(chunk).encode()+b'\n')
                            self.wfile.flush()
                            if index == 0 and owner.pause:
                                owner.pause.wait(3)
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        pass
                else:
                    try:self.wfile.write(b'{"done":true}')
                    except OSError:pass
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        return self

    def __exit__(self, *args):
        if self.pause:
            self.pause.set()
        for event in self.before_headers.values():
            event.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)


class TransportTests(unittest.TestCase):
    def test_only_loopback_urls_and_local_models(self):
        for url in ['http://localhost:11434', 'http://127.0.0.1:1/', 'http://[::1]:11434']:
            self.assertEqual(local_url(url), url.rstrip('/'))
        for url in [None, 'http://[', 'http://example.com', 'https://localhost',
                    'http://192.168.1.10', 'http://localhost.evil', 'http://user@localhost',
                    'http://localhost/a', 'http://localhost?x=1', 'http://localhost:70000']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                local_url(url)
        with self.assertRaises(ValueError):
            local_model('remote:cloud')
        self.assertEqual(provider({}), 'gemini')
        self.assertEqual(provider({'llm_provider': 'ollama'}), 'gemini')
        self.assertEqual(provider({'chat_provider': 'ollama'}), 'ollama')

    def test_streaming_profiles_bound_memory_and_do_not_force_gpu(self):
        with FakeOllama() as server:
            for name, profile in PROFILES.items():
                client = OllamaClient(Settings(server.url, 'local', name))
                try:
                    self.assertFalse(client.session.trust_env)
                    reply = ''.join(client.stream([{'role': 'user', 'content': 'hi'}], threading.Event()))
                    self.assertEqual(reply, 'Salom dunyo')
                finally:
                    client.close()
                payload = server.requests[-1][1]
                self.assertEqual(payload['keep_alive'], profile['keep_alive'])
                self.assertEqual(payload['options'], {key: profile[key] for key in ('num_ctx', 'num_predict')})
                self.assertNotIn('tools', payload)
                # Legacy metadata is unknown: do not force an unsupported option.
                self.assertNotIn('think', payload)

    def test_exact_model_tag_and_remote_metadata_are_checked(self):
        with FakeOllama() as server:
            client = OllamaClient(Settings(server.url, 'other:large'))
            with self.assertRaises(ValueError):
                list(client.stream([], threading.Event()))
            self.assertNotIn('/api/chat', [path for path, _ in server.requests])
            client.close()
            server.show = {'remote_host': 'https://ollama.com', 'remote_model': 'remote'}
            client = OllamaClient(Settings(server.url, 'local'))
            with self.assertRaises(ValueError):
                client.verify()
            self.assertNotIn('/api/chat', [path for path, _ in server.requests])
            client.close()

    def test_truncated_stream_is_not_a_completed_answer(self):
        with FakeOllama() as server:
            server.chunks = [{'message': {'content': 'partial'}, 'done': False}]
            client = OllamaClient(Settings(server.url, 'local'))
            with self.assertRaises(RuntimeError):
                list(client.stream([], threading.Event()))
            client.close()

    def test_cancelled_request_never_starts_generation(self):
        with FakeOllama() as server:
            cancelled = threading.Event()
            cancelled.set()
            client = OllamaClient(Settings(server.url, 'local'))
            self.assertEqual(list(client.stream([], cancelled)), [])
            self.assertEqual(server.requests, [])
            client.close()

    def test_unload_is_explicit_and_does_not_generate(self):
        with FakeOllama() as server:
            client = OllamaClient(Settings(server.url, 'local'))
            client.unload()
            self.assertEqual(server.requests, [('/api/generate', {'model': 'local', 'keep_alive': 0, 'stream': False})])
            client.close()

    def test_history_keeps_recent_complete_turns_and_current_message(self):
        history = [{'role': role, 'content': str(i)+'x'*200} for i in range(12)
                   for role in ('user', 'assistant')]
        result = bounded_messages(history, 'current', 'economy')
        self.assertEqual(result[-1], {'role': 'user', 'content': 'current'})
        self.assertEqual([row['role'] for row in result[1:-1]], ['user', 'assistant']*2)
        self.assertTrue(result[1]['content'].startswith('10'))
        self.assertLessEqual(sum(len(row['content']) for row in result[1:]), PROFILES['economy']['chars'])
        self.assertEqual(len(history), 24)
        with self.assertRaises(ValueError):
            bounded_messages([], 'a'*7000, 'quality')

    def test_redirects_are_not_followed(self):
        client = OllamaClient(Settings())
        response = Mock(is_redirect=True)
        with patch.object(client.session, 'request', return_value=response) as send:
            with self.assertRaises(ValueError):
                client.models()
        self.assertFalse(send.call_args.kwargs['allow_redirects'])
        client.close()


from PyQt6.QtCore import QCoreApplication, QEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton
import ui
import brave_ui
from core import workspace_store
from brave_local_chat import LocalChat, start_backend
from brave_settings import open_settings


class LocalUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = Path(self.temp.name)/'settings.json'
        self.config.write_text(json.dumps({'chat_provider': 'ollama', 'ollama_model': 'local',
                                          'ollama_url': 'http://127.0.0.1:1',
                                          'access_policy': {'permissions': {'network': True, 'microphone': True, 'screen': True, 'camera': True, 'files': True, 'code': True, 'system': True}}}), encoding='utf-8')
        self.patches = [patch.object(ui, 'API_FILE', self.config),
                        patch.object(config_manager, 'CONFIG_FILE', self.config),
                        patch.object(workspace_store, 'directory', return_value=Path(self.temp.name)),
                        patch('brave_local_chat.ensure_server', return_value=True),
                        patch.object(ui.MainWindow, '_check_autostart', return_value=False)]
        for item in self.patches:
            item.start()
        self.win = ui.MainWindow('')
        self.win.show()
        self.app.processEvents()

    def tearDown(self):
        runtime = getattr(self.win, '_local_chat', None)
        if runtime:
            runtime.shutdown()
        self.win.close()
        self.win.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def wait_for(self, predicate, timeout=4000):
        deadline = time.monotonic()+timeout/1000
        while time.monotonic() < deadline and not predicate():
            QTest.qWait(15)
        self.assertTrue(predicate())

    def start_local(self):
        self.win._runtime_started = True
        self.win._local_chat = LocalChat(self.win)
        return self.win._local_chat

    def test_local_startup_needs_no_key_and_never_constructs_gemini(self):
        cloud = Mock()
        start_backend(type('UI', (), {'_win': self.win})(), cloud)
        self.wait_for(lambda: hasattr(self.win, '_local_chat'))
        cloud.assert_not_called()
        self.assertTrue(self.win._ready)
        self.assertTrue(self.win._text_only)
        self.assertTrue(self.win._reply_mode.isEnabled())
        self.assertTrue(self.win._mute_btn.isEnabled())
        self.assertFalse(self.win._wake_btn.isEnabled())
        self.assertTrue(self.win._ptt_btn.isEnabled())
        self.assertIsNone(self.win.on_audio_device_change)

    def test_first_run_offline_button_configures_without_a_gemini_key(self):
        self.config.write_text('{}', encoding='utf-8')
        self.win._ready = False
        self.win._show_setup()
        button = next(b for b in self.win._overlay.findChildren(QPushButton)
                      if 'Ollama' in b.text())
        button.click()
        form = self.win._quick_drawer.forms['ai']
        self.assertEqual(form.provider.currentData(), 'ollama')
        form.model.setEditText('local')
        form.url.setText('http://127.0.0.1:1')
        form.apply()
        self.assertTrue(self.win._ready)
        self.assertTrue(self.win._check_config())
        self.assertNotIn('gemini_api_key', json.loads(self.config.read_text()))
        cloud = Mock()
        start_backend(type('UI', (), {'_win': self.win})(), cloud)
        self.wait_for(lambda: hasattr(self.win, '_local_chat'))
        cloud.assert_not_called()

    def test_gemini_startup_still_selects_live_engine(self):
        self.config.write_text(json.dumps({'gemini_api_key': 'test-key', 'os_system': 'windows'}), encoding='utf-8')
        called = threading.Event()
        class Live:
            async def run(self):
                called.set()
        factory = Mock(return_value=Live())
        start_backend(type('UI', (), {'_win': self.win})(), factory)
        self.wait_for(called.is_set)
        factory.assert_called_once()
        self.assertEqual(self.win._active_provider, 'gemini')
        self.assertFalse(hasattr(self.win, '_local_chat'))

    def test_streaming_saves_exactly_one_final_answer_and_keeps_draft(self):
        with FakeOllama() as server:
            Settings(server.url, 'local').save('ollama')
            runtime = self.start_local()
            self.win._input.setText('hello')
            self.win._send()
            self.win._input.setText('next draft')
            self.wait_for(lambda: not runtime.busy and len(runtime.history) == 2)
            rows = self.win._features.store.messages(self.win._features.chat_id)
            self.assertEqual([(r[0], r[1]) for r in rows], [('user', 'hello'), ('assistant', 'Salom dunyo')])
            self.assertEqual(self.win._input.text(), 'next draft')
            self.assertFalse(getattr(self.win._log, '_stream_row', None))
            self.assertTrue(self.win.can_change_chat())

    def test_cancel_immediately_discards_partial_answer_and_unblocks_chat(self):
        with FakeOllama() as server:
            server.pause = threading.Event()
            Settings(server.url, 'local').save('ollama')
            runtime = self.start_local()
            self.win._input.setText('hello')
            self.win._send()
            self.wait_for(lambda: bool(getattr(self.win._log, '_stream_row', None)))
            started = time.monotonic()
            self.win._features.cancel()
            self.assertLess(time.monotonic()-started, .25)
            self.assertTrue(self.win.can_change_chat())
            self.assertFalse(self.win._features.cancel_pending)
            self.assertIsNone(self.win._log._stream_row)
            server.pause.set()
            self.wait_for(lambda: not runtime.busy)
            self.assertEqual(runtime.history, [])
            self.assertEqual([r[0] for r in self.win._features.store.messages(self.win._features.chat_id)], ['user'])
            self.assertTrue(self.win.can_send_text())

    def test_cancel_before_http_headers_does_not_wait_for_server(self):
        with FakeOllama() as server:
            server.before_headers['/api/chat'] = threading.Event()
            Settings(server.url, 'local').save('ollama')
            runtime = self.start_local()
            self.win._input.setText('hello')
            self.win._send()
            self.wait_for(lambda: any(path == '/api/chat' for path, _ in server.requests))
            job = runtime.job
            self.win._do_interrupt()
            self.assertFalse(runtime.busy)
            self.assertTrue(job.ended)
            self.assertIsNone(job.reply)
            self.assertFalse(server.before_headers['/api/chat'].is_set())
            self.assertTrue(self.win.can_change_chat())
            self.assertEqual(runtime.history, [])

    def test_cancel_during_model_verification_prevents_generation(self):
        with FakeOllama() as server:
            server.before_headers['/api/tags'] = threading.Event()
            Settings(server.url, 'local').save('ollama')
            runtime = self.start_local()
            runtime.submit('hello', [])
            self.wait_for(lambda: bool(server.requests))
            self.assertEqual(runtime.phase, 'checking')
            runtime.cancel()
            server.before_headers['/api/tags'].set()
            QTest.qWait(80)
            self.assertFalse(runtime.busy)
            self.assertNotIn('/api/chat', [path for path, _ in server.requests])

    def test_late_cancelled_response_cannot_enter_new_conversation(self):
        with FakeOllama() as server:
            old_pause = threading.Event()
            server.pause = old_pause
            Settings(server.url, 'local').save('ollama')
            runtime = self.start_local()
            self.win._input.setText('old question')
            self.win._send()
            self.wait_for(lambda: bool(getattr(self.win._log, '_stream_row', None)))
            self.win._do_interrupt()
            self.assertTrue(self.win._features.switch_chat())
            server.pause = None
            server.chunks = [{'message': {'content': 'new answer'}, 'done': True}]
            self.win._input.setText('new question')
            self.win._send()
            self.wait_for(lambda: len(runtime.history) == 2)
            old_pause.set()
            QTest.qWait(80)
            self.assertEqual([r[1] for r in self.win._features.store.messages(self.win._features.chat_id)], ['new question', 'new answer'])

    def test_cold_warm_and_streaming_progress_reuse_existing_task_panel(self):
        from brave_i18n import translate
        for loaded in (False, True):
            with self.subTest(loaded=loaded), FakeOllama() as server:
                server.running = [{'name': 'local:latest'}] if loaded else []
                server.before_headers['/api/chat'] = threading.Event()
                server.pause = threading.Event()
                Settings(server.url, 'local').save('ollama')
                runtime = getattr(self.win, '_local_chat', None) or self.start_local()
                runtime.submit('hello', [])
                self.assertEqual(runtime.phase, 'checking')
                phase = 'waiting' if loaded else 'loading'
                self.wait_for(lambda: runtime.phase == phase)
                self.assertEqual(self.win._task_detail.text(), 'local')
                before = self.win._task_label.text()
                self.win._features.refresh()
                self.assertEqual(self.win._task_label.text(), before)
                server.before_headers['/api/chat'].set()
                self.wait_for(lambda: runtime.phase == 'replying')
                self.assertEqual(self.win._task_label.text(), translate('Javob kelmoqda…'))
                server.pause.set()
                self.wait_for(lambda: not runtime.busy)

    def test_first_token_timeout_aborts_request_and_restores_draft(self):
        from brave_ollama_request import ChatRequest
        with FakeOllama() as server, patch.object(ChatRequest, 'FIRST_TOKEN_MS', 60):
            server.before_headers['/api/chat'] = threading.Event()
            Settings(server.url, 'local').save('ollama')
            runtime = self.start_local()
            self.win._input.setText('restore this')
            self.win._send()
            self.wait_for(lambda: not runtime.busy and self.win._input.text() == 'restore this')
            self.assertEqual(runtime.history, [])
            self.assertIsNone(runtime.job)
            self.assertFalse(server.before_headers['/api/chat'].is_set())

    def test_stream_idle_timeout_discards_incomplete_answer(self):
        from brave_ollama_request import ChatRequest
        with FakeOllama() as server, patch.object(ChatRequest, 'IDLE_MS', 60):
            server.pause = threading.Event()
            Settings(server.url, 'local').save('ollama')
            runtime = self.start_local()
            self.win._input.setText('restore idle')
            self.win._send()
            self.wait_for(lambda: not runtime.busy and self.win._input.text() == 'restore idle')
            self.assertEqual(runtime.history, [])
            self.assertIsNone(getattr(self.win._log, '_stream_row', None))

    def test_failed_request_restores_input_and_does_not_pollute_model_context(self):
        with FakeOllama() as server:
            server.names = []
            Settings(server.url, 'local').save('ollama')
            runtime = self.start_local()
            self.win._input.setText('keep me')
            self.win._send()
            self.wait_for(lambda: not runtime.busy and self.win._input.text() == 'keep me')
            self.assertEqual(runtime.history, [])
            self.assertIsNone(getattr(self.win._log, '_stream_row', None))

    def test_attachment_and_long_prompt_are_rejected_without_consuming_draft(self):
        runtime = self.start_local()
        self.win._input.setText('draft')
        with patch.object(self.win._drop_zone, 'current_files', return_value=['private.txt']):
            self.win._send()
        self.assertEqual(self.win._input.text(), 'draft')
        self.win._input.setText('x'*7000)
        self.win._send()
        self.assertEqual(len(self.win._input.text()), 7000)
        self.assertFalse(runtime.busy)
        self.assertEqual(self.win._features.store.messages(self.win._features.chat_id), [])

    def test_history_switch_restores_bounded_context_and_resets_new_chat(self):
        runtime = self.start_local()
        store = self.win._features.store
        store.append('old', 'user', 'before', '12:00')
        store.append('old', 'assistant', 'answer', '12:00')
        store.append('old', 'user', 'failed', '12:01')
        self.assertTrue(self.win._features.switch_chat('old'))
        self.assertEqual([r['content'] for r in runtime.history], ['before', 'answer'])
        self.app.processEvents()
        self.assertTrue(self.win._features.switch_chat())
        self.assertEqual(runtime.history, [])

    def test_settings_save_preserves_credentials_and_gemini_requires_restart(self):
        self.start_local()
        open_settings(self.win, 'ai')
        form = self.win._quick_drawer.forms['ai']
        form.profile.setCurrentIndex(form.profile.findData('economy'))
        form.apply()
        self.assertEqual(Settings.read().profile, 'economy')
        self.assertEqual(self.win.hud._tmr.interval(), 50)
        form.provider.setCurrentIndex(form.provider.findData('gemini'))
        form.key.setText('test-key-not-real')
        form.apply()
        cfg = json.loads(self.config.read_text())
        self.assertEqual(cfg['chat_provider'], 'gemini')
        self.assertEqual(cfg['gemini_api_key'], 'test-key-not-real')
        self.assertEqual(cfg['ollama_profile'], 'economy')
        self.assertTrue(cfg['os_system'])
        self.assertEqual(self.win._active_provider, 'ollama')
        self.assertIn('qayta oching', form.status.text())
        self.assertEqual(form.key.text(), '')

    def test_automatic_budget_reaches_requests_and_recovers_without_oscillation(self):
        from core.ollama_resources import Resources, GIB
        with FakeOllama() as server:
            Settings(server.url, 'local', 'auto', autostart=False).save('ollama')
            snapshot = {'value': Resources(2*GIB, 16*GIB)}
            with patch('brave_local_chat.sample_resources', side_effect=lambda: snapshot['value']):
                runtime = self.start_local()
                for index in range(3):
                    if index == 1:
                        snapshot['value'] = Resources(12*GIB, 16*GIB)
                    if index == 2:
                        runtime.profile_policy.changed_at -= 61
                    self.win._input.setText(f'question {index}')
                    self.win._send()
                    self.wait_for(lambda: len(runtime.history) == 2*(index+1))
                calls = [body for path, body in server.requests if path == '/api/chat']
                self.assertEqual([body['options']['num_ctx'] for body in calls], [2048, 2048, 4096])
                self.assertEqual([body['keep_alive'] for body in calls], [0, 0, '5m'])
                self.assertEqual(Settings.read().profile, 'auto')
                self.assertEqual(runtime.diagnostics()['profile'], 'balanced')

    def test_manual_profile_is_not_changed_by_resource_pressure(self):
        with FakeOllama() as server:
            Settings(server.url, 'local', 'quality', autostart=False).save('ollama')
            with patch('brave_local_chat.sample_resources') as sample, patch('brave_local_chat.ensure_server') as start:
                runtime = self.start_local()
                self.win._input.setText('manual quality')
                self.win._send()
                self.wait_for(lambda: len(runtime.history) == 2)
                sample.assert_not_called()
                start.assert_not_called()
                body = next(body for path, body in server.requests if path == '/api/chat')
                self.assertEqual(body['options']['num_ctx'], 8192)

    def test_cancel_during_automatic_startup_never_generates_or_blocks_ui(self):
        with FakeOllama() as server:
            Settings(server.url, 'local', autostart=True).save('ollama')
            entered = threading.Event()
            def waiting(url, cancelled, stage):
                stage('starting')
                entered.set()
                cancelled.wait(2)
                return False
            runtime = self.start_local()
            with patch('brave_local_chat.ensure_server', side_effect=waiting):
                self.win._input.setText('cancel startup')
                self.win._send()
                self.wait_for(lambda: entered.is_set() and runtime.phase == 'starting')
                self.win._features.cancel()
                self.assertFalse(runtime.busy)
                self.assertTrue(self.win.can_send_text())
                self.assertFalse(self.win._features.cancel_pending)
                QTest.qWait(80)
                self.assertNotIn('/api/chat', [path for path, _ in server.requests])
                self.assertEqual(runtime.history, [])

    def test_preparation_timeout_restores_text_and_ignores_late_startup(self):
        with FakeOllama() as server:
            Settings(server.url, 'local', autostart=True).save('ollama')
            def waiting(url, cancelled, stage):
                stage('starting')
                cancelled.wait(2)
                return False
            runtime = self.start_local()
            with patch('brave_local_chat.ensure_server', side_effect=waiting):
                self.win._input.setText('restore preparation')
                self.win._send()
                self.wait_for(lambda: runtime.phase == 'starting')
                runtime.prepare_timer.start(30)
                self.wait_for(lambda: not runtime.busy and self.win._input.text() == 'restore preparation')
                self.assertFalse(runtime.cancelled.is_set())
                self.assertEqual(runtime.history, [])
                QTest.qWait(80)
                self.assertNotIn('/api/chat', [path for path, _ in server.requests])

    def test_auto_settings_save_and_translate_without_starting_when_disabled(self):
        from core.ollama_resources import Resources, GIB
        from brave_i18n import translate
        with FakeOllama() as server:
            Settings(server.url, 'local', 'balanced', autostart=False).save('ollama')
            with patch('brave_ai_settings.sample_resources', return_value=Resources(2*GIB, 16*GIB)), \
                    patch('brave_ai_settings.ensure_server') as start:
                open_settings(self.win, 'ai')
                form = self.win._quick_drawer.forms['ai']
                form.profile.setCurrentIndex(form.profile.findData('auto'))
                self.wait_for(lambda: form.resources is not None and not form.busy)
                form.apply()
                self.assertEqual(Settings.read().profile, 'auto')
                self.assertFalse(Settings.read().autostart)
                self.assertIn('2.0 GB', form.resource_info.text())
                for lang in ('en', 'ru', 'uz'):
                    brave_ui.set_language(self.win, lang, persist=False)
                    self.assertEqual(form.autostart.text(), translate('Ollama’ni avtomatik ishga tushirish'))
                    self.assertIn(translate('Tejamkor'), form.resource_info.text())
                start.assert_not_called()

    def test_local_diagnostics_never_probe_cloud_or_audio(self):
        from brave_diagnostics import collect_checks
        with FakeOllama() as server:
            Settings(server.url, 'local').save('ollama')
            network, audio = Mock(), Mock()
            results = collect_checks({'provider': 'ollama'}, network, audio)
            network.assert_not_called()
            audio.assert_not_called()
            self.assertEqual(results[0][1], 'good')

    def test_local_chat_is_available_with_internet_permission_off(self):
        self.win._capabilities.policy['permissions']['network'] = False
        self.start_local()
        self.assertTrue(self.win.can_send_text())
        self.assertTrue(self.win.can_change_chat())

    def test_settings_probe_lists_installed_models_without_loading_them(self):
        with FakeOllama() as server:
            Settings(server.url, 'local').save('ollama')
            open_settings(self.win, 'ai')
            form = self.win._quick_drawer.forms['ai']
            form.probe(False)
            self.wait_for(lambda: not form.busy)
            self.assertEqual([form.model.itemText(i) for i in range(form.model.count())], ['local:latest', 'other:small'])
            self.assertNotIn('/api/chat', [path for path, _ in server.requests])
            self.assertIn('tayyor', form.status.text())

    def test_model_picker_loads_automatically_and_preserves_choice_until_save(self):
        with FakeOllama() as server:
            server.catalog_rows = [
                {'name': 'local:latest', 'size': 2*1024**3, 'details': {'parameter_size': '3B', 'quantization_level': 'Q4_K_M'}},
                {'name': 'other:small'}, {'name': 'remote:cloud'}]
            Settings(server.url, 'local').save('ollama')
            original = self.config.read_text()
            open_settings(self.win, 'ai')
            form = self.win._quick_drawer.forms['ai']
            self.wait_for(lambda: form.catalog_url == server.url and not form.busy)
            self.assertEqual(self.config.read_text(), original)
            self.assertEqual(form.model.currentText(), 'local:latest')
            self.assertIn('2.0 GB', form.model_info.text())
            self.assertIn('Q4_K_M', form.model_info.text())
            self.assertEqual(form.model.count(), 2)
            form.model.setCurrentIndex(form.model.findText('other:small'))
            self.assertEqual(Settings.read().model, 'local')
            form.apply()
            self.assertEqual(Settings.read().model, 'other:small')
            self.assertNotIn('/api/chat', [path for path, _ in server.requests])

    def test_picker_refresh_works_with_missing_model_name_and_empty_inventory(self):
        with FakeOllama() as server:
            Settings(server.url, 'local').save('ollama')
            open_settings(self.win, 'ai')
            form = self.win._quick_drawer.forms['ai']
            form.model.setEditText('')
            form.refresh_models()
            self.wait_for(lambda: form.catalog_url == server.url and not form.busy)
            self.assertEqual(form.model.count(), 2)
            server.names = []
            form.refresh_models()
            self.wait_for(lambda: not form.busy)
            self.assertEqual(form.model.count(), 0)
            self.assertIn('topilmadi', form.status.text())

    def test_selected_model_is_used_next_request_without_restart(self):
        with FakeOllama() as server:
            Settings(server.url, 'local').save('ollama')
            runtime = self.start_local()
            self.win._input.setText('first')
            self.win._send()
            self.wait_for(lambda: len(runtime.history) == 2)
            open_settings(self.win, 'ai')
            form = self.win._quick_drawer.forms['ai']
            self.wait_for(lambda: form.catalog_url == server.url and not form.busy)
            form.model.setCurrentIndex(form.model.findText('other:small'))
            form.apply()
            self.win._quick_drawer.accept()
            self.win._input.setText('second')
            self.win._send()
            self.wait_for(lambda: len(runtime.history) == 4)
            calls = [payload for path, payload in server.requests if path == '/api/chat']
            self.assertEqual([call['model'] for call in calls], ['local', 'other:small'])
            self.assertEqual([m['content'] for m in calls[-1]['messages'][1:]], ['first', 'Salom dunyo', 'second'])

    def test_model_names_are_not_translated_and_saved_selection_is_restored(self):
        with FakeOllama() as server:
            server.names = ['local:latest', 'jarvis:latest']
            Settings(server.url, 'jarvis:latest').save('ollama')
            open_settings(self.win, 'ai')
            form = self.win._quick_drawer.forms['ai']
            self.wait_for(lambda: form.catalog_url == server.url and not form.busy)
            for lang in ('en', 'ru', 'uz'):
                brave_ui.set_language(self.win, lang, persist=False)
                self.assertEqual(form.model.currentText(), 'jarvis:latest')
                self.assertEqual(form.model.currentIndex(), form.model.findText('jarvis:latest'))
                self.assertEqual([form.model.itemText(i) for i in range(form.model.count())], server.names)
            form.model.completer().setCompletionPrefix('ARVIS')
            self.assertEqual(form.model.completer().completionCount(), 1)
            form.refresh_models()
            self.wait_for(lambda: not form.busy)
            self.assertEqual(form.model.currentText(), 'jarvis:latest')

    def test_late_model_inventory_cannot_replace_changed_server_list(self):
        with FakeOllama() as old, FakeOllama() as new:
            old.before_headers['/api/tags'] = threading.Event()
            new.names = ['new:small']
            Settings(old.url, 'local').save('ollama')
            open_settings(self.win, 'ai')
            form = self.win._quick_drawer.forms['ai']
            self.wait_for(lambda: bool(old.requests))
            form.url.setText(new.url)
            old.before_headers['/api/tags'].set()
            self.wait_for(lambda: form.catalog_url == new.url and not form.busy)
            self.assertEqual([form.model.itemText(i) for i in range(form.model.count())], ['new:small'])
            self.assertEqual(Settings.read().url, old.url)

    def test_native_chat_rejects_cloud_metadata_redirect_and_malformed_stream(self):
        cases = ('cloud', 'redirect', 'malformed', 'truncated')
        for case in cases:
            with self.subTest(case=case), FakeOllama() as server:
                if case == 'cloud':
                    server.show = {'remote_host': 'https://ollama.com'}
                elif case == 'redirect':
                    server.overrides['/api/tags'] = (302, {}, {'Location': 'https://example.com/'})
                elif case == 'malformed':
                    server.chunks = [b'not-json\n']
                else:
                    server.chunks = [{'message': {'content': 'unfinished'}, 'done': False}]
                Settings(server.url, 'local').save('ollama')
                runtime = getattr(self.win, '_local_chat', None) or self.start_local()
                self.win._input.setText(case)
                self.win._send()
                self.wait_for(lambda: not runtime.busy and self.win._input.text() == case)
                self.assertEqual(runtime.history, [])
                if case in ('cloud', 'redirect'):
                    self.assertNotIn('/api/chat', [path for path, _ in server.requests])

    def test_whole_request_deadline_includes_model_verification(self):
        from brave_ollama_request import ChatRequest
        with FakeOllama() as server, patch.object(ChatRequest, 'TOTAL_MS', 60):
            server.before_headers['/api/tags'] = threading.Event()
            Settings(server.url, 'local').save('ollama')
            runtime = self.start_local()
            self.win._input.setText('bounded')
            self.win._send()
            self.wait_for(lambda: not runtime.busy and self.win._input.text() == 'bounded')
            self.assertNotIn('/api/chat', [path for path, _ in server.requests])

    def test_stream_survives_theme_change_without_becoming_saved_message(self):
        self.win._log.update_stream('partial')
        brave_ui.set_theme(self.win, 'hacker', persist=False)
        self.assertEqual(self.win._log._stream_body.toPlainText(), 'partial')
        self.assertEqual(self.win._features.store.messages(self.win._features.chat_id), [])
        self.win._log.end_stream()
        self.assertIsNone(self.win._log._stream_row)

    def test_settings_page_renders_all_languages_and_themes(self):
        from core.ollama_resources import Resources, GIB
        with FakeOllama() as server, patch('brave_ai_settings.sample_resources', return_value=Resources(8*GIB, 16*GIB, 4*GIB, 8*GIB)):
            server.catalog_rows = [
                {'name': 'llama3.2:latest', 'size': 2*1024**3,
                 'details': {'parameter_size': '3B', 'quantization_level': 'Q4_K_M'}},
                {'name': 'qwen2.5-coder:7b'}, {'name': 'gemma4:12b'}]
            server.show = {'capabilities': ['completion', 'thinking', 'vision'],
                           'thinking': {'values': [False, True]},
                           'model_info': {'llama.context_length': 8192}}
            Settings(server.url, 'llama3.2:latest', 'auto').save('ollama')
            open_settings(self.win, 'ai')
            dialog = self.win._quick_drawer
            form = dialog.forms['ai']
            self.wait_for(lambda: form.catalog_url == server.url and form.resources is not None and not form.busy)
            self.wait_for(lambda: form.description is not None)
            for theme in ('dark', 'light', 'hacker'):
                brave_ui.set_theme(self.win, theme, persist=False)
                for lang in ('uz', 'en', 'ru'):
                    brave_ui.set_language(self.win, lang, persist=False)
                    self.app.processEvents()
                    dialog.sections['ai'].ensureWidgetVisible(form.save)
                    self.app.processEvents()
                    self.assertFalse(dialog.grab().isNull())
                    self.assertEqual(form.model.currentText(), 'llama3.2:latest')
                    if os.environ.get('BRAVE_UI_PREVIEWS'):
                        destination = Path(os.environ['BRAVE_UI_PREVIEWS'])
                        destination.mkdir(parents=True, exist_ok=True)
                        dialog.grab().save(str(destination/f'brave-ollama-{theme}-{lang}.png'))

    def test_embedding_model_restores_draft_and_never_generates(self):
        with FakeOllama() as server:
            server.show = {'capabilities': ['embedding']}
            Settings(server.url, 'local', autostart=False).save('ollama')
            runtime = self.start_local()
            self.win._input.setText('keep unsupported prompt')
            self.win._send()
            self.wait_for(lambda: not runtime.busy and self.win._input.text() == 'keep unsupported prompt')
            self.assertEqual(runtime.history, [])
            self.assertEqual(runtime.diagnostics()['last_request']['status'], 'error')
            self.assertNotIn('/api/chat', [path for path, _ in server.requests])

    def test_model_capabilities_and_thinking_choice_follow_selection(self):
        from brave_i18n import translate
        with FakeOllama() as server:
            server.show = {'capabilities': ['completion', 'thinking'],
                           'thinking': {'values': ['low', 'high']},
                           'model_info': {'llama.context_length': 2048}}
            Settings(server.url, 'local', autostart=False).save('ollama')
            runtime = self.start_local()
            open_settings(self.win, 'ai')
            form = self.win._quick_drawer.forms['ai']
            self.wait_for(lambda: form.description is not None)
            self.assertTrue(form.thinking_row.isVisible())
            self.assertEqual([form.thinking.itemData(i) for i in range(form.thinking.count())], ['auto', 'low', 'high'])
            form.thinking.setCurrentIndex(form.thinking.findData('high'))
            form.apply()
            self.assertEqual(Settings.read().thinking, 'high')
            for lang in ('en', 'ru', 'uz'):
                brave_ui.set_language(self.win, lang, persist=False)
                self.assertIn(translate('Fikrlash'), form.model_info.text())
                self.assertEqual(form.thinking.currentData(), 'high')
            runtime.submit('hello', [])
            self.wait_for(lambda: not runtime.busy)
            payload = next(body for path, body in server.requests if path == '/api/chat')
            self.assertEqual(payload['think'], 'high')
            self.assertEqual(payload['options']['num_ctx'], 2048)
            server.show = {'capabilities': ['embedding']}
            form.model.setCurrentIndex(form.model.findText('other:small'))
            self.wait_for(lambda: form.description is not None)
            self.assertFalse(form.thinking_row.isVisible())
            form.apply()
            self.assertEqual(Settings.read().model, 'local:latest')
            self.assertIn(translate('Bu model matnli chatni qo‘llamaydi. Chat modelini tanlang.'), form.status.text())

    def test_request_statistics_are_numeric_and_do_not_retain_content(self):
        from brave_diagnostics import local_performance_checks
        with FakeOllama() as server:
            server.overrides['/api/version'] = (200, {'version': '0.12.3'}, {})
            server.running = [{'name': 'local:latest'}]
            server.chunks[-1].update(done_reason='length', eval_count=20, eval_duration=2_000_000_000,
                                      prompt_eval_count=12, load_duration=100_000_000)
            Settings(server.url, 'local', autostart=False).save('ollama')
            runtime = self.start_local()
            runtime.submit('secret prompt', [])
            self.wait_for(lambda: not runtime.busy)
            metrics = runtime.diagnostics()['last_request']
            self.assertEqual(metrics['tokens_per_second'], 10)
            self.assertEqual(metrics['load_s'], .1)
            self.assertEqual(metrics['residency'], 'loaded')
            self.assertEqual(metrics['server_version'], '0.12.3')
            self.assertGreaterEqual(metrics['first_reply_s'], metrics['preparation_s'])
            self.assertGreaterEqual(metrics['elapsed_s'], metrics['first_reply_s'])
            self.assertNotIn('secret prompt', json.dumps(metrics))
            self.assertNotIn('dunyo', json.dumps(metrics))
            metrics['model'] = 'modified snapshot'
            self.assertEqual(runtime.last_request['model'], 'local')
            self.assertTrue(any('10.0 token/s' in detail for _, _, detail in local_performance_checks(runtime.diagnostics())))
            self.assertEqual(runtime.last_request['done_reason'], 'length')

    def test_metadata_from_previous_selection_cannot_change_current_controls(self):
        with FakeOllama() as server:
            server.before_headers['/api/show'] = threading.Event()
            Settings(server.url, 'local', autostart=False).save('ollama')
            open_settings(self.win, 'ai')
            form = self.win._quick_drawer.forms['ai']
            self.wait_for(lambda: any(path == '/api/show' for path, _ in server.requests))
            form.model.setEditText('')
            server.before_headers['/api/show'].set()
            QTest.qWait(150)
            self.assertIsNone(form.description)
            self.assertFalse(form.thinking_row.isVisible())

    def test_performance_diagnostics_render_without_changing_model_names(self):
        from brave_diagnostics import DiagnosticsDialog, local_performance_checks
        from PyQt6.QtWidgets import QLabel, QScrollArea
        from brave_i18n import translate
        runtime = {'provider': 'ollama', 'configured_profile': 'auto', 'profile': 'balanced',
                   'last_request': {'model': 'jarvis:latest', 'profile': 'balanced',
                                    'server_version': '0.12.3', 'residency': 'loaded', 'status': 'completed',
                                    'context_length': 4096, 'first_reply_s': 1.2, 'elapsed_s': 3.4,
                                    'preparation_s': .02, 'load_s': .1, 'tokens_per_second': 10,
                                    'prompt_eval_count': 12, 'eval_count': 20}}
        for theme in ('dark', 'light', 'hacker'):
            brave_ui.set_theme(self.win, theme, persist=False)
            for lang in ('uz', 'en', 'ru'):
                brave_ui.set_language(self.win, lang, persist=False)
                checks = [('Ollama · Offline', 'good', 'Ollama ulandi. Lokal model tayyor.')]+local_performance_checks(runtime)
                with patch('brave_diagnostics.collect_checks', return_value=checks):
                    dialog = DiagnosticsDialog(self.win)
                    dialog.show()
                    self.wait_for(lambda: dialog.rows.count() == len(checks))
                    texts = '\n'.join(label.text() for label in dialog.findChildren(QLabel))
                    self.assertIn('jarvis:latest', texts)
                    self.assertIn(translate('Generatsiya tezligi'), texts)
                    self.assertIn('10.0 token/s', texts)
                    self.assertTrue(dialog.findChild(QScrollArea).isVisible())
                    if os.environ.get('BRAVE_UI_PREVIEWS'):
                        destination = Path(os.environ['BRAVE_UI_PREVIEWS'])
                        dialog.grab().save(str(destination/f'brave-local-diagnostics-{theme}-{lang}.png'))
                    dialog.close()
                    dialog.deleteLater()


if __name__ == '__main__':
    unittest.main()
