"""Custom commands, durable queue and paged chat search with real Qt transport."""
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import sys
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication,QMessageBox
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_ollama as fixtures
from core import workspace_store,custom_commands,task_queue,command_store
from core.slash_commands import parse,matches
from core.ollama_chat import Settings
from memory import config_manager


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.location=patch.object(workspace_store,'directory',return_value=self.root);self.location.start()
    def tearDown(self):self.location.stop();self.temp.cleanup()

    def save_command(self,name='myplan',**values):
        return custom_commands.save(name=name,title='My plan',template='Plan this: {input}',**values)

    def test_custom_names_cannot_override_builtins_aliases_or_execute_code(self):
        for name in ('plan','quick','queue','x','a/b','_test','abc def','ábc','name'*7):
            with self.assertRaises(ValueError):self.save_command(name)
        self.save_command('/MyPlan');self.assertEqual(parse('/myplan demo')[0].name,'myplan')
        with self.assertRaises(ValueError):self.save_command('another',model='remote:cloud')

    def test_custom_crud_rename_dynamic_menu_and_favorites(self):
        self.save_command();self.assertIn('myplan',[row.name for row in matches('/myp')])
        command_store.favorite('myplan');command_store.used('myplan');self.assertIn('myplan',command_store.preferences()['favorites'])
        with self.assertRaises(ValueError):self.save_command()
        custom_commands.save('myplan',name='myother',title='Other',template='Reply briefly',profile='economy')
        self.assertEqual(len(custom_commands.rows()),1);self.assertEqual(matches('/myplan'),[])
        self.assertEqual(command_store.preferences()['favorites'],[])
        custom_commands.delete('myother');self.assertEqual(custom_commands.rows(),[])

    def test_custom_render_is_literal_and_pinned_settings_do_not_mutate_defaults(self):
        self.save_command(model='other:small',profile='quality');command,body,_=parse('/myplan {system} /new')
        self.assertEqual(custom_commands.render(command,body),'Plan this: {system} /new')
        default=Settings();selected=custom_commands.request_settings(default,command)
        self.assertEqual((selected.model,selected.profile),('other:small','quality'));self.assertEqual(default,Settings())
        with self.assertRaises(ValueError):custom_commands.render(command,'')
        with self.assertRaises(ValueError):custom_commands.render(command,'a'*12000)

    def test_corrupt_commands_are_ignored_and_capacity_is_bounded(self):
        workspace_store.write(custom_commands.FILE,[None,{},dict(name='invalid',title=8,template='x')]);self.assertEqual(custom_commands.rows(),[])
        for i in range(50):self.save_command('cmd'+str(i))
        with self.assertRaises(ValueError):self.save_command('oneextra')
        custom_commands.save('cmd0',name='cmd0',title='Updated',template='updated')
        self.assertEqual(len(custom_commands.rows()),50)

    def test_queue_preserves_results_and_marks_interrupted_without_running(self):
        row=task_queue.create('Task','Summarize','Ali 42',model_settings=Settings(autostart=False));row['status']='running';task_queue.save([row])
        result=task_queue.load();self.assertEqual(result[0]['status'],'interrupted')
        self.assertEqual(workspace_store.read(task_queue.FILE)[0]['status'],'running')
        row.update(status='completed',result='Budget 42');task_queue.save([row]);self.assertEqual(task_queue.load()[0]['result'],'Budget 42')

    def test_queue_file_changes_are_rejected_and_limits_are_enforced(self):
        path=self.root/'source.txt';path.write_text('old')
        row=task_queue.create('File','Summarize',paths=[path],model_settings=Settings());self.assertEqual(task_queue.verify_paths(row['files']),[str(path.resolve())])
        path.write_text('changed')
        with self.assertRaises(ValueError):task_queue.verify_paths(row['files'])
        for args in [('', 'Task','x'),('Title','','x'),('Title','Task',''),('Title','Task','x'*10001)]:
            with self.assertRaises(ValueError):task_queue.create(*args,model_settings=Settings())
        with self.assertRaises(ValueError):task_queue.save([row]*31)

    def test_queue_corrupt_or_remote_configuration_is_not_loaded(self):
        row=task_queue.create('Task','Summarize','source',model_settings=Settings());row['settings']['url']='http://example.com'
        workspace_store.write(task_queue.FILE,[None,{},row]);self.assertEqual(task_queue.load(),[])

    def test_search_scopes_paginates_casefolds_and_treats_wildcards_as_literals(self):
        from brave_history import HistoryStore
        store=HistoryStore()
        for i in range(130):store.append('a','user',f'САЛОМ {i}'+(' 100% _value' if i==72 else ''),'now')
        store.append('b','assistant','САЛОМ other','now')
        rows=store.search_messages('a','салом',50,51);self.assertEqual(len(rows),51)
        self.assertEqual(store.message_index('a',rows[0][0]),50)
        row=store.search_messages('a','100%')[0];self.assertEqual(store.message_index('a',row[0]),72)
        self.assertEqual(len(store.search_messages('a','_value')),1)
        self.assertIsNone(store.message_index('b',row[0]));self.assertEqual(store.search_messages('a',''),[]);store.close()

    def test_new_registries_are_backed_up(self):
        from core.app_recovery import FILES
        self.assertTrue({task_queue.FILE,custom_commands.FILE}<=FILES)


