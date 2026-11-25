"""Real local workflow smoke, isolated from personal settings and history."""
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
    from brave_custom_commands import open_commands
    from brave_task_queue import open_queue
    from brave_chat_search import open_search
    from core import workspace_store,task_queue
    from core.ollama_chat import Settings
    from memory import config_manager
    cfg=Settings.read();before_cfg=config_manager.CONFIG_FILE.read_bytes();model='llama3.2:latest'
    session=requests.Session();session.trust_env=False
    resident={row['name'] for row in session.get(cfg.url+'/api/ps',timeout=5).json().get('models',[])}
    installed={row['name'] for row in session.get(cfg.url+'/api/tags',timeout=5).json().get('models',[])}
    assert model in installed,'Install a small local chat model explicitly first.'
    output=Path('logs/productivity-real-smoke.json');results={'complete':False};used=False
    app=QApplication.instance() or QApplication([])
    def checkpoint():output.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    def wait_for(predicate):
        end=time.monotonic()+180
        while not predicate() and time.monotonic()<end:QTest.qWait(20)
        assert predicate(),'Workflow timed out'
    try:
        with tempfile.TemporaryDirectory(prefix='brave-productivity-smoke-') as directory:
            root=Path(directory);config=root/'settings.json'
            config.write_text(json.dumps({'chat_provider':'ollama','ollama_url':cfg.url,'ollama_model':model,
                'ollama_profile':'balanced','ollama_thinking':'off','ollama_autostart':False,'local_voice_reply':False,'ui_language':'en'}),encoding='utf-8')
            with (patch.object(ui,'API_FILE',config),patch.object(config_manager,'CONFIG_FILE',config),
                  patch.object(workspace_store,'directory',return_value=root),patch.object(ui.MainWindow,'_check_config',return_value=True),
                  patch.object(ui.MainWindow,'_check_autostart',return_value=False)):
                win=ui.MainWindow('');win.show();runtime=LocalChat(win);win._local_chat=runtime
                try:
                    print('Custom command through native editor and chat',flush=True)
                    editor=open_commands(win);editor.name.setText('mybrief');editor.title.setText('Short factual summary')
                    editor.text.setPlainText('Summarize the following note in one short sentence. Preserve names, numbers and dates: {input}')
                    editor.model.setText(model);editor.profile.setCurrentIndex(editor.profile.findData('balanced'));assert editor.save();editor.insert()
                    win._input.setText('/mybrief Ali will send the report Monday. The budget is 42 dollars.')
                    started=time.monotonic();used=True;win._send();wait_for(lambda:not runtime.busy and len(runtime.history)==2)
                    answer=runtime.history[-1]['content'];assert '42' in answer,answer
                    results['custom_command']={'model':runtime.last_request['model'],'answer':answer,'elapsed_s':time.monotonic()-started};checkpoint()
                    print('Sequential AI and file-to-text queue',flush=True)
                    dialog=open_queue(win);dialog.title.setText('Budget summary');dialog.instruction.setPlainText('Summarize briefly, preserving the name and budget amount.')
                    dialog.source.setPlainText('Ali has a budget of 42 dollars for Monday.');dialog.add();manager=dialog.manager
                    path=root/'meeting.txt';path.write_text('Budget 42. Ali: Monday.',encoding='utf-8')
                    dialog.title.setText('Text extraction');dialog.kind.setCurrentIndex(dialog.kind.findData('totext'));dialog.paths=[str(path)];dialog.add()
                    win._input.setText('Preserved draft');started=time.monotonic();manager.start()
                    wait_for(lambda:all(row['status'] in ('completed','failed') for row in manager.rows))
                    assert len(manager.rows)==2 and all(row['status']=='completed' for row in manager.rows),manager.rows
                    assert '42' in manager.rows[0]['result'] and 'Budget 42. Ali: Monday.' in manager.rows[1]['result']
                    assert win._input.text()=='Preserved draft'
                    assert len(task_queue.load())==2
                    results['queue']={'elapsed_s':time.monotonic()-started,'jobs':[dict(title=row['title'],status=row['status'],result=row['result']) for row in manager.rows],
                        'draft_preserved':True,'restored_results':True};checkpoint()
                    folder=Path('design-preview/productivity');folder.mkdir(parents=True,exist_ok=True);dialog.grab().save(str(folder/'real-queue-en.png'));dialog.reject()
                    print('Old-page chat search and highlighted jump',flush=True)
                    chat=win._features.chat_id
                    for i in range(140):win._features.store.append(chat,'user' if i%2==0 else 'assistant',f'Synthetic entry {i}'+(' target-needle' if i==8 else ''),'now')
                    win._features.show_page(82);finder=open_search(win,'target-needle');assert finder.list.count()==1
                    finder.grab().save(str(folder/'real-search-en.png'));finder.go();QTest.qWait(100)
                    assert win._features.page_offset==0 and win._input.text()=='Preserved draft'
                    results['search']={'matched':1,'jumped_to_old_page':True,'draft_preserved':True};checkpoint()
                    assert Settings.read().model==model and Settings.read().profile=='balanced'
                finally:
                    manager=getattr(win,'_queue_manager',None)
                    if manager:manager.shutdown()
                    runtime.shutdown();win.close();app.processEvents()
        results['global_settings_unchanged']=config_manager.CONFIG_FILE.read_bytes()==before_cfg;assert results['global_settings_unchanged']
        results['complete']=True;checkpoint()
    finally:
        if used and model not in resident:session.post(cfg.url+'/api/generate',json={'model':model,'keep_alive':0},timeout=15).raise_for_status()
        session.close()
    print(json.dumps(results,ensure_ascii=True,indent=2),flush=True)


if __name__=='__main__':main()
