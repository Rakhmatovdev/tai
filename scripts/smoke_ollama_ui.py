"""Exercise real local inference through the UI with isolated synthetic history."""
import argparse
from dataclasses import asdict
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
    parser.add_argument('--long-history', action='store_true')
    args = parser.parse_args()
    import ui
    from PyQt6.QtCore import QEventLoop, QTimer
    from PyQt6.QtWidgets import QApplication
    from brave_local_chat import LocalChat
    from core.ollama_chat import Settings
    from core import workspace_store
    from memory import config_manager

    selected = Settings.read()
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix='brave-local-smoke-') as folder:
        root = Path(folder)
        config = root / 'config.json'
        values = {'chat_provider': 'ollama', 'local_voice_reply': False,
                  'ui_language': 'uz', **{'ollama_'+key: value for key, value in asdict(selected).items()}}
        # Only local-model settings are copied; no keys, history, audio or files.
        config.write_text(json.dumps(values), encoding='utf-8')
        with (patch.object(ui, 'API_FILE', config),
              patch.object(config_manager, 'CONFIG_FILE', config),
              patch.object(workspace_store, 'directory', return_value=root),
              patch.object(ui.MainWindow, '_check_config', return_value=True),
              patch.object(ui.MainWindow, '_check_autostart', return_value=False)):
            win = ui.MainWindow('')
            win.show()
            runtime = LocalChat(win)
            win._local_chat = runtime
            if args.long_history:
                for index in range(12):
                    for role in ('user', 'assistant'):
                        win._features.store.append(win._features.chat_id, role,
                            f'Synthetic note {index}: the budget is 42. ' * 45, '12:00')
                runtime.change_chat(win._features.store.messages(win._features.chat_id))
            initial_count = win._features.store.count(win._features.chat_id)
            loop = QEventLoop()
            samples = []
            last_tick = time.monotonic()
            def check():
                nonlocal last_tick
                now = time.monotonic()
                samples.append(now-last_tick)
                last_tick = now
                if not runtime.busy:
                    loop.quit()
            timer = QTimer()
            timer.timeout.connect(check)
            timer.start(20)
            deadline = QTimer()
            deadline.setSingleShot(True)
            deadline.timeout.connect(lambda: (runtime.cancel(), loop.quit()))
            deadline.start(60000)
            win._input.setText('Ali 12 ta daftar oldi, 5 tasini berdi. Nechta qoldi? Qisqa javob bering.')
            started = time.monotonic()
            win._send()
            win._input.setText('Unsent synthetic draft')
            loop.exec()
            timer.stop()
            deadline.stop()
            metrics = runtime.last_request or {}
            rows = win._features.store.messages(win._features.chat_id)
            result = {'elapsed_s': time.monotonic()-started,
                      'max_ui_tick_gap_s': max(samples, default=0),
                      'summary_requests': getattr(runtime, 'summary_rounds', 0),
                      'saved_messages': len(rows)-initial_count,
                      'draft_preserved': win._input.text() == 'Unsent synthetic draft',
                      'metrics': metrics, 'answer': rows[-1][1]}
            args.output.parent.mkdir(parents=True, exist_ok=True)
            win.grab().save(str(args.output.with_suffix('.png')))
            runtime.shutdown()
            win.close()
            win.deleteLater()
            app.processEvents()
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(result, ensure_ascii=True), flush=True)
            assert result['saved_messages'] == 2, result
            assert result['draft_preserved'], result
            assert metrics.get('status') == 'completed', result
            if args.long_history:
                assert result['summary_requests'] == 1, result


if __name__ == '__main__':
    main()
