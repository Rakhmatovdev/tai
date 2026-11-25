"""Reproducible offline UI benchmark using temporary settings and synthetic text."""
import argparse
import cProfile
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    import ui
    from PyQt6.QtCore import QEventLoop, QTimer
    from PyQt6.QtWidgets import QApplication
    from core import workspace_store
    from memory import config_manager

    result = {'ui_import_s': time.perf_counter() - started}
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix='brave-perf-') as folder:
        root = Path(folder)
        config = root / 'config.json'
        config.write_text('{"chat_provider":"ollama","ollama_autostart":false}')
        with (patch.object(ui, 'API_FILE', config),
              patch.object(config_manager, 'CONFIG_FILE', config),
              patch.object(workspace_store, 'directory', return_value=root),
              patch.object(ui.MainWindow, '_check_config', return_value=True),
              patch.object(ui.MainWindow, '_check_autostart', return_value=False)):
            started = time.perf_counter()
            win = ui.MainWindow('')
            win.show()
            app.processEvents()
            result['window_s'] = time.perf_counter() - started
            profile = cProfile.Profile()
            loop = QEventLoop()
            cpu_start = time.process_time()
            started = time.perf_counter()
            QTimer.singleShot(3000, loop.quit)
            profile.enable()
            loop.exec()
            profile.disable()
            result['idle_cpu_s'] = time.process_time() - cpu_start
            result['idle_wall_s'] = time.perf_counter() - started
            log = win._log
            text = ''
            started = time.perf_counter()
            for _ in range(160):
                text += 'Synthetic streaming answer with words and **formatting**.\n' * 2
                log.update_stream(text)
            result['stream_160_updates_s'] = time.perf_counter() - started
            log.end_stream()
            app.processEvents()
            win.hide()
            cpu_start = time.process_time()
            started = time.perf_counter()
            QTimer.singleShot(2000, loop.quit)
            loop.exec()
            result['hidden_cpu_s'] = time.process_time() - cpu_start
            result['hidden_wall_s'] = time.perf_counter() - started
            win.close()
            win.deleteLater()
            app.processEvents()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    profile.dump_stats(str(args.output.with_suffix('.prof')))
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