class UITests(unittest.TestCase):
    setUpClass=classmethod(fixtures.LocalUITests.setUpClass.__func__)
    setUp=fixtures.LocalUITests.setUp
    wait_for=fixtures.LocalUITests.wait_for
    start_local=fixtures.LocalUITests.start_local

    def tearDown(self):
        manager=getattr(self.win,'_queue_manager',None)
        if manager:manager.shutdown()
        for attr in ('_custom_commands','_task_queue','_chat_search','_slash_help'):
            dialog=getattr(self.win,attr,None)
            if dialog:
                if attr=='_custom_commands':dialog.original=dialog.values()
                dialog.reject()
        QTest.qWait(80);fixtures.LocalUITests.tearDown(self)

    def action(self,text):
        from brave_slash import prepare_send
        self.win._input.setText(text);return prepare_send(self.win,text)

    def add_job(self,manager,title='Task',text='Budget 42',paths=(),kind='analysis'):
        row=task_queue.create(title,'Summarize the supplied material.',text,paths,Settings.read(),kind)
        manager.add(row);return row

    def manager(self):
        from brave_task_queue import open_queue
        return open_queue(self.win).manager

    def test_custom_editor_saves_then_inserts_without_sending_and_updates_dropdown(self):
        self.action('/commands');dialog=self.win._custom_commands
        dialog.name.setText('myplan');dialog.title.setText('Personal plan');dialog.text.setPlainText('Make a plan: {input}');self.assertTrue(dialog.save())
        with patch.object(self.win,'on_text_command') as send:dialog.insert();send.assert_not_called()
        self.assertEqual(self.win._input.text(),'/myplan ')
        self.win._input.setText('/myp');self.assertEqual(self.win._slash_menu.list.item(0).data(Qt.ItemDataRole.UserRole),'myplan')

    def test_custom_missing_input_or_permission_preserves_draft(self):
        custom_commands.save(name='myplan',title='Plan',template='Plan: {input}');self.start_local()
        self.win._input.setText('/myplan')
        with patch.object(self.win,'on_text_command') as send:self.win._send();send.assert_not_called()
        self.assertEqual(self.win._input.text(),'/myplan')
        self.win._capabilities.policy['permissions']['files']=False
        self.assertIsNone(self.action('/myplan demo'));self.assertEqual(self.win._input.text(),'/myplan demo')

    def test_pinned_custom_model_profile_and_prompt_reach_actual_transport(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',profile='balanced',autostart=False).save('ollama');config_manager._patch_config(local_tools_enabled=True)
            custom_commands.save(name='myplan',title='Plan',template='Plan this: {input}',model='other:small',profile='quality')
            runtime=self.start_local();previous=self.config.read_bytes()
            with patch('core.model_router.route',side_effect=AssertionError('Pinned model must not be rerouted')):
                self.win._input.setText('/myplan Build a demo');self.win._send();self.wait_for(lambda:not runtime.busy and len(runtime.history)==2)
            payload=[body for path,body in server.requests if path=='/api/chat'][-1]
            self.assertEqual(payload['model'],'other:small');self.assertEqual(payload['options']['num_ctx'],8192)
            self.assertEqual(payload['messages'][-1]['content'],'Plan this: Build a demo');self.assertNotIn('tools',payload)
            self.assertEqual(self.config.read_bytes(),previous)

    def test_static_custom_prompt_and_cloud_expansion_are_supported(self):
        custom_commands.save(name='myhello',title='Hello',template='Say hello briefly.')
        self.win._active_provider='gemini';value=self.action('/myhello');self.assertIn('Say hello briefly.',value)
        custom_commands.save('myhello',name='myhello',title='Hello',template='Say hello.',model='local')
        self.assertIsNone(self.action('/myhello'));self.assertEqual(self.win._input.text(),'/myhello')

    def test_queue_add_does_not_generate_and_start_processes_jobs_in_order(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama');manager=self.manager()
            first=self.add_job(manager,'First','Ali 42');second=self.add_job(manager,'Second','Sara 17')
            QTest.qWait(100);self.assertEqual(server.requests,[]);self.win._input.setText('Keep my draft')
            manager.start();self.wait_for(lambda:all(row['status']=='completed' for row in (first,second)),8000)
            payloads=[body for path,body in server.requests if path=='/api/chat'];self.assertEqual(len(payloads),2)
            self.assertIn('Ali 42',payloads[0]['messages'][-1]['content']);self.assertIn('Sara 17',payloads[1]['messages'][-1]['content'])
            self.assertNotIn('tools',payloads[0]);self.assertEqual(self.win._input.text(),'Keep my draft')
            self.assertEqual(self.win._features.store.count(self.win._features.chat_id),0)
            self.assertEqual(task_queue.load()[1]['result'],'Salom dunyo')

    def test_queue_pause_finishes_current_and_does_not_start_next(self):
        with fixtures.FakeOllama() as server:
            server.before_headers['/api/chat']=threading.Event();Settings(server.url,'local',autostart=False).save('ollama');manager=self.manager()
            first=self.add_job(manager,'First');second=self.add_job(manager,'Second');manager.start()
            self.wait_for(lambda:any(path=='/api/chat' for path,_ in server.requests));manager.pause();server.before_headers['/api/chat'].set()
            self.wait_for(lambda:first['status']=='completed');QTest.qWait(250);self.assertEqual(second['status'],'pending')
            self.assertFalse(manager.enabled);self.assertFalse(manager.timer.isActive())

    def test_queue_cancel_discards_partial_and_ignores_late_completion(self):
        with fixtures.FakeOllama() as server:
            server.pause=threading.Event();Settings(server.url,'local',autostart=False).save('ollama');manager=self.manager();row=self.add_job(manager)
            manager.start();self.wait_for(lambda:manager.job is not None and bool(manager.job.job and manager.job.job.text))
            generation=manager.generation;manager.pause();manager.cancel(row['id']);self.assertEqual(row['status'],'cancelled')
            server.pause.set();manager.finish(generation,'late answer');QTest.qWait(60)
            self.assertEqual(row['result'],'');self.assertEqual(row['status'],'cancelled')

    def test_queue_permission_or_provider_change_stops_active_work(self):
        with fixtures.FakeOllama() as server:
            server.before_headers['/api/chat']=threading.Event();Settings(server.url,'local',autostart=False).save('ollama');manager=self.manager()
            first=self.add_job(manager);second=self.add_job(manager,'Second');manager.start()
            self.wait_for(lambda:any(path=='/api/chat' for path,_ in server.requests))
            self.win._capabilities.policy['permissions']['files']=False;self.wait_for(lambda:first['status']=='failed')
            self.assertEqual(second['status'],'pending');self.assertFalse(manager.enabled);self.assertEqual(first['result'],'')
            self.win._capabilities.policy['permissions']['files']=True;self.win._active_provider='gemini';manager.start();self.assertFalse(manager.enabled)

    def test_queue_recovery_requires_explicit_retry_and_start(self):
        row=task_queue.create('Interrupted','Summarize','source',model_settings=Settings(autostart=False));row['status']='running';task_queue.save([row])
        manager=self.manager();self.assertEqual(manager.rows[0]['status'],'interrupted');QTest.qWait(150)
        self.assertFalse(manager.enabled);self.assertIsNone(manager.active)
        manager.retry(row['id']);self.assertEqual(manager.rows[0]['status'],'pending');self.assertFalse(manager.enabled)

    def test_queue_changed_file_fails_before_inference(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama');path=Path(self.temp.name)/'source.txt';path.write_text('original')
            manager=self.manager();row=self.add_job(manager,paths=[path]);path.write_text('changed content')
            manager.start();self.wait_for(lambda:row['status']=='failed');self.assertEqual(server.requests,[])

    def test_queue_totext_uses_actual_file_conversion_and_inserts_without_sending(self):
        path=Path(self.temp.name)/'source.txt';path.write_text('Budget 42. Ali Monday.')
        manager=self.manager();row=self.add_job(manager,text='',paths=[path],kind='totext')
        manager.start();self.wait_for(lambda:row['status']=='completed');dialog=self.win._task_queue
        self.assertIn('Budget 42.',row['result']);self.win._input.setText('Draft')
        with patch.object(self.win,'on_text_command') as send:dialog.insert();send.assert_not_called()
        self.assertIn('Draft\n\nsource.txt',self.win._input.text())

    def test_queue_batch_adds_one_job_per_file_and_is_atomic_on_failure(self):
        from brave_task_queue import open_queue
        dialog=open_queue(self.win);paths=[]
        for i in range(3):
            path=Path(self.temp.name)/f'source-{i}.txt';path.write_text('Source '+str(i));paths.append(str(path))
        dialog.paths=paths;dialog.separate.setChecked(True);dialog.title.setText('Batch');dialog.kind.setCurrentIndex(dialog.kind.findData('totext'));dialog.add()
        manager=dialog.manager;self.assertEqual(len(manager.rows),3);self.assertTrue(all(len(row['files'])==1 for row in manager.rows));self.assertFalse(manager.enabled)
        dialog.paths=paths;dialog.title.setText('Failed batch')
        with patch('core.task_queue.save',side_effect=OSError('Disk full')):dialog.add()
        self.assertEqual(len(manager.rows),3)
        self.assertEqual(dialog.list.count(),3)

    def test_closing_queue_window_keeps_explicitly_started_work_running(self):
        with fixtures.FakeOllama() as server:
            server.before_headers['/api/chat']=threading.Event();Settings(server.url,'local',autostart=False).save('ollama');manager=self.manager();row=self.add_job(manager)
            manager.start();self.wait_for(lambda:any(path=='/api/chat' for path,_ in server.requests))
            self.win._task_queue.reject();QTest.qWait(20);server.before_headers['/api/chat'].set();self.wait_for(lambda:row['status']=='completed')
            self.assertEqual(row['result'],'Salom dunyo')

    def test_queue_waits_while_main_chat_is_busy(self):
        runtime=self.start_local();runtime.busy=True;manager=self.manager();row=self.add_job(manager);manager.start();QTest.qWait(220)
        self.assertEqual(row['status'],'pending');self.assertIsNone(manager.active);manager.pause();runtime.busy=False

    def test_queue_save_failure_never_starts_inference(self):
        manager=self.manager();row=self.add_job(manager)
        with patch('core.task_queue.save',side_effect=OSError('Disk full')):
            manager.start();self.assertFalse(manager.enabled);self.assertIsNone(manager.active);self.assertEqual(row['status'],'pending')

    def test_queue_shutdown_marks_only_current_job_interrupted(self):
        with fixtures.FakeOllama() as server:
            server.before_headers['/api/chat']=threading.Event();Settings(server.url,'local',autostart=False).save('ollama');manager=self.manager()
            first=self.add_job(manager);second=self.add_job(manager,'Second');manager.start()
            self.wait_for(lambda:any(path=='/api/chat' for path,_ in server.requests));self.win.close()
            self.assertTrue(manager.closed)
            self.assertEqual(first['status'],'interrupted');self.assertEqual(second['status'],'pending');self.assertFalse(manager.timer.isActive())

    def test_find_searches_old_pages_and_jumps_without_changing_chat_or_draft(self):
        store=self.win._features.store;chat=self.win._features.chat_id
        for i in range(145):store.append(chat,'user' if i%2==0 else 'assistant',f'Content {i}'+(' needle' if i==8 else ''),'now')
        store.append('another','assistant','needle from another chat','now')
        self.win._features.show_page(85);self.win._input.setText('Preserve me')
        from brave_chat_search import open_search
        dialog=open_search(self.win,'needle');self.assertEqual(dialog.list.count(),1);dialog.go();QTest.qWait(90)
        self.assertEqual(self.win._features.page_offset,0);self.assertIn('Content 8 needle',self.win._log.toPlainText())
        self.assertEqual(self.win._input.text(),'Preserve me');self.assertEqual(self.win._features.chat_id,chat)
        from brave_chat import MessageCard
        self.assertTrue(self.win._log._rows[8].findChild(MessageCard).body.extraSelections())

    def test_find_busy_guard_and_query_flush(self):
        self.win._features.store.append(self.win._features.chat_id,'user','Find me','now')
        self.action('/find Find');dialog=self.win._chat_search;self.win._features.started=1.0;dialog.go();self.assertTrue(dialog.isVisible())
        self.win._features.started=None;dialog.query.setText('missing');dialog.go();self.assertEqual(dialog.list.count(),0)

    def test_find_shortcut_and_search_pagination(self):
        for i in range(120):self.win._features.store.append(self.win._features.chat_id,'user',f'Needle {i}','now')
        self.win.activateWindow();self.win._input.setFocus();QTest.keyClick(self.win._input,Qt.Key.Key_F,Qt.KeyboardModifier.ControlModifier);QTest.qWait(20)
        dialog=self.win._chat_search;dialog.query.setText('needle');dialog.flush();self.assertEqual(dialog.list.count(),50);self.assertTrue(dialog.next.isEnabled())
        dialog.page(50);self.assertEqual(dialog.offset,50);self.assertTrue(dialog.previous.isEnabled())
        dialog.page(50);self.assertEqual(dialog.list.count(),20);self.assertFalse(dialog.next.isEnabled())

    def test_new_windows_render_in_three_themes_and_languages(self):
        import brave_ui
        from brave_custom_commands import open_commands
        from brave_chat_search import open_search
        from brave_task_queue import open_queue
        for theme in ('dark','light','hacker'):
            for language in ('uz','en','ru'):
                brave_ui.set_theme(self.win,theme,persist=False);brave_ui.set_language(self.win,language,persist=False)
                windows={'commands':open_commands(self.win),'queue':open_queue(self.win),'search':open_search(self.win)}
                for key,widget in windows.items():
                    QTest.qWait(15);self.assertLessEqual(widget.height(),self.win.screen().availableGeometry().height())
                    self.assertLessEqual(widget.width(),self.win.screen().availableGeometry().width())
                    target=os.environ.get('BRAVE_PRODUCTIVITY_PREVIEWS')
                    if target:
                        folder=Path(target);folder.mkdir(parents=True,exist_ok=True);widget.grab().save(str(folder/f'{key}-{theme}-{language}.png'))
                for widget in windows.values():widget.reject()
                QTest.qWait(15)


if __name__=='__main__':unittest.main()
