"""Regression checks for retrieval, inference arbitration, branches and recoverable app state."""
import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_ollama as fixtures
from PyQt6.QtTest import QTest
from core import chat_memory,local_documents,knowledge,local_tools,app_recovery,workspace_store
from core.local_jobs import JobGate,Cancelled,gate
from core.ollama_chat import Settings
from brave_history import HistoryStore
from brave_ollama_request import ChatRequest
from memory import config_manager


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.cancel=threading.Event();self.settings=Settings('http://127.0.0.1:1','local',autostart=False)

    def test_zero_evidence_never_returns_leading_chunks(self):
        path=self.root/'notes.txt';path.write_text('Apples and pears.',encoding='utf-8')
        self.assertEqual(local_documents.retrieve([path],'rocket launch',500,self.cancel)[0],[])

    def test_semantic_index_retrieves_paraphrase_and_reuses_unchanged_file(self):
        path=self.root/'notes.txt';path.write_text('The payment deadline is Monday.',encoding='utf-8')
        store=knowledge.KnowledgeStore(self.root/'index.db');self.addCleanup(store.close)
        with patch.object(knowledge,'model_stamp',return_value='a'*64),patch.object(knowledge,'embeddings',side_effect=lambda *args:[[1.,0.] for _ in args[2]]) as embed:
            store.index([path],self.settings,'embedding',self.cancel)
            store.index([path],self.settings,'embedding',self.cancel)
            self.assertEqual(embed.call_count,1)
            rows,_=store.retrieve([path],'Pulni qachon berish kerak?',100,self.cancel,self.settings)
            self.assertIn('Monday',rows[0]['text'])
            self.assertLessEqual(sum(len(row['text']) for row in rows),100)
            with patch.object(knowledge,'model_stamp',return_value='b'*64):
                with self.assertRaisesRegex(ValueError,'o‘zgargan'):store.retrieve([path],'qachon?',100,self.cancel,self.settings)

    def test_changed_file_does_not_reuse_stale_excerpts(self):
        path=self.root/'notes.txt';path.write_text('Budget is 42.',encoding='utf-8')
        store=knowledge.KnowledgeStore(self.root/'index.db');self.addCleanup(store.close)
        store.index([path],self.settings,'',self.cancel)
        path.write_text('Budget is 99.',encoding='utf-8')
        rows,_=store.retrieve([path],'budget',100,self.cancel,self.settings)
        self.assertIn('99',rows[0]['text']);self.assertNotIn('42',rows[0]['text'])

    def test_cancelled_reindex_retains_previous_index(self):
        path=self.root/'notes.txt';path.write_text('Budget is 42.',encoding='utf-8')
        store=knowledge.KnowledgeStore(self.root/'index.db');self.addCleanup(store.close)
        store.index([path],self.settings,'',self.cancel);self.cancel.set()
        with self.assertRaises(Cancelled):store.index([path],self.settings,'',self.cancel)
        self.assertEqual(store.list()[0][2],1)


