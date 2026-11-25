"""Model compatibility and native protocol measurements, without real inference."""
import json
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.ollama_chat import Settings, chat_payload, OllamaClient
from core.ollama_model import model_info, require_chat, response_metrics
from test_ollama import FakeOllama
from PyQt6.QtTest import QTest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from brave_ollama_request import ChatRequest


class ModelPolicyTests(unittest.TestCase):
    def test_unknown_old_metadata_does_not_force_thinking(self):
        payload = chat_payload(Settings(), [], model_info({}))
        self.assertNotIn('think', payload)
        self.assertEqual(payload['options']['num_ctx'], 4096)

    def test_embedding_only_is_rejected_by_both_transports(self):
        with self.assertRaises(ValueError):
            require_chat(model_info({'capabilities': ['embedding']}))
        with FakeOllama() as server:
            server.show = {'capabilities': ['embedding']}
            client = OllamaClient(Settings(server.url, 'local'))
            try:
                with self.assertRaises(ValueError):
                    list(client.stream([], threading.Event()))
                self.assertNotIn('/api/chat', [p for p, _ in server.requests])
            finally:
                client.close()

    def test_boolean_and_named_controls_are_not_interchanged(self):
        for values, choice, expected in [([False, True], 'off', False),
                                        ([False, True], 'on', True),
                                        (['low', 'high'], 'high', 'high'),
                                        (['low', 'high'], 'off', None),
                                        ([False], 'on', None),
                                        ([True], 'off', None),
                                        ([False, True], 'auto', None)]:
            with self.subTest(values=values, choice=choice):
                info = model_info({'thinking': {'values': values}})
                payload = chat_payload(Settings(thinking=choice), [], info)
                self.assertEqual(payload.get('think'), expected)

    def test_legacy_thinking_capability_and_model_context_cap(self):
        info = model_info({'capabilities': ['completion', 'thinking'],
                           'model_info': {'general.architecture': 'llama', 'llama.context_length': 1024}})
        payload = chat_payload(Settings(profile='quality'), [], info)
        self.assertNotIn('think', payload)
        self.assertEqual(payload['options']['num_ctx'], 1024)

    def test_invalid_optional_metadata_cannot_create_controls(self):
        info = model_info({'capabilities': 'embedding', 'thinking': {'values': [1, [], {}, 'bad value']},
                           'model_info': {'x.context_length': True}})
        self.assertIsNone(info['capabilities'])
        self.assertEqual(info['thinking_values'], [])
        self.assertIsNone(info['context_length'])

    def test_metrics_allowlist_ignores_text_and_invalid_numbers(self):
        result = response_metrics({'eval_count': True, 'eval_duration': 0, 'load_duration': -1,
                                   'done_reason': 'secret text', 'message': {'content': 'secret'},
                                   'prompt_eval_count': 10, 'total_duration': 3_000_000_000})
        self.assertEqual(result, {'prompt_eval_count': 10, 'total_s': 3, 'eval_s': 0, 'done_reason': 'other'})


class NativeProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def run_request(self, server, thinking='off', action=None):
        job = ChatRequest(Settings(server.url, 'local', thinking=thinking), [])
        self.addCleanup(job.deleteLater)
        results, phases = [], []
        job.finished.connect(lambda *args: results.append(args))
        job.phase.connect(phases.append)
        job.start()
        if action:
            action(job)
        deadline = time.monotonic()+3
        while not results and time.monotonic() < deadline:
            QTest.qWait(5)
        self.assertTrue(results, phases)
        return job, results[0], phases

    def test_thinking_stream_is_activity_without_exposing_reasoning(self):
        with FakeOllama() as server:
            server.show = {'capabilities': ['completion', 'thinking'], 'thinking': {'values': [True]}}
            server.chunks = [{'message': {'thinking': 'private reasoning'}, 'done': False},
                             {'message': {'content': 'answer'}, 'done': True}]
            job, result, phases = self.run_request(server)
            self.assertEqual(result, ('answer', '', False))
            self.assertIn('thinking', phases)
            self.assertNotIn('private reasoning', json.dumps(job.metrics))
            body = next(body for path, body in server.requests if path == '/api/chat')
            self.assertNotIn('think', body)

    def test_thinking_only_stall_is_timed_out(self):
        with FakeOllama() as server, patch.object(ChatRequest, 'IDLE_MS', 40):
            server.pause = threading.Event()
            server.chunks[0] = {'message': {'thinking': 'private'}, 'done': False}
            job, result, phases = self.run_request(server)
            self.assertTrue(result[1])
            self.assertEqual(job.metrics['status'], 'error')
            self.assertNotIn('first_reply_s', job.metrics)

    def test_thinking_activity_replaces_first_reply_timeout_with_idle_timeout(self):
        with FakeOllama() as server, patch.object(ChatRequest, 'FIRST_TOKEN_MS', 40), patch.object(ChatRequest, 'IDLE_MS', 250):
            server.pause = threading.Event()
            server.chunks[0] = {'message': {'thinking': 'private'}, 'done': False}
            def action(job):
                job.phase.connect(lambda phase: QTimer.singleShot(80, server.pause.set) if phase == 'thinking' else None)
            _, result, _ = self.run_request(server, action=action)
            self.assertEqual(result, ('dunyo', '', False))

    def test_optional_metadata_timeout_does_not_prevent_chat(self):
        with FakeOllama() as server, patch.object(ChatRequest, 'META_MS', 40):
            server.before_headers['/api/version'] = threading.Event()
            job, result, _ = self.run_request(server)
            self.assertEqual(result, ('Salom dunyo', '', False))
            self.assertIsNone(job.metrics['server_version'])

    def test_advisory_checks_have_a_short_budget_independent_of_required_checks(self):
        with FakeOllama() as server, patch.object(ChatRequest, 'ADVISORY_MS', 60):
            server.before_headers['/api/version'] = threading.Event()
            server.before_headers['/api/ps'] = threading.Event()
            started = time.monotonic()
            job, result, _ = self.run_request(server)
            elapsed = time.monotonic() - started
            server.before_headers['/api/version'].set()
            server.before_headers['/api/ps'].set()
            self.assertEqual(result, ('Salom dunyo', '', False))
            self.assertLess(elapsed, 1)
            self.assertIsNone(job.metrics['server_version'])
            self.assertEqual(job.metrics['residency'], 'unknown')

    def test_total_deadline_still_applies_during_optional_metadata(self):
        with FakeOllama() as server, patch.object(ChatRequest, 'TOTAL_MS', 60):
            server.before_headers['/api/version'] = threading.Event()
            job, result, _ = self.run_request(server)
            self.assertTrue(result[1])
            self.assertEqual(job.metrics['status'], 'error')
            self.assertNotIn('/api/chat', [path for path, _ in server.requests])

    def test_missing_version_and_running_metadata_still_allow_chat(self):
        with FakeOllama() as server:
            server.overrides['/api/version'] = (404, {}, {})
            server.overrides['/api/ps'] = (404, {}, {})
            job, result, _ = self.run_request(server)
            self.assertEqual(result, ('Salom dunyo', '', False))
            self.assertIsNone(job.metrics['server_version'])
            self.assertEqual(job.metrics['residency'], 'unknown')
            self.assertNotIn('tokens_per_second', job.metrics)

    def test_metrics_count_zero_without_dividing_by_zero(self):
        with FakeOllama() as server:
            server.chunks[-1].update(eval_count=0, eval_duration=0, load_duration=0)
            job, result, _ = self.run_request(server)
            self.assertEqual(job.metrics['eval_count'], 0)
            self.assertEqual(job.metrics['load_s'], 0)
            self.assertNotIn('tokens_per_second', job.metrics)

    def test_cancelled_metrics_do_not_look_like_completed_reply(self):
        with FakeOllama() as server:
            job, result, _ = self.run_request(server, action=lambda job: job.cancel())
            self.assertTrue(result[2])
            self.assertEqual(job.metrics['status'], 'cancelled')
            self.assertNotIn('eval_count', job.metrics)


if __name__ == '__main__':
    unittest.main()
