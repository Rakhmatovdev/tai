"""Model comparison, explicit continuation and durable chat organization."""
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
import sys
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication,QInputDialog,QMessageBox,QFileDialog
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_ollama as fixtures
from brave_history import HistoryStore
from core import workspace_store,continuation
from core.ollama_chat import Settings,PROFILES
from memory import config_manager


class CoreTests(unittest.TestCase):
    def setUp(self):self.store=HistoryStore()
    def tearDown(self):self.store.close()
    def chat(self,identity='a',text='question'):
        self.store.append(identity,'user',text,'now');self.store.append(identity,'assistant','part one','now')
        return identity
    def limited(self,identity='a'):
        self.chat(identity);self.store.record_reply(identity,dict(model='local',profile='balanced',done_reason='length'))

    def test_schema_migrates_existing_database_without_changing_messages(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'old.db';db=sqlite3.connect(path)
            db.executescript("CREATE TABLE chats(id TEXT PRIMARY KEY,title TEXT,updated TEXT); CREATE TABLE messages(seq INTEGER PRIMARY KEY,chat_id TEXT,role TEXT,body TEXT,stamp TEXT); INSERT INTO chats VALUES('a','Old','now'); INSERT INTO messages VALUES(1,'a','user','Original','now');")
            db.close();store=HistoryStore(path);self.assertEqual(store.messages('a'),[('user','Original','now')]);folder=store.save_folder('Work');store.organize('a',folder,True,['code']);store.close()
            store=HistoryStore(path);self.assertEqual(store.chat_info('a'),dict(folder_id=folder,pinned=True,tags=['code']));store.close()

    def test_folder_filter_rename_delete_preserves_chats_and_tags(self):
        self.chat('a','Alpha');self.chat('b','Beta');folder=self.store.save_folder('Work')
        self.store.organize('a',folder,True,['Python','ЛОКАЛ']);self.store.save_folder('Renamed',folder)
        self.assertEqual([row[0] for row in self.store.search(folder_id=folder)],['a'])
        self.assertEqual([row[0] for row in self.store.search(folder_id='')],['b'])
        self.assertEqual([row[0] for row in self.store.search(pinned_only=True,tag='локал')],['a'])
        self.store.delete_folder(folder);self.assertEqual(self.store.chat_info('a')['folder_id'],None)
        self.assertEqual(self.store.count('a'),2);self.assertTrue(self.store.chat_info('a')['pinned'])

    def test_organization_validation_is_atomic_and_unicode_names_are_unique(self):
        self.chat();folder=self.store.save_folder('РАБОТА');self.store.organize('a',folder,True,['Code','code'])
        self.assertEqual(self.store.chat_info('a')['tags'],['Code'])
        with self.assertRaises(ValueError):self.store.save_folder('работа')
        for tags in (['x'*33],['x,y'],[str(i) for i in range(9)]):
            with self.assertRaises(ValueError):self.store.organize('a',None,False,tags)
        self.assertEqual(self.store.chat_info('a'),dict(folder_id=folder,pinned=True,tags=['Code']))
        with self.assertRaises(ValueError):self.store.organize('a','missing',False,[])
        for name in ('','x'*41,'bad\nname'):
            with self.assertRaises(ValueError):self.store.save_folder(name)

    def test_folder_capacity_and_chat_pagination_keep_pinned_first(self):
        for i in range(30):self.store.save_folder(str(i))
        with self.assertRaises(ValueError):self.store.save_folder('extra')
        for i in range(110):self.chat(str(i),str(i))
        self.store.organize('0',pinned=True)
        self.assertEqual(self.store.search()[0][0],'0');self.assertEqual(len(self.store.search(offset=100)),10)

    def test_branch_copies_folder_tags_and_reply_metadata_without_pinning(self):
        self.limited();folder=self.store.save_folder('Work');self.store.organize('a',folder,True,['tag'])
        branch=self.store.fork('a',2);self.assertEqual(self.store.chat_info(branch),dict(folder_id=folder,pinned=False,tags=['tag']))
        self.assertTrue(self.store.continuation(branch));self.assertNotEqual(self.store.continuation(branch)['seq'],self.store.continuation('a')['seq'])

    def test_continuation_requires_length_reason_and_is_invalidated_by_new_question(self):
        self.chat();self.assertIsNone(self.store.continuation('a'))
        self.store.record_reply('a',dict(model='local',profile='balanced',done_reason='stop'));self.assertIsNone(self.store.continuation('a'))
        self.store.record_reply('a',dict(model='local',profile='balanced',done_reason='length'));self.assertTrue(self.store.continuation('a'))
        self.store.append('a','user','Davom ettir','now');self.assertTrue(self.store.continuation('a'))
        self.store.append('a','user','New question','now');self.assertIsNone(self.store.continuation('a'))

    def test_continuation_context_is_bounded_and_preserves_answer_tail(self):
        context=dict(question='Original '*2000,answer='Beginning '*2000+'END',model='local',profile='balanced')
        for profile in PROFILES:
            rows=continuation.messages(context,profile,'uz')
            self.assertEqual([row['role'] for row in rows],['system','user','assistant','user'])
            self.assertTrue(rows[2]['content'].endswith('END'));self.assertLessEqual(sum(len(row['content']) for row in rows[1:]),PROFILES[profile]['chars'])

    def test_chat_deletion_cascades_organization_and_reply_metadata(self):
        self.limited();folder=self.store.save_folder('Work');self.store.organize('a',folder,True,['tag']);self.store.delete('a')
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM reply_metadata').fetchone()[0],0)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM chat_tags').fetchone()[0],0);self.assertEqual(len(self.store.folders()),1)


