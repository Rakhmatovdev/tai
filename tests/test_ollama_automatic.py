"""Service startup and resource policy tests without launching real processes."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core import ollama_service as service
from core.ollama_chat import Settings
from core.ollama_resources import (AutoProfile, Resources, GIB, sample_resources, suggested_profile,
                                   sample_hardware, hardware_tier, hardware_summary, hardware_recommendation_text)
from core.model_recommender import suggest_downloads, best_installed_model, model_fit_details
from memory import config_manager


class ServiceTests(unittest.TestCase):
    def test_reuses_existing_server(self):
        with patch.object(service, 'health', return_value=True), patch.object(service, 'launch_server') as launch:
            self.assertTrue(service.ensure_server(Settings.url))
            launch.assert_not_called()

    def test_disabled_or_custom_address_does_not_launch(self):
        with patch.object(service, 'health', return_value=False), patch.object(service, 'launch_server') as launch:
            for url, enabled in [(Settings.url, False), ('http://127.0.0.1:12345', True), ('http://[::1]:11434', True)]:
                with self.subTest(url=url, enabled=enabled), self.assertRaises(RuntimeError):
                    service.ensure_server(url, enabled)
            launch.assert_not_called()

    def test_launch_uses_installed_binary_hidden_and_process_local_environment(self):
        with patch.object(service, 'executable', return_value='C:/Program Files/Ollama/ollama.exe'), \
                patch.object(service.subprocess, 'Popen') as launch, \
                patch.dict(os.environ, {'OLLAMA_HOST': '0.0.0.0:9999', 'OLLAMA_NO_CLOUD': '0'}):
            service.launch_server()
            args, options = launch.call_args
            self.assertEqual(args[0], ['C:/Program Files/Ollama/ollama.exe', 'serve'])
            self.assertEqual(options['env']['OLLAMA_HOST'], '127.0.0.1:11434')
            self.assertEqual(options['env']['OLLAMA_NO_CLOUD'], '1')
            self.assertEqual(os.environ['OLLAMA_HOST'], '0.0.0.0:9999')
            self.assertNotIn('shell', options)
            if service.sys.platform == 'win32':
                self.assertTrue(options['creationflags'] & service.subprocess.CREATE_NO_WINDOW)

    def test_missing_install_is_actionable(self):
        with patch.object(service, 'health', return_value=False), patch.object(service, '_process', None), \
                patch.object(service, 'executable', return_value=None), self.assertRaisesRegex(RuntimeError, 'topilmadi'):
            service.ensure_server(Settings.url)

    def test_simultaneous_requests_launch_once(self):
        ready = threading.Event()
        process = Mock()
        process.poll.return_value = None
        def launch():
            ready.set()
            return process
        with patch.object(service, 'health', side_effect=lambda *args: ready.is_set()), \
                patch.object(service, '_process', None), patch.object(service, 'launch_server', side_effect=launch) as starter:
            with ThreadPoolExecutor(max_workers=2) as pool:
                requests = [pool.submit(service.ensure_server, Settings.url) for _ in range(2)]
                self.assertTrue(all(task.result(3) for task in requests))
            starter.assert_called_once()

    def test_startup_timeout_never_creates_another_running_process(self):
        process = Mock()
        process.poll.return_value = None
        with patch.object(service, 'health', return_value=False), patch.object(service, '_process', process), \
                patch.object(service, 'launch_server') as launch, self.assertRaises(RuntimeError):
            service.ensure_server(Settings.url, timeout=.02)
        launch.assert_not_called()

    def test_cancel_before_launch_or_during_startup(self):
        cancelled = threading.Event()
        cancelled.set()
        with patch.object(service, 'health') as health, patch.object(service, 'launch_server') as launch:
            self.assertFalse(service.ensure_server(Settings.url, cancelled=cancelled))
            health.assert_not_called()
            launch.assert_not_called()
        cancelled.clear()
        with patch.object(service, 'health', return_value=False), patch.object(service, 'launch_server') as launch:
            self.assertFalse(service.ensure_server(Settings.url, cancelled=cancelled, stage=lambda _: cancelled.set()))
            launch.assert_not_called()

    def test_redirect_or_invalid_server_never_triggers_launch(self):
        response = Mock(is_redirect=True, status_code=302)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        session = Mock()
        session.__enter__ = Mock(return_value=session)
        session.__exit__ = Mock(return_value=False)
        session.get.return_value = response
        with patch.object(service.requests, 'Session', return_value=session), patch.object(service, 'launch_server') as launch:
            with self.assertRaises(RuntimeError):
                service.ensure_server(Settings.url)
            launch.assert_not_called()
            self.assertFalse(session.get.call_args.kwargs['allow_redirects'])
            self.assertFalse(session.trust_env)


class ResourceTests(unittest.TestCase):
    def test_policy_uses_available_memory_and_keeps_quality_manual(self):
        cases = [(Resources(), 'economy'), (Resources(3*GIB, 64*GIB), 'economy'),
                 (Resources(5*GIB, 64*GIB), 'economy'), (Resources(8*GIB, 16*GIB), 'balanced'),
                 (Resources(16*GIB, 32*GIB, GIB//2, 8*GIB), 'economy'),
                 (Resources(32*GIB, 64*GIB, 2*GIB, 32*GIB), 'economy'),
                 (Resources(16*GIB, 32*GIB, 4*GIB, 8*GIB), 'balanced'),
                 (Resources(64*GIB, 128*GIB, 48*GIB, 64*GIB), 'balanced')]
        for resources, expected in cases:
            with self.subTest(resources=resources):
                self.assertEqual(suggested_profile(resources), expected)

    def test_auto_downshifts_and_waits_for_recovery(self):
        auto = AutoProfile()
        settings = Settings(profile='auto')
        high, low = Resources(12*GIB, 16*GIB), Resources(2*GIB, 16*GIB)
        self.assertEqual(auto.resolve(settings, high, now=0).profile, 'balanced')
        self.assertEqual(auto.resolve(settings, low, now=10).profile, 'economy')
        self.assertEqual(auto.resolve(settings, low, now=50).profile, 'economy')
        self.assertEqual(auto.resolve(settings, high, now=70).profile, 'economy')
        self.assertEqual(auto.resolve(settings, high, now=111).profile, 'balanced')
        manual = Settings(profile='quality')
        self.assertIs(auto.resolve(manual, low), manual)

    def test_probe_falls_back_when_gpu_or_memory_unavailable(self):
        with patch('psutil.virtual_memory', side_effect=OSError), patch('core.ollama_resources.gpu_backend', return_value=None):
            self.assertEqual(sample_resources(), Resources())
        with patch('psutil.virtual_memory', return_value=SimpleNamespace(available=8*GIB, total=16*GIB)), \
                patch('core.ollama_resources.gpu_backend', return_value=None):
            self.assertEqual(suggested_profile(sample_resources()), 'balanced')

    def test_gpu_probe_does_not_sum_unrelated_devices(self):
        nvml = Mock()
        nvml.nvmlDeviceGetCount.return_value = 2
        nvml.nvmlDeviceGetHandleByIndex.side_effect = lambda index: index
        nvml.nvmlDeviceGetMemoryInfo.side_effect = lambda index: SimpleNamespace(free=(2+index)*GIB, total=8*GIB)
        with patch('psutil.virtual_memory', return_value=SimpleNamespace(available=8*GIB, total=16*GIB)), \
                patch('core.ollama_resources.gpu_backend', return_value=nvml):
            resources = sample_resources()
        self.assertEqual(resources.gpu_free, 3*GIB)

    def test_settings_round_trip_and_legacy_manual_profile(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(config_manager, 'CONFIG_FILE', Path(directory)/'settings.json'):
            config_manager._patch_config(gemini_api_key='fake-key', ollama_profile='quality')
            self.assertEqual(Settings.read().profile, 'quality')
            Settings(profile='auto', autostart=False).save('ollama')
            settings = Settings.read()
            self.assertEqual(settings.profile, 'auto')
            self.assertFalse(settings.autostart)
            self.assertEqual(config_manager.load_api_keys()['gemini_api_key'], 'fake-key')

    def test_hardware_tier_classification(self):
        high = Resources(ram_free=16*GIB, ram_total=32*GIB, gpu_free=6*GIB, gpu_total=8*GIB)
        mid = Resources(ram_free=6*GIB, ram_total=16*GIB, gpu_free=2*GIB, gpu_total=4*GIB)
        entry = Resources(ram_free=2*GIB, ram_total=8*GIB, gpu_free=None, gpu_total=None)
        self.assertEqual(hardware_tier(high), 'high')
        self.assertEqual(hardware_tier(mid), 'mid')
        self.assertEqual(hardware_tier(entry), 'entry')

    def test_hardware_summary_and_recommendation_text(self):
        res = Resources(
            ram_free=16*GIB, ram_total=32*GIB,
            gpu_free=6*GIB, gpu_total=8*GIB,
            cpu_cores=8, cpu_threads=16,
            cpu_name='AMD Ryzen 7 7435HS',
            gpu_name='NVIDIA RTX 4060',
            disk_free=50*GIB, disk_total=500*GIB
        )
        summary = hardware_summary(res)
        self.assertIn('AMD Ryzen 7 7435HS', summary)
        self.assertIn('32.0 GB', summary)
        self.assertIn('NVIDIA RTX 4060', summary)
        self.assertIn('50.0 GB', summary)

        rec = hardware_recommendation_text(res)
        self.assertIn('7B', rec)
        self.assertIn('Qwen', rec)

    def test_model_fit_details_and_best_model(self):
        high_res = Resources(ram_free=16*GIB, ram_total=32*GIB, gpu_free=6*GIB, gpu_total=8*GIB)
        fit_small = model_fit_details('llama3.2:3b', 2*GIB, high_res)
        self.assertTrue(fit_small['vram_fit'])
        self.assertEqual(fit_small['fit_level'], 'perfect')
        self.assertIn('GPU', fit_small['badge'])

        fit_huge = model_fit_details('llama3.1:70b', 40*GIB, high_res)
        self.assertFalse(fit_huge['fits'])
        self.assertEqual(fit_huge['fit_level'], 'exceeds')

        # Test suggest_downloads
        high_dl = suggest_downloads(high_res)
        self.assertTrue(any('qwen2.5:7b' in item['name'] for item in high_dl))

        entry_res = Resources(ram_free=2*GIB, ram_total=4*GIB, gpu_free=None, gpu_total=None)
        entry_dl = suggest_downloads(entry_res)
        self.assertTrue(any('1b' in item['name'] for item in entry_dl))

        # Test best_installed_model
        catalog = [
            {'name': 'llama3.2:3b', 'size': 2*GIB},
            {'name': 'qwen2.5:7b', 'size': 4*GIB},
            {'name': 'huge:70b', 'size': 40*GIB}
        ]
        descs = {
            'llama3.2:3b': {'capabilities': ['completion']},
            'qwen2.5:7b': {'capabilities': ['completion']},
            'huge:70b': {'capabilities': ['completion']}
        }
        best = best_installed_model(catalog, descs, high_res)
        self.assertIsNotNone(best)
        self.assertTrue(best['name'] in ('llama3.2:3b', 'qwen2.5:7b'))

    def test_pick_best_prefers_strongest_model_that_fits_without_metadata(self):
        from core.model_recommender import pick_best_for_hardware
        catalog = [{'name': 'llama3.2:3b', 'size': 2*GIB}, {'name': 'qwen2.5:7b', 'size': 4*GIB},
                   {'name': 'nomic-embed-text', 'size': GIB // 4}, {'name': 'huge:70b', 'size': 40*GIB}]
        roomy_gpu = Resources(ram_free=16*GIB, ram_total=32*GIB, gpu_free=8*GIB, gpu_total=12*GIB)
        self.assertEqual(pick_best_for_hardware(catalog, roomy_gpu)['name'], 'qwen2.5:7b')
        # Smoothness first: a model fully on the GPU beats a larger one spilling into RAM.
        gpu = Resources(ram_free=16*GIB, ram_total=32*GIB, gpu_free=5*GIB, gpu_total=8*GIB)
        self.assertEqual(pick_best_for_hardware(catalog, gpu)['name'], 'llama3.2:3b')
        cpu_only = Resources(ram_free=16*GIB, ram_total=32*GIB)
        self.assertEqual(pick_best_for_hardware(catalog, cpu_only)['name'], 'qwen2.5:7b')
        small = Resources(ram_free=4*GIB, ram_total=8*GIB)
        self.assertEqual(pick_best_for_hardware(catalog, small)['name'], 'llama3.2:3b')
        self.assertIsNone(pick_best_for_hardware([catalog[3]], roomy_gpu))


if __name__ == '__main__':
    unittest.main()
