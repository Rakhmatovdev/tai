"""Behavioral checks for the six added AI workflows and their failure paths."""
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock,patch

import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_ollama as fixtures
from PyQt6.QtTest import QTest
from PyQt6.QtGui import QPixmap,QColor
from core import ai_extensions,workspace_store,code_changes,model_router
from core.ollama_chat import Settings
from memory import config_manager
from brave_ai_studio import AIStudio


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.location=patch.object(workspace_store,'directory',return_value=self.root);self.location.start()
        model_router._cache.clear()

    def tearDown(self):self.location.stop();self.temp.cleanup()

    def test_visual_context_is_bounded_isolated_and_forgettable(self):
        context=ai_extensions.VisualContext();context.put('one',['pixels'],['one.jpg'])
        self.assertEqual(context.get('other'),([],[]))
        data,_=context.get('one');data.clear();self.assertEqual(context.get('one')[0],['pixels'])
        for i in range(5):context.put(str(i),['pixels'],['name'])
        self.assertEqual(len(context.chats),4);self.assertEqual(context.get('one'),([],[]))
        context.clear();self.assertFalse(context.chats)

    def test_settings_are_strict_and_route_is_opt_in(self):
        self.assertFalse(ai_extensions.settings()['auto_route'])
        ai_extensions.save(auto_route=True,remember_images=False)
        self.assertEqual(ai_extensions.settings(),{'auto_route':True,'remember_images':False})
        with self.assertRaises(ValueError):ai_extensions.save(auto_route='true')
        ai_extensions.save(auto_route=False)
        with patch.object(model_router,'recommend') as recommend:
            self.assertEqual(model_router.route(Settings(),'code',False,threading.Event()),Settings())
            recommend.assert_not_called()

    def test_router_uses_task_capabilities_cache_and_preserves_settings(self):
        ai_extensions.save(auto_route=True)
        cfg=Settings(model='original',thinking='off');event=threading.Event()
        with patch.object(model_router,'recommend',return_value=[{'name':'coder','fits_estimate':True}]) as advice:
            first=model_router.route(cfg,'debug python code',False,event)
            second=model_router.route(cfg,'SQL bug',False,event)
            self.assertEqual(first,replace(cfg,model='coder'));self.assertEqual(second,first)
            self.assertEqual(advice.call_count,1);self.assertEqual(advice.call_args.args[1],'code')
        with patch.object(model_router,'recommend',return_value=[]):
            with self.assertRaises(ValueError):model_router.route(cfg,'image?',True,event)
        self.assertEqual(cfg.model,'original')

    def test_router_requires_tool_capability_when_chat_tools_enabled(self):
        ai_extensions.save(auto_route=True)
        rows=[{'name':'small','fits_estimate':True,'capabilities':['completion']},
              {'name':'tools','fits_estimate':True,'capabilities':['completion','tools']}]
        with patch.object(model_router,'recommend',return_value=rows):
            selected=model_router.route(Settings(),'hello',False,threading.Event(),tools=True)
        self.assertEqual(selected.model,'tools')

    def test_patch_preview_apply_backup_and_conflict_safe_restore(self):
        from core.file_backups import restore
        target=self.root/'sample.py';original=b'\xef\xbb\xbfanswer = 1\r\n';target.write_bytes(original)
        source=code_changes.snapshot(target)
        self.assertIn('+answer = 2',code_changes.preview(source,'answer = 2\n'))
        self.assertEqual(target.read_bytes(),original)
        identity=code_changes.apply(source,'answer = 2\n')
        self.assertEqual(target.read_bytes(),b'\xef\xbb\xbfanswer = 2\r\n')
        target.write_text('external = 3\n')
        with self.assertRaises(ValueError):restore(identity)
        target.write_bytes(b'\xef\xbb\xbfanswer = 2\r\n');restore(identity)
        self.assertEqual(target.read_bytes(),original)

    def test_stale_file_or_parent_link_cannot_be_overwritten(self):
        path=self.root/'sample.py';path.write_text('a = 1\n');source=code_changes.snapshot(path)
        path.write_text('external = 2\n')
        with self.assertRaises(ValueError):code_changes.apply(source,'a = 3\n')
        self.assertEqual(path.read_text(),'external = 2\n')
        path.write_text('password = "private"\n')
        with self.assertRaises(ValueError):code_changes.snapshot(path)

    def test_speaker_assignment_reuses_voice_and_marks_unknown_after_limit(self):
        from core.speaker_labels import SpeakerLabels
        labels=SpeakerLabels.__new__(SpeakerLabels)
        labels.threshold=.55;labels.maximum=2;labels.centers=[];labels.counts=[]
        self.assertEqual(labels.assign(np.array([1.,0.,0.])),'1')
        self.assertEqual(labels.assign(np.array([0.,1.,0.])),'2')
        self.assertEqual(labels.assign(np.array([1.,0.,0.])),'1')
        self.assertEqual(labels.assign(np.array([0.,0.,1.])),'?')
        self.assertEqual(labels.assign(None),'?')

    def test_live_meeting_streams_chunks_and_drains_after_stop(self):
        from core.live_meeting import run
        (self.root/'model.bin').touch();stop=threading.Event();event=threading.Event();progress=[]
        class Stream:
            def __init__(self,**kwargs):self.callback=kwargs['callback']
            def __enter__(self):
                for _ in range(19):self.callback(np.ones((8000,1),dtype='float32')*.1,8000,None,None)
                stop.set();return self
            def __exit__(self,*args):pass
        with patch('core.audio_devices.resolve',return_value=None),patch('core.live_meeting.transcribe_chunk',return_value=['[00:00:00] hello']) as transcribe:
            result=run(str(self.root),'en',stop,event,lambda:True,progress.append,stream_factory=Stream)
        self.assertEqual(transcribe.call_count,2)
        self.assertEqual([len(call.args[0]) for call in transcribe.call_args_list],[128000,24000])
        self.assertEqual(result,'[00:00:00] hello\n[00:00:00] hello')
        self.assertEqual(len(progress),2)

    def test_live_meeting_permission_loss_closes_microphone(self):
        from core.live_meeting import run
        (self.root/'model.bin').touch();allowed=[True];closed=[]
        class Stream:
            def __init__(self,**kwargs):pass
            def __enter__(self):allowed[0]=False;return self
            def __exit__(self,*args):closed.append(True)
        with patch('core.audio_devices.resolve',return_value=None):
            with self.assertRaises(ValueError):run(str(self.root),'en',threading.Event(),threading.Event(),lambda:allowed[0],stream_factory=Stream)
        self.assertTrue(closed)


