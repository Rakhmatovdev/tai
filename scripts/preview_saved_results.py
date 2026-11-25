"""Offline visual QA with synthetic records and temporary app settings."""
import os
from pathlib import Path
import sys
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
import test_ollama as fixtures
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QMessageBox
from core import comparison_store,task_queue
from core.ollama_chat import Settings
from brave_model_duel import open_duel
from brave_features import HistoryDialog
from brave_task_queue import open_queue
import brave_ui


def main():
    fixtures.LocalUITests.setUpClass();fixture=fixtures.LocalUITests('runTest');fixture.setUp()
    win=fixture.win;target=ROOT/'design-preview'/'saved-results';target.mkdir(parents=True,exist_ok=True)
    try:
        comparison_store.save(dict(id=comparison_store.new_id(),created=comparison_store.now(),question='Compare two approaches to a local document assistant.',
            profile='balanced',models=['llama3.2:latest','qwen2.5-coder:7b'],results=['Use a small local model for short tasks.\nKeep documents on this device.',
            'Use the stronger model for code review.\nReview generated changes before applying.'],errors=['',''],durations=[2.6,4.8],
            metrics=[dict(first_reply_s=.4,tokens_per_second=53),dict(first_reply_s=.9,tokens_per_second=39)]))
        store=win._features.store;store.append('demo','user','Local assistant project','10:20');store.append('demo','assistant','Milestones:\n- Improve local response speed\n- Keep results recoverable\n- Review before applying changes','10:21')
        folder=store.save_folder('Project notes');store.organize('demo',folder,True,['local','planning'])
        for theme in ('dark','light','hacker'):
            for language in ('uz','en','ru'):
                brave_ui.set_theme(win,theme,persist=False);brave_ui.set_language(win,language,persist=False)
                duel=open_duel(win);duel.history.setCurrentIndex(1);duel.restore()
                history=HistoryDialog(win._features);history.show();history.tags_edit.setText('local, planning, draft');history.refresh()
                queue=open_queue(win)
                if not queue.manager.rows:
                    row=task_queue.create('Document summary','Summarize','Synthetic source',model_settings=Settings(autostart=False))
                    row.update(status='completed',result='Completed review\n\n1. Add saved comparisons.\n2. Keep organization drafts.\n3. Export finished results.');queue.manager.add(row)
                for key,widget in [('comparison',duel),('history',history),('queue',queue)]:
                    QTest.qWait(35);available=win.screen().availableGeometry()
                    assert widget.width()<=available.width() and widget.height()<=available.height(),(key,theme,language,widget.size())
                    assert widget.grab().save(str(target/f'{key}-{theme}-{language}.png'))
                with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):history.reject()
                duel.reject();queue.reject();QTest.qWait(20)
        print('27 previews saved; 3 views x 3 themes x 3 languages. No inference was started.')
    finally:
        if getattr(win,'_queue_manager',None):win._queue_manager.shutdown()
        fixture.tearDown()


if __name__=='__main__':main()
