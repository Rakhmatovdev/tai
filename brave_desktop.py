"""Frozen desktop entry; application settings survive versioned per-user updates."""
import os
import sys
from pathlib import Path


def main():
    frozen=getattr(sys,'frozen',False)
    from memory import config_manager
    if frozen:
        root=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))/'Brave'/'config'
        root.mkdir(parents=True,exist_ok=True)
        config_manager.CONFIG_DIR=root;config_manager.CONFIG_FILE=root/'api_keys.json'
        os.chdir(Path(sys.executable).parent)
    import ui
    if frozen:
        ui.CONFIG_DIR=config_manager.CONFIG_DIR;ui.API_FILE=config_manager.CONFIG_FILE
    import core.gemini as gemini
    import core.llm_client as client
    import memory.memory_manager as memories
    import main as engine
    if frozen:
        gemini._KEY_FILE=config_manager.CONFIG_FILE;client.CONFIG_PATH=config_manager.CONFIG_FILE
        engine.API_CONFIG_PATH=config_manager.CONFIG_FILE
        memories.MEMORY_PATH=config_manager.CONFIG_DIR.parent/'long-term-memory.json'
    if '--smoke-test' in sys.argv:
        import json
        import tempfile
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication
        from core import workspace_store
        temporary=tempfile.TemporaryDirectory(prefix='brave-package-smoke-');root=Path(temporary.name)
        workspace_store.directory=lambda:root
        ui.API_FILE=root/'config.json';config_manager.CONFIG_FILE=ui.API_FILE
        ui.API_FILE.write_text('{"chat_provider":"ollama","ollama_autostart":false}',encoding='utf-8')
        ui.MainWindow._check_config=lambda self:True
        ui.MainWindow._check_autostart=lambda self:False
        app=QApplication.instance() or QApplication([])
        window=ui.MainWindow('');window.show()
        from brave_local_lab import LocalLab
        from brave_document_lab import DocumentLab
        from brave_conversation_inspector import Inspector
        dialogs=[factory(window) for factory in (LocalLab,DocumentLab,Inspector)]
        target=Path(sys.argv[sys.argv.index('--smoke-test')+1])
        def finish():
            try:
                target.parent.mkdir(parents=True,exist_ok=True)
                window.grab().save(str(target.with_suffix('.png')))
                target.write_text(json.dumps({'ok':True,'dialogs':len(dialogs),'frozen':frozen}),encoding='utf-8')
            finally:
                for dialog in dialogs:dialog.reject()
                window.close();app.quit()
        QTimer.singleShot(1500,finish);app.exec();temporary.cleanup();return
    engine.main()


if __name__=='__main__':
    try:main()
    except Exception:
        import traceback
        root=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))/'Brave'
        root.mkdir(parents=True,exist_ok=True)
        (root/'startup-error.log').write_text(traceback.format_exc(),encoding='utf-8')
        sys.exit(1)