class StateTests(unittest.TestCase):
    def test_long_message_coverage_advances_only_after_all_segments_are_seen(self):
        history=[{'role':'user','content':'x'*14000+' LATE_FACT_42'},{'role':'assistant','content':'ack'}]
        memory={'enabled':True,'summary':'','covered':0,'offset':0};seen=''
        for _ in range(6):
            plan=chat_memory.summary_plan(memory,history,0)
            if plan is None:break
            covered,messages,offset=plan
            seen+=messages[1]['content'].split('Older conversation segment:\n')[1]
            memory.update(covered=covered,offset=offset)
        self.assertIn('LATE_FACT_42',seen);self.assertEqual(memory['covered'],2);self.assertEqual(memory['offset'],0)

    def test_paging_branch_facts_and_deleted_parent_are_independent(self):
        store=HistoryStore();self.addCleanup(store.close)
        for index in range(200):store.append('root','user' if index%2==0 else 'assistant',str(index),'12:00')
        store.add_fact('root','decision','use blue',12);store.add_fact('root','fact','later',100)
        branch=store.fork('root',40)
        self.assertEqual(store.page('root',60,3)[0][1],'60')
        self.assertEqual(store.count(branch),40);self.assertEqual(len(store.facts(branch)),1)
        self.assertEqual(len(store.branches(branch)),2)
        store.delete('root');self.assertEqual(store.count(branch),40);self.assertEqual(len(store.facts(branch)),1)

    def test_job_gate_prefers_foreground_and_waiter_can_cancel(self):
        gate=JobGate();cancel=threading.Event();owner=gate.acquire(cancel);order=[];threads=[]
        def work(priority):
            with gate.hold(cancel,priority):order.append(priority)
        for priority in (10,0):
            thread=threading.Thread(target=work,args=(priority,));thread.start();threads.append(thread)
        deadline=time.monotonic()+2
        while len(gate.waiters)<2 and time.monotonic()<deadline:time.sleep(.01)
        gate.release(owner)
        for thread in threads:thread.join(2)
        self.assertEqual(order,[0,10])
        cancel.set()
        with self.assertRaises(Cancelled):gate.acquire(cancel)
        self.assertIsNone(gate.active)

    def test_arithmetic_rejects_execution_and_unbounded_work(self):
        self.assertEqual(local_tools.calculate('(12 - 5) * 3'),21)
        for expression in ('__import__("os")','2**999999','(1+','True','1/0','[1]*9999'):
            with self.subTest(expression=expression),self.assertRaises(ValueError):local_tools.calculate(expression)

    def test_word_error_rate_is_computed_from_reference(self):
        from core.offline_voice import word_error_rate
        self.assertEqual(word_error_rate('hello blue folder','Hello blue folder.'),0)
        self.assertAlmostEqual(word_error_rate('hello blue folder','hello red folder'),1/3)


