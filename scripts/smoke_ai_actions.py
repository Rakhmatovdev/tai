"""Explicit real local AI checks, using only synthetic text/images and temp history."""
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
    parser.add_argument('--vision-model', help='An installed vision model to test; never downloads')
    args = parser.parse_args()
    import ui
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication
    from brave_local_chat import LocalChat
    from brave_text_actions import TextActions
    from core.ollama_chat import Settings
    from core import workspace_store
    from memory import config_manager
    from PIL import Image

    app = QApplication.instance() or QApplication([])
    selected = Settings.read()
    results = {}
    def wait_for(predicate, seconds=180):
        deadline = time.monotonic()+seconds
        while not predicate() and time.monotonic()<deadline:
            QTest.qWait(20)
        if not predicate(): raise RuntimeError('Real AI smoke timed out')
    with tempfile.TemporaryDirectory(prefix='brave-ai-smoke-') as folder:
        root = Path(folder)
        config = root/'config.json'
        values = {'chat_provider': 'ollama', 'local_voice_reply': False, 'ui_language': 'uz',
                  **{'ollama_'+key: value for key, value in asdict(selected).items()}}
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
            dialog = TextActions(win, 'Project budget: 42 units. Deadline: Monday. Owner: Ali.')
            dialog.open()
            dialog.target.setCurrentIndex(dialog.target.findData('en'))
            started = time.monotonic()
            dialog.start()
            wait_for(lambda: dialog.run.isEnabled())
            assert dialog.answer and '42' in dialog.answer, dialog.status.text()
            assert win._features.store.count(win._features.chat_id) == 0
            results['summary'] = {'elapsed_s': time.monotonic()-started,
                                  'answer': dialog.answer, 'metrics': dialog.metrics}
            dialog.reject()
            if args.vision_model:
                values['ollama_model'] = args.vision_model
                values['ollama_profile'] = 'balanced'
                config.write_text(json.dumps(values), encoding='utf-8')
                path = root/'red-synthetic.png'
                Image.new('RGB', (320, 240), 'red').save(path)
                win._drop_zone._set_file(str(path))
                win._image_mode.setCurrentIndex(win._image_mode.findData('vision'))
                win._input.setText('What is the main color of this image? Reply with one English color word.')
                started = time.monotonic()
                win._send()
                wait_for(lambda: runtime.last_request is not None and not runtime.busy)
                assert runtime.last_request.get('status') == 'completed', runtime.last_request
                answer = runtime.history[-1]['content']
                assert 'red' in answer.casefold(), answer
                results['vision_chat'] = {'elapsed_s': time.monotonic()-started,
                                          'answer': answer, 'metrics': runtime.last_request}
                args.output.parent.mkdir(parents=True, exist_ok=True)
                win.grab().save(str(args.output.with_suffix('.png')))
            runtime.shutdown()
            win.close()
            win.deleteLater()
            app.processEvents()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=True, indent=2))


if __name__ == '__main__': main()
