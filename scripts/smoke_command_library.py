"""Real Ollama command smoke: synthetic data, temporary history and settings."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch
import requests

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))


def main():
    import ui
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtTest import QTest
    from brave_local_chat import LocalChat
    from core import workspace_store
    from core.ollama_chat import Settings
    from memory import config_manager
    cfg=Settings.read();before_cfg=config_manager.CONFIG_FILE.read_bytes()
    resident={row['name'] for row in requests.get(cfg.url+'/api/ps',timeout=5).json().get('models',[])}
    installed={row['name'] for row in requests.get(cfg.url+'/api/tags',timeout=5).json().get('models',[])}
    assert 'llama3.2:latest' in installed,'Install a small local chat model explicitly first.'
    results={'complete':False,'commands':{}};used=set()
    output=Path('logs/commands-real-smoke.json')
    def checkpoint():output.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    app=QApplication.instance() or QApplication([])
    def wait_for(predicate):
        end=time.monotonic()+180
        while not predicate() and time.monotonic()<end:QTest.qWait(20)
        assert predicate(),'Command timed out'
    try:
        with tempfile.TemporaryDirectory(prefix='brave-command-smoke-') as directory:
            root=Path(directory);config=root/'settings.json'
            config.write_text(json.dumps({'chat_provider':'ollama','ollama_url':cfg.url,'ollama_model':'llama3.2:latest',
                'ollama_profile':'balanced','ollama_thinking':'off','ollama_autostart':False,'local_voice_reply':False,'ui_language':'en'}),encoding='utf-8')
            with (patch.object(ui,'API_FILE',config),patch.object(config_manager,'CONFIG_FILE',config),
                  patch.object(workspace_store,'directory',return_value=root),
                  patch.object(ui.MainWindow,'_check_config',return_value=True),patch.object(ui.MainWindow,'_check_autostart',return_value=False)):
                win=ui.MainWindow('');win.show();runtime=LocalChat(win);win._local_chat=runtime
                try:
                    for name,prompt in [('debug','/debug Python: def divide(a,b): return a/b\nCalling divide(4,0) raises ZeroDivisionError. Explain the cause and a minimal fix.'),
                        ('table','/table Make a table with name and budget: Ali, 42 dollars; Sara, 17 dollars.'),
                        ('extract','/extract Return fields name and amount: name is Ali, amount is 42.')]:
                        print('Real /'+name,flush=True);previous=runtime.last_request;count=len(runtime.history);started=time.monotonic()
                        win._input.setText(prompt);win._send()
                        wait_for(lambda:not runtime.busy and runtime.last_request is not previous)
                        assert len(runtime.history)==count+2,(name,win._log.toPlainText()[-1200:])
                        answer=runtime.history[-1]['content'];model=runtime.last_request.get('model');used.add(model)
                        results['commands'][name]={'answer':answer,'model':model,'elapsed_s':time.monotonic()-started}
                        if name=='extract':
                            parsed=json.loads(answer);assert parsed.get('name')=='Ali' and parsed.get('amount')==42,parsed
                        checkpoint()
                    from brave_slash import prepare_send
                    win._input.setText('/shorten @last');expanded=prepare_send(win,'/shorten @last')
                    assert 'Ali' in expanded and '42' in expanded and '@last' not in expanded
                    win._input.setText('/copy');prepare_send(win,'/copy');assert QApplication.clipboard().text()==runtime.history[-1]['content']
                    win._input.setText('/snippets');prepare_send(win,'/snippets');dialog=win._prompt_snippets
                    dialog.title.setText('Budget');dialog.text.setPlainText('/extract name and amount');dialog.save();dialog.insert()
                    assert win._input.text()=='/extract name and amount'
                    results['native_actions']={'last_source':True,'copy':True,'templates':True}
                    assert Settings.read().model=='llama3.2:latest' and Settings.read().profile=='balanced'
                finally:
                    runtime.shutdown();win.close();app.processEvents()
        results['global_settings_unchanged']=config_manager.CONFIG_FILE.read_bytes()==before_cfg
        assert results['global_settings_unchanged'];results['complete']=True;checkpoint()
    finally:
        # Release only models this smoke loaded that were not resident beforehand.
        for model in used-resident:
            if model:
                requests.post(cfg.url+'/api/generate',json={'model':model,'keep_alive':0},timeout=15).raise_for_status()
    print(json.dumps(results,ensure_ascii=True,indent=2),flush=True)


if __name__=='__main__':main()