class UITests(unittest.TestCase):
    setUpClass=classmethod(fixtures.LocalUITests.setUpClass.__func__)
    setUp=fixtures.LocalUITests.setUp
    wait_for=fixtures.LocalUITests.wait_for
    start_local=fixtures.LocalUITests.start_local

    def tearDown(self):
        if getattr(self,'studio',None):self.studio.reject();QTest.qWait(10)
        fixtures.LocalUITests.tearDown(self)

    def open(self):self.studio=AIStudio(self.win);self.studio.show();return self.studio

    def test_followup_reuses_only_successful_chat_image_and_forget_stops_reuse(self):
        from PIL import Image
        with fixtures.FakeOllama() as server:
            server.show={'capabilities':['completion','vision']}
            Settings(server.url,'local',autostart=False).save('ollama')
            image=Path(self.temp.name)/'red.png';Image.new('RGB',(32,32),'red').save(image)
            runtime=self.start_local();runtime.submit('Describe.',[str(image)],'vision')
            self.wait_for(lambda:not runtime.busy and len(runtime.history)==2)
            runtime.submit('What color?',[]);self.wait_for(lambda:not runtime.busy and len(runtime.history)==4)
            requests=[body for path,body in server.requests if path=='/api/chat']
            self.assertEqual(requests[0]['messages'][-1]['images'],requests[1]['messages'][-1]['images'])
            self.assertNotIn('images',runtime.history[0])
            self.open().pages['models'].forget_images()
            runtime.submit('Continue.',[]);self.wait_for(lambda:not runtime.busy and len(runtime.history)==6)
            last=[body for path,body in server.requests if path=='/api/chat'][-1]
            self.assertNotIn('images',last['messages'][-1])

    def test_auto_route_changes_request_but_never_saved_default(self):
        ai_extensions.save(auto_route=True)
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama')
            runtime=self.start_local()
            with patch('core.model_router.recommend',return_value=[{'name':'local','fits_estimate':True}]) as recommend:
                runtime.submit('debug this python code',[])
                self.wait_for(lambda:not runtime.busy and len(runtime.history)==2)
            self.assertEqual(recommend.call_args.args[1],'code')
            self.assertEqual(config_manager.load_api_keys()['ollama_model'],'local')

    def test_forget_while_image_request_is_running_prevents_late_retention(self):
        from PIL import Image
        with fixtures.FakeOllama() as server:
            server.show={'capabilities':['completion','vision']}
            Settings(server.url,'local',autostart=False).save('ollama')
            image=Path(self.temp.name)/'red.png';Image.new('RGB',(20,20),'red').save(image)
            server.pause=threading.Event();runtime=self.start_local()
            runtime.submit('Describe',[str(image)],'vision')
            self.wait_for(lambda:any(path=='/api/chat' for path,_ in server.requests))
            self.open().pages['models'].forget_images();server.pause.set()
            self.wait_for(lambda:not runtime.busy)
            self.assertEqual(runtime.visual_context.get(self.win._features.chat_id),([],[]))

    def test_truncated_ai_fix_never_opens_apply_dialog(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama')
            server.chunks=[{'message':{'content':'a = 2'},'done':True,'done_reason':'length'}]
            path=Path(self.temp.name)/'sample.py';path.write_text('a = 1\n')
            page=self.open().pages['review'];page.path.setText(str(path));page.propose_fix()
            self.wait_for(lambda:not page.busy)
            self.assertFalse(hasattr(page,'editor'));self.assertEqual(path.read_text(),'a = 1\n')

    def test_code_edit_preview_does_not_write_until_apply_and_undo_works(self):
        path=Path(self.temp.name)/'sample.py';path.write_text('a = 1\n')
        page=self.open().pages['review'];page.path.setText(str(path));page.edit_file()
        editor=page.editor;editor.editor.setPlainText('a = 2\n')
        self.assertEqual(path.read_text(),'a = 1\n');self.assertIn('+a = 2',editor.diff.toPlainText())
        editor.apply();self.assertEqual(path.read_text(),'a = 2\n')
        page.undo_edit();self.assertEqual(path.read_text(),'a = 1\n')

    def test_editor_refuses_apply_after_permission_revoked(self):
        path=Path(self.temp.name)/'sample.py';path.write_text('a = 1\n')
        page=self.open().pages['review'];page.path.setText(str(path));page.edit_file()
        page.editor.editor.setPlainText('a = 2\n');self.win._capabilities.policy['permissions']['code']=False
        page.editor.apply();self.assertEqual(path.read_text(),'a = 1\n')

    def test_ai_fix_opens_complete_diff_without_writing(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama')
            server.chunks=[{'message':{'content':'```python\na = 2\n```'},'done':True}]
            path=Path(self.temp.name)/'sample.py';path.write_text('a = 1\n')
            page=self.open().pages['review'];page.path.setText(str(path));page.propose_fix()
            self.wait_for(lambda:hasattr(page,'editor'))
            self.assertEqual(path.read_text(),'a = 1\n');self.assertIn('+a = 2',page.editor.diff.toPlainText())

    def test_screen_requires_permission_and_separate_preview_then_analyze(self):
        with fixtures.FakeOllama() as server:
            server.show={'capabilities':['completion','vision']}
            Settings(server.url,'local',autostart=False).save('ollama')
            page=self.open().pages['screen']
            self.win._capabilities.policy['permissions']['screen']=False
            page.capture();self.assertIsNone(page.encoded)
            self.win._capabilities.policy['permissions']['screen']=True
            pixmap=QPixmap(120,90);pixmap.fill(QColor('red'))
            screen=Mock();screen.grabWindow.return_value=pixmap
            with patch('brave_screen_page.QApplication.screens',return_value=[screen]):
                page.capture();self.wait_for(lambda:bool(page.encoded),timeout=2500)
            self.assertFalse(any(path=='/api/chat' for path,_ in server.requests))
            with patch('core.model_router.recommend',return_value=[{'name':'local','fits_estimate':True}]):
                page.inspect();self.wait_for(lambda:bool(page.answer))
            payload=[body for path,body in server.requests if path=='/api/chat'][-1]
            self.assertTrue(payload['messages'][-1]['images']);page.clear();self.assertIsNone(page.encoded)

    def test_live_meeting_controls_keep_recording_until_worker_returns(self):
        page=self.open().pages['meeting'];entered=threading.Event()
        def run(_model,_language,stop,cancelled,allowed,progress,**kwargs):
            entered.set();progress('[00:00:00] Speaker 1: Hello')
            stop.wait(3);return '[00:00:00] Speaker 1: Hello'
        with patch('core.live_meeting.run',side_effect=run):
            page.start_live();self.wait_for(entered.is_set)
            self.assertTrue(self.win._meeting_recording);self.assertTrue(page.stop_live_button.isEnabled())
            self.wait_for(lambda:'Hello' in page.transcript.toPlainText())
            page.stop_live();self.wait_for(lambda:not page.busy)
            self.assertFalse(self.win._meeting_recording)
            self.assertIn('Speaker 1:',page.transcript.toPlainText())

    def test_live_action_items_can_update_during_recording_without_stopping_it(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama')
            page=self.open().pages['meeting'];entered=threading.Event()
            def run(_model,_language,stop,cancelled,allowed,progress,**kwargs):
                progress('Ali will send the report Monday.');entered.set();stop.wait(4)
                return 'Ali will send the report Monday.'
            with patch('core.live_meeting.run',side_effect=run):
                page.start_live();self.wait_for(entered.is_set)
                self.wait_for(lambda:bool(page.transcript.toPlainText()))
                page.update_live_notes();self.wait_for(lambda:bool(page.live_notes.toPlainText()))
                self.assertTrue(page.busy);self.assertTrue(self.win._meeting_recording)
                page.stop_live();self.wait_for(lambda:not page.busy)


if __name__=='__main__':unittest.main()