class UITests(unittest.TestCase):
    setUpClass=classmethod(fixtures.LocalUITests.setUpClass.__func__)
    setUp=fixtures.LocalUITests.setUp
    wait_for=fixtures.LocalUITests.wait_for
    start_local=fixtures.LocalUITests.start_local
    def tearDown(self):
        for attr in ('_model_duel','_slash_history'):
            dialog=getattr(self.win,attr,None)
            if dialog:dialog.reject()
        QTest.qWait(30);fixtures.LocalUITests.tearDown(self)

    def duel(self):
        from brave_model_duel import open_duel
        dialog=open_duel(self.win);dialog.pickers[0].setEditText('local');dialog.pickers[1].setEditText('other:small');dialog.prompt.setPlainText('What is 2 plus 2?');return dialog

    def start_limited(self,server):
        server.chunks=[{'message':{'content':'First part of the answer.'},'done':True,'done_reason':'length'}]
        Settings(server.url,'local',autostart=False).save('ollama');runtime=self.start_local();self.win._input.setText('Write a detailed answer.');self.win._send()
        self.wait_for(lambda:not runtime.busy and len(runtime.history)==2);return runtime

    def test_duel_sends_same_prompt_profile_sequentially_and_keeps_chat_settings(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama');dialog=self.duel();before=self.config.read_bytes();self.win._input.setText('Unsent draft')
            server.chat_handler=lambda payload:[dict(message={'content':payload['model']+' answer'},done=True,eval_count=5,eval_duration=100000000)]
            dialog.start();self.wait_for(lambda:not dialog.busy and all(dialog.results),8000)
            requests=[body for path,body in server.requests if path=='/api/chat'];self.assertEqual(len(requests),2)
            self.assertEqual([row['model'] for row in requests],['local','other:small']);self.assertEqual(requests[0]['messages'],requests[1]['messages']);self.assertEqual(requests[0]['options'],requests[1]['options'])
            self.assertEqual(requests[0]['messages'][-1]['content'],'What is 2 plus 2?');self.assertNotIn('tools',requests[0])
            self.assertEqual(self.win._input.text(),'Unsent draft');self.assertEqual(self.config.read_bytes(),before);self.assertEqual(self.win._features.store.count(self.win._features.chat_id),0)
            self.assertIn('tokens_per_second',dialog.metrics[0])

    def test_duel_model_refresh_is_read_only_and_does_not_generate(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama');dialog=self.duel();dialog.refresh_models();self.wait_for(lambda:dialog.worker is None)
            self.assertEqual(dialog.pickers[0].count(),2);self.assertEqual([path for path,_ in server.requests],['/api/tags'])

    def test_duel_rejects_duplicate_models_and_wrong_provider(self):
        dialog=self.duel();dialog.pickers[1].setEditText('local:latest');dialog.start();self.assertFalse(dialog.busy)
        self.win._active_provider='gemini';dialog.pickers[1].setEditText('other:small');dialog.start();self.assertFalse(dialog.busy)

    def test_duel_first_model_failure_still_runs_second(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama');dialog=self.duel();dialog.pickers[0].setEditText('missing')
            dialog.start();self.wait_for(lambda:not dialog.busy and bool(dialog.results[1]),8000)
            self.assertEqual(dialog.results[0],'');self.assertEqual(dialog.results[1],'Salom dunyo')

    def test_duel_cancel_discards_partial_and_does_not_start_second_model(self):
        with fixtures.FakeOllama() as server:
            server.pause=threading.Event();Settings(server.url,'local',autostart=False).save('ollama');dialog=self.duel();dialog.start()
            self.wait_for(lambda:bool(dialog.outputs[0].toPlainText()));dialog.cancel();server.pause.set();QTest.qWait(80)
            self.assertEqual(dialog.results,['','']);self.assertEqual(dialog.outputs[0].toPlainText(),'')
            self.assertEqual(len([path for path,_ in server.requests if path=='/api/chat']),1)

    def test_duel_provider_change_cancels_work(self):
        with fixtures.FakeOllama() as server:
            server.before_headers['/api/chat']=threading.Event();Settings(server.url,'local',autostart=False).save('ollama');dialog=self.duel();dialog.start()
            self.wait_for(lambda:any(path=='/api/chat' for path,_ in server.requests));self.win._active_provider='gemini';self.wait_for(lambda:not dialog.busy)
            self.assertEqual(dialog.results,['',''])

    def test_duel_waits_for_shared_inference_gate_and_cancel_keeps_other_owner(self):
        from core.local_jobs import gate
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama');dialog=self.duel();ticket=gate.try_acquire();self.assertIsNotNone(ticket)
            try:
                dialog.start();QTest.qWait(150);self.assertEqual(server.requests,[]);dialog.cancel();self.assertEqual(gate.active,ticket)
            finally:gate.release(ticket)

    def test_duel_copy_insert_and_export_only_completed_results(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama');dialog=self.duel();dialog.start();self.wait_for(lambda:not dialog.busy and all(dialog.results),8000)
            dialog.copy(0);self.assertEqual(QApplication.clipboard().text(),'Salom dunyo');self.win._input.setText('Draft');dialog.insert(1);self.assertEqual(self.win._input.text(),'Draft\n\nSalom dunyo')
            path=Path(self.temp.name)/'duel.md'
            with patch.object(QFileDialog,'getSaveFileName',return_value=(str(path),'')):dialog.export()
            self.assertIn('other:small',path.read_text(encoding='utf-8'))

    def test_continue_button_uses_prior_model_profile_and_preserves_draft_attachments(self):
        from brave_chat import MessageCard
        with fixtures.FakeOllama() as server:
            runtime=self.start_limited(server);context=self.win._features.store.continuation(self.win._features.chat_id);self.assertTrue(context)
            card=self.win._log._rows[-1].findChild(MessageCard);self.wait_for(lambda:card.continue_button.isVisible())
            Settings(server.url,'other:small',profile='quality',autostart=False).save('ollama')
            path=Path(self.temp.name)/'unsent.txt';path.write_text('Do not send this file.');self.win._drop_zone._set_file(str(path));self.win._input.setText('Unsent draft')
            server.chunks=[{'message':{'content':'Second part.'},'done':True,'done_reason':'stop'}]
            QTest.mouseClick(card.continue_button,Qt.MouseButton.LeftButton);self.wait_for(lambda:not runtime.busy and len(runtime.history)==4)
            payload=[body for route,body in server.requests if route=='/api/chat'][-1]
            self.assertEqual(payload['model'],'local');self.assertEqual(payload['options']['num_ctx'],4096);self.assertNotIn('tools',payload)
            self.assertEqual(payload['messages'][2]['content'],'First part of the answer.')
            self.assertEqual(self.win._input.text(),'Unsent draft');self.assertEqual(self.win._drop_zone.current_files(),[str(path)])
            self.assertEqual(self.win._features.store.files(self.win._features.chat_id,2),[])
            self.assertEqual(Settings.read().model,'other:small');self.assertIsNone(self.win._features.store.continuation(self.win._features.chat_id))

    def test_continue_is_not_automatic_and_stale_source_is_rejected(self):
        from brave_continuation import continue_answer
        with fixtures.FakeOllama() as server:
            self.start_limited(server);context=self.win._features.store.continuation(self.win._features.chat_id);QTest.qWait(100)
            self.assertEqual(len([path for path,_ in server.requests if path=='/api/chat']),1)
            self.assertFalse(continue_answer(self.win,context['seq']+1));self.win._features.store.append(self.win._features.chat_id,'user','Different question','now')
            self.assertFalse(continue_answer(self.win));self.assertEqual(len([path for path,_ in server.requests if path=='/api/chat']),1)

    def test_continue_busy_and_live_meeting_guards_keep_draft(self):
        from brave_continuation import continue_answer
        with fixtures.FakeOllama() as server:
            self.start_limited(server);self.win._input.setText('Draft');self.win._meeting_recording=True
            self.assertFalse(continue_answer(self.win));self.win._meeting_recording=False;self.win._features.started=1.0
            self.assertFalse(continue_answer(self.win));self.win._features.started=None;self.assertEqual(self.win._input.text(),'Draft')

    def test_continue_is_hidden_when_viewing_older_page_with_identical_answer(self):
        from brave_chat import MessageCard
        with fixtures.FakeOllama() as server:
            self.start_limited(server);store=self.win._features.store;chat=self.win._features.chat_id
            for i in range(70):store.append(chat,'user','Question '+str(i),'now')
            store.append(chat,'assistant','First part of the answer.','now');store.record_reply(chat,dict(model='local',profile='balanced',done_reason='length'))
            self.win._features.show_page(0);QTest.qWait(30)
            self.assertTrue(all(not row.findChild(MessageCard).continue_button.isVisible() for row in self.win._log._rows if row.findChild(MessageCard).role=='ai'))

    def test_continue_cancel_and_retry_excludes_partial_from_history(self):
        from brave_continuation import continue_answer
        with fixtures.FakeOllama() as server:
            runtime=self.start_limited(server);server.pause=threading.Event();server.chunks=[{'message':{'content':'Partial'},'done':False},{'message':{'content':' finished'},'done':True}]
            self.assertTrue(continue_answer(self.win));self.wait_for(lambda:runtime.job is not None and bool(runtime.job.text));runtime.cancel();server.pause.set()
            self.assertEqual(len(runtime.history),2);self.assertTrue(self.win._features.store.continuation(self.win._features.chat_id))
            server.pause=None;server.chunks=[{'message':{'content':'Final continuation'},'done':True}]
            self.assertTrue(continue_answer(self.win));self.wait_for(lambda:not runtime.busy and len(runtime.history)==4)
            self.assertEqual(runtime.history[-1]['content'],'Final continuation')

    def test_continue_metadata_survives_database_reopen_and_theme_rebuild(self):
        import brave_ui
        from brave_chat import MessageCard
        with fixtures.FakeOllama() as server:
            self.start_limited(server);brave_ui.set_theme(self.win,'light',persist=False)
            self.wait_for(lambda:self.win._log._rows[-1].findChild(MessageCard).continue_button.isVisible())
            original=self.win._features.store;path=Path(self.temp.name)/'saved.db';backup=sqlite3.connect(path);original.db.backup(backup);backup.close()
            saved=HistoryStore(path);self.assertTrue(saved.continuation(self.win._features.chat_id));saved.close()

    def test_continue_metadata_handles_model_output_with_surrounding_whitespace(self):
        with fixtures.FakeOllama() as server:
            server.chunks=[dict(message={'content':'\nFirst part.\n'},done=True,done_reason='length')]
            Settings(server.url,'local',autostart=False).save('ollama');runtime=self.start_local();self.win._input.setText('Write a detailed answer');self.win._send()
            self.wait_for(lambda:not runtime.busy and len(runtime.history)==2)
            context=self.win._features.store.continuation(self.win._features.chat_id);self.assertIsNotNone(context);self.assertEqual(context['answer'],'First part.')

    def test_folders_ui_assigns_filters_pins_and_keeps_draft(self):
        from brave_features import HistoryDialog
        store=self.win._features.store;store.append('a','user','Work chat','now');store.append('b','user','Other chat','now');folder=store.save_folder('Work')
        dialog=HistoryDialog(self.win._features);self.win._slash_history=dialog;dialog.show()
        for i in range(dialog.list.count()):
            if dialog.list.item(i).data(Qt.ItemDataRole.UserRole)=='a':dialog.list.setCurrentRow(i)
        dialog.folder_edit.setCurrentIndex(dialog.folder_edit.findData(folder));dialog.tags_edit.setText('code, Uzbek');dialog.pin_edit.setChecked(True)
        self.win._input.setText('Draft');dialog.save_organization()
        self.assertEqual(store.chat_info('a'),dict(folder_id=folder,pinned=True,tags=['code','Uzbek']))
        dialog.folder_filter.setCurrentIndex(dialog.folder_filter.findData(folder));dialog.timer.stop();dialog.refresh()
        self.assertEqual(dialog.list.count(),1);self.assertEqual(dialog.selected(),'a');self.assertEqual(self.win._input.text(),'Draft')

    def test_folder_dialog_creates_renames_and_deletes_folder_without_deleting_chat(self):
        from brave_features import HistoryDialog
        store=self.win._features.store;store.append('a','user','Chat','now');dialog=HistoryDialog(self.win._features);self.win._slash_history=dialog
        with patch.object(QInputDialog,'getText',return_value=('Work',True)):dialog.new_folder()
        folder=store.folders()[0][0];dialog.folder_edit.setCurrentIndex(dialog.folder_edit.findData(folder))
        # Refresh the folder choices after new_folder before assigning.
        dialog.show_chat();dialog.folder_edit.setCurrentIndex(dialog.folder_edit.findData(folder));dialog.save_organization()
        dialog.folder_filter.setCurrentIndex(dialog.folder_filter.findData(folder));dialog.timer.stop();dialog.refresh()
        with patch.object(QInputDialog,'getText',return_value=('Renamed',True)):dialog.rename_folder()
        self.assertEqual(store.folders()[0][1],'Renamed')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):dialog.delete_folder()
        self.assertEqual(store.folders(),[]);self.assertEqual(store.count('a'),1)

    def test_history_active_chat_cannot_be_deleted_while_busy(self):
        from brave_features import HistoryDialog
        store=self.win._features.store;chat=self.win._features.chat_id;store.append(chat,'user','Active','now')
        dialog=HistoryDialog(self.win._features);self.win._slash_history=dialog;self.win._features.started=1.0
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):dialog.delete()
        self.assertEqual(store.count(chat),1);self.win._features.started=None

    def test_history_chat_list_paginates_beyond_one_hundred(self):
        from brave_features import HistoryDialog
        for i in range(120):self.win._features.store.append(str(i),'user',str(i),'now')
        dialog=HistoryDialog(self.win._features);self.win._slash_history=dialog;self.assertEqual(dialog.list.count(),100);dialog.chat_page(100);self.assertEqual(dialog.list.count(),20)

    def test_renaming_pinned_chat_does_not_add_the_pin_marker_to_its_title(self):
        from brave_features import HistoryDialog
        store=self.win._features.store;store.append('a','user','Original title','now');store.organize('a',pinned=True)
        dialog=HistoryDialog(self.win._features);self.win._slash_history=dialog
        with patch.object(QInputDialog,'getText',return_value=('Updated title',True)) as edit:
            dialog.rename();self.assertEqual(edit.call_args.kwargs['text'],'Original title')
        self.assertEqual(store.title('a'),'Updated title');self.assertTrue(store.chat_info('a')['pinned'])

    def test_new_slash_actions_open_duel_and_folders_without_sending(self):
        from brave_slash import prepare_send
        with patch('brave_model_duel.open_duel') as handler:
            self.win._input.setText('/duel');prepare_send(self.win,'/duel');handler.assert_called_once_with(self.win)
        self.win._input.setText('/folders');prepare_send(self.win,'/folders');self.assertTrue(self.win._slash_history.isVisible())
        self.win._input.setText('/continue');prepare_send(self.win,'/continue');self.assertEqual(self.win._input.text(),'/continue')

    def test_new_views_render_with_long_folder_names_in_all_themes_and_languages(self):
        import brave_ui
        from brave_features import HistoryDialog
        store=self.win._features.store;store.append('a','user','Saved chat','now');folder=store.save_folder('W'*40);store.organize('a',folder,True,['tag'])
        self.win._log.append_log('You: Long question');self.win._log.append_log('Brave: A length-limited answer.')
        store.record_reply(self.win._features.chat_id,dict(model='local',profile='balanced',done_reason='length'))
        for theme in ('dark','light','hacker'):
            for language in ('uz','en','ru'):
                brave_ui.set_theme(self.win,theme,persist=False);brave_ui.set_language(self.win,language,persist=False)
                duel=self.duel();history=HistoryDialog(self.win._features);self.win._slash_history=history;history.show()
                self.win._log.retheme()
                for key,widget in [('duel',duel),('folders',history),('continue',self.win._log)]:
                    QTest.qWait(25);self.assertLessEqual(widget.width(),self.win.screen().availableGeometry().width());self.assertLessEqual(widget.height(),self.win.screen().availableGeometry().height())
                    target=os.environ.get('BRAVE_COMPARE_PREVIEWS')
                    if target:
                        path=Path(target);path.mkdir(parents=True,exist_ok=True);widget.grab().save(str(path/f'{key}-{theme}-{language}.png'))
                duel.reject();history.reject();self.win._slash_history=None;QTest.qWait(15)


if __name__=='__main__':unittest.main()