class RecoveryTests(unittest.TestCase):
    @unittest.skipUnless(os.name=='nt','Windows installer')
    def test_per_user_installer_updates_and_rolls_back_without_touching_shortcuts(self):
        import shutil,subprocess
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'package';source.mkdir();(source/'Brave').mkdir()
            (source/'Brave/Brave.exe').write_bytes(b'synthetic test executable, never run')
            script=source/'Install-Brave.ps1'
            shutil.copyfile(Path(__file__).resolve().parent.parent/'packaging/Install-Brave.ps1',script)
            target=root/'installed'
            command=['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script),'-InstallDirectory',str(target),'-SkipShortcut']
            def run(extra=()):
                result=subprocess.run(command+list(extra),capture_output=True,text=True,timeout=30,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                self.assertEqual(result.returncode,0,result.stderr)
                return json.loads((target/'installation.json').read_text(encoding='utf-8-sig'))
            first=run();second=run();self.assertNotEqual(first['current'],second['current'])
            self.assertEqual(second['previous'],first['current'])
            restored=run(['-Rollback']);self.assertEqual(restored['current'],first['current'])

    def test_verified_restore_preserves_secret_and_keeps_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);cfg=root/'config.json';cfg.write_text(json.dumps({'gemini_api_key':'keep-secret','ollama_model':'first'}))
            with patch.object(workspace_store,'directory',return_value=root),patch.object(config_manager,'CONFIG_FILE',cfg):
                store=HistoryStore(root/'chat-history.sqlite3');store.append('chat','user','before','12:00')
                archive=root/'export.zip';app_recovery.backup(archive,store.db);store.close()
                rows=app_recovery.validate(archive)
                self.assertNotIn('gemini_api_key',json.loads(rows['preferences.json']))
                store=HistoryStore(root/'chat-history.sqlite3');store.append('chat','assistant','later','12:01');store.close()
                app_recovery.stage_restore(archive);self.assertTrue(app_recovery.apply_pending())
                store=HistoryStore(root/'chat-history.sqlite3')
                try:self.assertEqual(store.count('chat'),1)
                finally:store.close()
                self.assertEqual(config_manager.load_api_keys()['gemini_api_key'],'keep-secret')
                self.assertTrue(list(root.glob('before-restore-*.zip')))

    def test_restore_rejects_traversal_and_tampered_payload(self):
        from zipfile import ZipFile
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'bad.zip'
            with ZipFile(target,'w') as archive:
                archive.writestr('../escape.json','{}');archive.writestr('manifest.json','{}')
            with self.assertRaises(ValueError):app_recovery.validate(target)


class RequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=fixtures.QApplication.instance() or fixtures.QApplication([])

    def run_job(self,server,**kwargs):
        job=ChatRequest(Settings(server.url,'local',autostart=False),[{'role':'user','content':'question'}],**kwargs)
        result=[];job.finished.connect(lambda *args:result.append(args));job.start()
        deadline=time.monotonic()+4
        while not result and time.monotonic()<deadline:QTest.qWait(10)
        if not result:job.cancel()
        job.deleteLater();self.assertTrue(result);return result[0]

    def test_local_tool_round_executes_only_allowlisted_calculator(self):
        with fixtures.FakeOllama() as server:
            server.show={'capabilities':['completion','tools']}
            def respond(payload):
                if payload['messages'][-1]['role']=='tool':return [{'message':{'content':'7'},'done':True}]
                return [{'message':{'tool_calls':[{'function':{'name':'calculate','arguments':{'expression':'12-5'}}}]},'done':True}]
            server.chat_handler=respond
            result=self.run_job(server,tools=local_tools.TOOLS,tool_handler=lambda name,args:local_tools.execute(name,args,[]))
            self.assertEqual(result,('7','',False))
            requests=[body for path,body in server.requests if path=='/api/chat']
            self.assertEqual(json.loads(requests[-1]['messages'][-1]['content'])['result'],7)

    def test_unknown_tool_never_runs_and_vision_requires_capability(self):
        with fixtures.FakeOllama() as server:
            server.show={'capabilities':['completion','tools']}
            server.chunks=[{'message':{'tool_calls':[{'function':{'name':'shell','arguments':{}}}]},'done':True}]
            calls=[]
            result=self.run_job(server,tools=local_tools.TOOLS,tool_handler=lambda *args:calls.append(args))
            self.assertTrue(result[1]);self.assertEqual(calls,[])
        with fixtures.FakeOllama() as server:
            server.show={'capabilities':['completion']}
            self.assertTrue(self.run_job(server,images=['fake'])[1])
            self.assertFalse(any(path=='/api/chat' for path,_ in server.requests))

    def test_tool_round_accepts_a_final_chunk_without_a_newline(self):
        with fixtures.FakeOllama() as server:
            server.show = {'capabilities': ['completion', 'tools']}
            def respond(payload):
                if payload['messages'][-1]['role'] == 'tool':
                    return [{'message': {'content': '7'}, 'done': True}]
                return [json.dumps({'message': {'tool_calls': [
                    {'function': {'name': 'calculate', 'arguments': {'expression': '12-5'}}}
                ]}, 'done': True}).encode()]
            server.chat_handler = respond
            result = self.run_job(server, tools=local_tools.TOOLS,
                                  tool_handler=lambda name, args: local_tools.execute(name, args, []))
            self.assertEqual(result, ('7', '', False))
            self.assertEqual(sum(path == '/api/chat' for path, _ in server.requests), 2)

    def test_hidden_request_output_limit_does_not_expand_the_profile_budget(self):
        with fixtures.FakeOllama() as server:
            self.run_job(server, output_limit=128)
            payload = next(body for path, body in server.requests if path == '/api/chat')
            self.assertEqual(payload['options']['num_predict'], 128)
        with fixtures.FakeOllama() as server:
            self.run_job(server, output_limit=10000)
            payload = next(body for path, body in server.requests if path == '/api/chat')
            self.assertEqual(payload['options']['num_predict'], 512)

    def test_schema_and_image_payload_are_forwarded_to_capable_model(self):
        with fixtures.FakeOllama() as server:
            server.show={'capabilities':['completion','vision']}
            schema={'type':'object'}
            self.run_job(server,images=['encoded'],output_schema=schema)
            request=next(body for path,body in server.requests if path=='/api/chat')
            self.assertEqual(request['format'],schema);self.assertEqual(request['messages'][-1]['images'],['encoded'])

    def test_embedding_transport_cancels_before_delayed_headers(self):
        from core.local_http import embedding_request
        from PyQt6.QtCore import QTimer
        with fixtures.FakeOllama() as server:
            server.before_headers['/api/embed']=threading.Event()
            cancel=threading.Event();QTimer.singleShot(50,cancel.set);started=time.monotonic()
            with self.assertRaises(Cancelled):embedding_request(server.url,{'model':'local','input':['text']},cancel)
            self.assertLess(time.monotonic()-started,1)
            server.before_headers['/api/embed'].set()

    def test_embedding_transport_uses_loopback_and_rejects_redirects(self):
        from core.local_http import embedding_request
        with fixtures.FakeOllama() as server:
            server.post_overrides['/api/embed']=(302,{}, {'Location':'https://example.com'})
            with self.assertRaises(ValueError):embedding_request(server.url,{'model':'local','input':['text']},threading.Event())
        with self.assertRaises(ValueError):embedding_request('https://example.com',{},threading.Event())

    def test_embedding_transport_runs_inside_a_background_worker(self):
        from brave_local_jobs import Worker
        from core.local_http import embedding_request
        with fixtures.FakeOllama() as server:
            server.post_overrides['/api/embed']=(200,{'embeddings':[[1.,0.]]},{})
            worker=Worker(None,lambda cancel,progress:embedding_request(server.url,{'model':'local','input':['text']},cancel))
            results=[];worker.completed.connect(lambda *args:results.append(args));worker.start()
            deadline=time.monotonic()+3
            while not results and time.monotonic()<deadline:QTest.qWait(10)
            self.assertTrue(results);self.assertEqual(results[0][0]['embeddings'],[[1.,0.]])


class NewUITests(unittest.TestCase):
    setUpClass=classmethod(fixtures.LocalUITests.setUpClass.__func__)
    setUp=fixtures.LocalUITests.setUp
    tearDown=fixtures.LocalUITests.tearDown
    wait_for=fixtures.LocalUITests.wait_for
    start_local=fixtures.LocalUITests.start_local

    def test_new_dialogs_open_without_duplicate_theme_controls(self):
        from brave_local_lab import LocalLab
        from brave_document_lab import DocumentLab
        from brave_conversation_inspector import Inspector
        from PyQt6.QtWidgets import QComboBox
        self.win._features.store.append(self.win._features.chat_id,'user','question','12:00')
        import brave_ui
        for theme in ('dark','light','hacker'):
            brave_ui.set_theme(self.win,theme,persist=False)
            for language in ('uz','en','ru'):
                brave_ui.set_language(self.win,language,persist=False)
                for factory in (LocalLab,DocumentLab,Inspector):
                    dialog=factory(self.win);dialog.show();QTest.qWait(10)
                    self.assertFalse(dialog.grab().isNull())
                    self.assertFalse(any(box.objectName()=='BraveTheme' for box in dialog.findChildren(QComboBox)))
                    if os.environ.get('BRAVE_UI_PREVIEWS'):
                        dialog.grab().save(str(Path(os.environ['BRAVE_UI_PREVIEWS'])/f'brave-{factory.__name__}-{theme}-{language}.png'))
                    dialog.reject();dialog.deleteLater()

    def test_large_history_displays_a_page_and_can_reach_earliest_messages(self):
        features=self.win._features
        with features.store.db:
            features.store.db.execute("INSERT INTO chats VALUES ('large','Long chat','')")
            features.store.db.executemany('INSERT INTO messages(chat_id,role,body,stamp) VALUES (?,?,?,?)',
                [('large','user' if i%2==0 else 'assistant',f'message {i}','12:00') for i in range(10000)])
        self.assertTrue(features.switch_chat('large'));QTest.qWait(30)
        self.assertEqual(len(self.win._log._history),60)
        self.assertEqual(features.page_offset,9940)
        features.show_page(0);QTest.qWait(10)
        self.assertIn('message 0',self.win._log._history[0][0])
        self.assertLessEqual(len(self.win._log._rows),60)

    def test_benchmark_repeats_and_releases_inference_gate(self):
        from brave_local_lab import LocalLab
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama')
            dialog=LocalLab(self.win);dialog.models.setText('local');dialog.start()
            self.wait_for(lambda:len(dialog.samples)==6,timeout=6000)
            self.assertEqual(sum(path=='/api/generate' for path,_ in server.requests),3)
            dialog.reject();self.assertIsNone(gate.active);dialog.deleteLater()
