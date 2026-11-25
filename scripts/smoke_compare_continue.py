"""Real model comparison and length-limited continuation on synthetic data only."""
import json
import os
from pathlib import Path
import sqlite3
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
    from PyQt6.QtCore import Qt
    from brave_local_chat import LocalChat
    from brave_model_duel import open_duel
    from brave_chat import MessageCard
    from brave_features import HistoryDialog
    from brave_history import HistoryStore
    from core import workspace_store
    from core.ollama_chat import Settings
    from memory import config_manager
    cfg=Settings.read();original=config_manager.CONFIG_FILE.read_bytes()
    models=['llama3.2:latest','qwen2.5-coder:7b'];used=set();session=requests.Session();session.trust_env=False
    resident={row['name'] for row in session.get(cfg.url+'/api/ps',timeout=5).json().get('models',[])}
    installed={row['name'] for row in session.get(cfg.url+'/api/tags',timeout=5).json().get('models',[])}
    assert set(models)<=installed,'Explicitly install the two models before running this smoke.'
    app=QApplication.instance() or QApplication([]);result={'complete':False};output=Path('logs/compare-real-smoke.json')
    def checkpoint():output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    def wait_for(predicate):
        end=time.monotonic()+240
        while not predicate() and time.monotonic()<end:QTest.qWait(20)
        assert predicate(),'Workflow timed out'
    folder=Path('design-preview/compare');folder.mkdir(parents=True,exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix='brave-compare-smoke-') as directory:
            root=Path(directory);config=root/'settings.json'
            config.write_text(json.dumps({'chat_provider':'ollama','ollama_url':cfg.url,'ollama_model':models[0],'ollama_profile':'economy',
                'ollama_autostart':False,'ollama_thinking':'off','local_voice_reply':False,'ui_language':'en'}),encoding='utf-8')
            with (patch.object(ui,'API_FILE',config),patch.object(config_manager,'CONFIG_FILE',config),patch.object(workspace_store,'directory',return_value=root),
                  patch.object(ui.MainWindow,'_check_config',return_value=True),patch.object(ui.MainWindow,'_check_autostart',return_value=False)):
                win=ui.MainWindow('');win.show();runtime=LocalChat(win);win._local_chat=runtime
                try:
                    print('Compare two actual models',flush=True)
                    duel=open_duel(win)
                    for picker,model in zip(duel.pickers,models):picker.setEditText(model)
                    duel.profile.setCurrentIndex(duel.profile.findData('economy'));duel.prompt.setPlainText('What is 17 times 23? Give the result and a brief arithmetic check.')
                    used.update(models);duel.start();wait_for(lambda:not duel.busy)
                    assert all(duel.results) and all('391' in text for text in duel.results),duel.results
                    result['comparison']=[dict(model=models[i],answer=duel.results[i],elapsed_s=duel.durations[i],metrics=duel.metrics[i]) for i in range(2)];checkpoint()
                    duel.grab().save(str(folder/'real-duel-en.png'));duel.reject()
                    print('Generate a real length-limited answer',flush=True)
                    win._input.setText('Give 40 numbered tips for writing clear Python functions. Explain each tip in a full sentence. Begin with 1.')
                    win._send();wait_for(lambda:not runtime.busy and len(runtime.history)==2)
                    result['length_test']=dict(metrics=runtime.last_request,answer_head=runtime.history[-1]['content'][:400]);checkpoint()
                    assert runtime.last_request.get('done_reason')=='length',(runtime.last_request,runtime.history[-1]['content'])
                    context=win._features.store.continuation(win._features.chat_id);assert context
                    win._input.setText('Preserved draft');card=win._log._rows[-1].findChild(MessageCard)
                    wait_for(lambda:card.continue_button.isVisible() and card.continue_button.isEnabled())
                    win._log.grab().save(str(folder/'real-continue-en.png'))
                    first_metrics=dict(runtime.last_request);started=time.monotonic();QTest.mouseClick(card.continue_button,Qt.MouseButton.LeftButton)
                    wait_for(lambda:not runtime.busy and len(runtime.history)==4)
                    assert win._input.text()=='Preserved draft'
                    result['continuation']=dict(first_metrics=first_metrics,next_metrics=runtime.last_request,elapsed_s=time.monotonic()-started,
                        first_tail=runtime.history[1]['content'][-400:],next_head=runtime.history[-1]['content'][:600],draft_preserved=True)
                    checkpoint()
                    print('Organize and restore chat metadata',flush=True)
                    store=win._features.store;chat=win._features.chat_id;identity=store.save_folder('Project demos')
                    history=HistoryDialog(win._features);history.show();history.folder_edit.setCurrentIndex(history.folder_edit.findData(identity));history.tags_edit.setText('local, demo');history.pin_edit.setChecked(True);history.save_organization()
                    history.folder_filter.setCurrentIndex(history.folder_filter.findData(identity));history.timer.stop();history.refresh();assert history.selected()==chat and history.list.count()==1
                    history.grab().save(str(folder/'real-folders-en.png'));history.reject()
                    target=root/'history.sqlite3';backup=sqlite3.connect(target);store.db.backup(backup);backup.close();reopened=HistoryStore(target)
                    info=reopened.chat_info(chat);assert info==dict(folder_id=identity,pinned=True,tags=['demo','local']);assert reopened.count(chat)==4;reopened.close()
                    result['folders']=dict(restored=True,metadata=info,chat_messages_preserved=4)
                    assert Settings.read().model==models[0] and Settings.read().profile=='economy'
                finally:
                    if getattr(win,'_model_duel',None):win._model_duel.reject()
                    runtime.shutdown();win.close();app.processEvents()
        result['global_settings_unchanged']=config_manager.CONFIG_FILE.read_bytes()==original;assert result['global_settings_unchanged']
        result['complete']=True;checkpoint()
    finally:
        for model in used-resident:session.post(cfg.url+'/api/generate',json={'model':model,'keep_alive':0},timeout=15).raise_for_status()
        session.close()
    print(json.dumps(result,ensure_ascii=True,indent=2),flush=True)


if __name__=='__main__':main()
