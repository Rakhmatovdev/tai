"""Durable comparison results, protected organization drafts and explicit exports."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication,QFileDialog,QMessageBox
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_ollama as fixtures
from core import comparison_store,workspace_store,task_queue,app_recovery,text_export
from core.ollama_chat import Settings


def record():
    return dict(id=comparison_store.new_id(),created=comparison_store.now(),question='17 × 23?',profile='economy',
        models=['local','other:small'],results=['391','391.'],errors=['',''],durations=[1.0,2.0],
        metrics=[dict(first_reply_s=.5,tokens_per_second=20,done_reason='stop'),{}])


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.location=patch.object(workspace_store,'directory',return_value=self.root);self.location.start()
    def tearDown(self):self.location.stop();self.temp.cleanup()

    def test_history_is_bounded_updates_same_run_and_deletes(self):
        value=record();comparison_store.save(value);value['results'][1]='Updated';comparison_store.save(value)
        self.assertEqual(len(comparison_store.rows()),1);self.assertEqual(comparison_store.rows()[0]['results'][1],'Updated')
        for _ in range(24):comparison_store.save(record())
        self.assertEqual(len(comparison_store.rows()),20);self.assertNotIn(value['id'],[row['id'] for row in comparison_store.rows()])
        identity=comparison_store.rows()[0]['id'];comparison_store.delete(identity);self.assertEqual(len(comparison_store.rows()),19)

    def test_corrupt_history_and_untrusted_metrics_are_ignored(self):
        value=record();value['metrics'][0].update(prompt='secret',tokens_per_second=float('nan'),first_reply_s=True)
        comparison_store.save(value);self.assertEqual(comparison_store.rows()[0]['metrics'][0],dict(done_reason='stop'))
        for key,bad in [('results',['','']),('models',['remote:cloud','local']),('durations',[float('inf'),0]),('question','x'*6001),('errors',['x'*2001,''])]:
            invalid=record();invalid[key]=bad
            with self.assertRaises(ValueError):comparison_store.save(invalid)
        workspace_store.write(comparison_store.FILE,[{},None,record()]);self.assertEqual(len(comparison_store.rows()),1)
        workspace_store.write(comparison_store.FILE,{});self.assertEqual(comparison_store.rows(),[])

    def test_backup_includes_comparisons_and_validates_contents(self):
        value=record();comparison_store.save(value);path=self.root/'snapshot.zip';app_recovery.backup(path)
        saved=json.loads(app_recovery.validate(path)[comparison_store.FILE]);self.assertEqual(saved[0]['results'],['391','391.'])

    def test_failed_export_preserves_existing_file_and_cleans_temporary(self):
        target=self.root/'answer.md';target.write_text('original',encoding='utf-8')
        with patch.object(Path,'replace',side_effect=OSError('Disk unavailable')):
            with self.assertRaises(OSError):text_export.write(target,'new')
        self.assertEqual(target.read_text(encoding='utf-8'),'original');self.assertEqual(list(self.root.glob('*.tmp')),[])


class UITests(unittest.TestCase):
    setUpClass=classmethod(fixtures.LocalUITests.setUpClass.__func__)
    setUp=fixtures.LocalUITests.setUp
    wait_for=fixtures.LocalUITests.wait_for
    def tearDown(self):
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):
            for attr in ('_model_duel','_slash_history','_task_queue'):
                dialog=getattr(self.win,attr,None)
                if dialog:dialog.reject()
        manager=getattr(self.win,'_queue_manager',None)
        if manager:manager.shutdown()
        QTest.qWait(30);fixtures.LocalUITests.tearDown(self)

    def duel(self):
        from brave_model_duel import open_duel
        return open_duel(self.win)

    def test_real_transport_result_survives_close_reopen_and_exports_without_inference(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama');before=self.config.read_bytes()
            dialog=self.duel();dialog.pickers[0].setEditText('local');dialog.pickers[1].setEditText('other:small');dialog.prompt.setPlainText('Budget 42?')
            dialog.start();self.wait_for(lambda:not dialog.busy and all(dialog.results),8000)
            self.assertEqual(len(comparison_store.rows()),1);identity=dialog.record_id;expected=list(dialog.results);dialog.reject();QTest.qWait(25)
            count=len(server.requests);dialog=self.duel();dialog.history.setCurrentIndex(dialog.history.findData(identity));dialog.restore()
            self.assertEqual(dialog.results,expected);self.assertFalse(dialog.busy);self.assertEqual(len(server.requests),count)
            self.assertEqual(self.config.read_bytes(),before)
            path=Path(self.temp.name)/'saved.md'
            with patch.object(QFileDialog,'getSaveFileName',return_value=(str(path),'')):dialog.export()
            self.assertIn('Budget 42?',path.read_text(encoding='utf-8'));self.assertIn('Salom dunyo',path.read_text(encoding='utf-8'))

    def test_cancel_second_model_retains_only_first_completed_answer(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama')
            server.chat_handler=lambda payload:([dict(message={'content':'Completed'},done=True)] if payload['model']=='local' else [dict(message={'content':'Partial'}),dict(message={'content':' end'},done=True)])
            # Delay only the second request, after the first result is durably saved.
            dialog=self.duel();dialog.pickers[0].setEditText('local');dialog.pickers[1].setEditText('other:small');dialog.prompt.setPlainText('Question')
            original=dialog.run_side
            def run():
                if dialog.current==1:server.pause=threading.Event()
                original()
            dialog.run_side=run;dialog.start();self.wait_for(lambda:dialog.outputs[1].toPlainText()=='Partial',8000)
            dialog.cancel();server.pause.set();QTest.qWait(50)
            saved=comparison_store.rows()[0];self.assertEqual(saved['results'],['Completed','']);self.assertEqual(saved['errors'][1],'Bekor qilindi.')

    def test_save_failure_keeps_outputs_available_and_reports_it(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama');dialog=self.duel()
            dialog.pickers[0].setEditText('local');dialog.pickers[1].setEditText('other:small');dialog.prompt.setPlainText('Question')
            with patch.object(comparison_store,'save',side_effect=OSError('Full disk')):
                dialog.start();self.wait_for(lambda:not dialog.busy and all(dialog.results),8000)
            self.assertTrue(dialog.buttons['export'].isEnabled());self.assertIn('Full disk',dialog.status.text())

    def test_saved_history_replacement_and_deletion_need_explicit_choice(self):
        value=record();comparison_store.save(value);dialog=self.duel();dialog.history.setCurrentIndex(1);dialog.prompt.setPlainText('My draft')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.No):dialog.restore();dialog.delete_saved()
        self.assertEqual(dialog.prompt.toPlainText(),'My draft');self.assertEqual(len(comparison_store.rows()),1)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):dialog.restore();dialog.delete_saved()
        self.assertEqual(dialog.results,['391','391.']);self.assertEqual(comparison_store.rows(),[])
        dialog.reject();self.assertEqual(comparison_store.rows(),[])

    def history(self):
        from brave_features import HistoryDialog
        store=self.win._features.store
        for identity in ('a','b'):store.append(identity,'user',identity,'now')
        dialog=HistoryDialog(self.win._features);self.win._slash_history=dialog;dialog.show();return dialog

    def select_chat(self,dialog,identity):
        for i in range(dialog.list.count()):
            if dialog.list.item(i).data(Qt.ItemDataRole.UserRole)==identity:dialog.list.setCurrentRow(i);return
        self.fail('Chat is missing')

    def test_organization_drafts_survive_chat_filter_and_page_refresh(self):
        dialog=self.history();self.select_chat(dialog,'a');dialog.tags_edit.setText('unsaved, Python');dialog.pin_edit.setChecked(True)
        self.select_chat(dialog,'b');dialog.tags_edit.setText('second draft');self.select_chat(dialog,'a')
        self.assertEqual(dialog.tags_edit.text(),'unsaved, Python');self.assertTrue(dialog.pin_edit.isChecked())
        dialog.search.setText('b');dialog.timer.stop();dialog.refresh();dialog.search.clear();dialog.timer.stop();dialog.refresh();self.select_chat(dialog,'a')
        self.assertEqual(dialog.tags_edit.text(),'unsaved, Python');dialog.save_organization()
        self.assertEqual(self.win._features.store.chat_info('a')['tags'],['Python','unsaved']);self.assertIn('b',dialog.organization_drafts)

    def test_close_cancel_keeps_drafts_and_explicit_discard_does_not_write(self):
        dialog=self.history();identity=dialog.selected();dialog.tags_edit.setText('do not lose')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.No):dialog.reject()
        self.assertTrue(dialog.isVisible());self.assertEqual(dialog.tags_edit.text(),'do not lose')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):dialog.reject()
        self.assertFalse(dialog.isVisible());self.assertEqual(self.win._features.store.chat_info(identity)['tags'],[])

    def queue(self,status='completed'):
        from brave_task_queue import open_queue
        dialog=open_queue(self.win);row=task_queue.create('Budget','Summarize','Sensitive source',model_settings=Settings(autostart=False))
        row.update(status=status,result='Natija: 42\nПривет');dialog.manager.add(row);return dialog,row

    def test_queue_exports_markdown_and_exact_utf8_text(self):
        dialog,row=self.queue();self.win._input.setText('Unsent draft');path=Path(self.temp.name)/'result.md'
        with patch.object(QFileDialog,'getSaveFileName',return_value=(str(path),'Markdown (*.md)')):dialog.export()
        text=path.read_text(encoding='utf-8');self.assertIn('# Budget',text);self.assertIn(row['result'],text);self.assertNotIn('Sensitive source',text)
        path=path.with_suffix('')
        with patch.object(QFileDialog,'getSaveFileName',return_value=(str(path),'Text (*.txt)')):dialog.export()
        self.assertEqual(path.with_suffix('.txt').read_text(encoding='utf-8'),row['result']);self.assertEqual(self.win._input.text(),'Unsent draft')

    def test_queue_export_rejects_partial_and_revoked_permission(self):
        dialog,row=self.queue('pending')
        with patch.object(QFileDialog,'getSaveFileName') as choose:dialog.export();choose.assert_not_called()
        row['status']='completed';self.win._capabilities.policy['permissions']['files']=False;dialog.describe()
        self.assertFalse(dialog.buttons['export'].isEnabled())
        with patch.object(QFileDialog,'getSaveFileName') as choose:dialog.export();choose.assert_not_called()
        self.win._capabilities.policy['permissions']['files']=True;path=Path(self.temp.name)/'blocked.md'
        def revoke(*args):self.win._capabilities.policy['permissions']['files']=False;return str(path),''
        with patch.object(QFileDialog,'getSaveFileName',side_effect=revoke):dialog.export()
        self.assertFalse(path.exists())


if __name__=='__main__':unittest.main()
