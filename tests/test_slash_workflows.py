"""Slash modes, durable meetings, screen editing, measured routing and test execution."""
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch,Mock
import numpy as np
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_ollama as fixtures
from PyQt6.QtCore import Qt,QRect
from PyQt6.QtGui import QPixmap,QColor
from PyQt6.QtTest import QTest
from core import workspace_store,meeting_sessions,code_changes,model_performance,model_router,ai_extensions
from core.slash_commands import parse,matches,COMMANDS
from core.ollama_chat import Settings
from core.test_execution import run
from memory import config_manager


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.location=patch.object(workspace_store,'directory',return_value=self.root);self.location.start();model_router._cache.clear()
    def tearDown(self):self.location.stop();self.temp.cleanup()

    def test_slash_grammar_languages_aliases_and_literal_input(self):
        command,body,instruction=parse('/translate en Salom 42')
        self.assertEqual((command.name,body),('translate','Salom 42'));self.assertIn('English',instruction)
        self.assertEqual(parse('/plan\nBuild a site')[1],'Build a site')
        self.assertEqual(parse('/quick answer')[0].name,'fast')
        self.assertEqual(parse('normal text'),(None,'normal text',''))
        with self.assertRaises(ValueError):parse('/unknown x')
        self.assertEqual([row.name for row in matches('/fa')],['fast'])
        self.assertEqual(matches('/fast prompt'),[])
        self.assertEqual(len({row.name for row in COMMANDS}),len(COMMANDS))

    def test_sessions_are_atomic_bounded_and_restore_recording_as_data(self):
        identity=meeting_sessions.save(None,'Ali Monday',notes='task',recording=True)
        meeting_sessions.save(identity,'Ali Tuesday',notes='updated')
        self.assertEqual(len(meeting_sessions.sessions()),1)
        self.assertEqual(meeting_sessions.sessions()[0]['notes'],'updated')
        for i in range(12):meeting_sessions.save(None,str(i))
        self.assertEqual(len(meeting_sessions.sessions()),10)
        selected=meeting_sessions.sessions()[-1]['id'];meeting_sessions.delete(selected)
        self.assertNotIn(selected,[row['id'] for row in meeting_sessions.sessions()])

    def test_number_review_ignores_time_and_speaker_ids_without_rewriting_values(self):
        from core.meeting_review import numbers
        self.assertEqual(numbers('[00:00:16] Speaker 2: Budget $42, later $4.2 and 15%.'),['$42','$4.2','15%'])
        from core.meeting_review import correct
        text,count=correct('[00:00:01] Speaker 1: Budget 1.','1','42')
        self.assertEqual(text,'[00:00:01] Speaker 1: Budget 42.');self.assertEqual(count,1)
        text,count=correct(text,'Speaker 1','Ali')
        self.assertIn('Ali:',text)

    def test_measured_routing_needs_repeated_matching_task_and_profile(self):
        settings=Settings();metrics={'status':'completed','first_reply_s':.2,'tokens_per_second':100,'residency':'loaded'}
        model_performance.record(settings,'code',metrics)
        self.assertEqual(model_performance.estimates(settings,'code'),{})
        model_performance.record(settings,'code',metrics)
        self.assertIn(settings.model,model_performance.estimates(settings,'code'))
        self.assertEqual(model_performance.estimates(settings,'vision'),{})
        self.assertEqual(model_performance.estimates(replace(settings,profile='quality'),'code'),{})
        model_performance.record(settings,'code',dict(metrics,status='error',first_reply_s=.01))
        self.assertEqual(model_performance.estimates(settings,'code')[settings.model]['samples'],2)

    def test_measured_selection_prefers_known_fast_fit_and_preserves_code_preference(self):
        cfg=Settings();rows=[{'name':'small','fits_estimate':True,'code_name':False},
                            {'name':'coder','fits_estimate':True,'code_name':True}]
        for _ in range(2):
            model_performance.record(replace(cfg,model='coder'),'text',{'first_reply_s':.1,'tokens_per_second':100})
        self.assertEqual(model_performance.measured_order(rows,cfg,'text')[0]['name'],'coder')
        self.assertEqual(model_performance.measured_order(rows,cfg,'code'),rows)

    def test_exact_multi_file_changes_and_conflict_preflight(self):
        a=self.root/'a.py';b=self.root/'b.py';a.write_text('a = 1\n');b.write_text('b = 2\n')
        sources=[code_changes.snapshot(path) for path in (a,b)]
        payload=json.dumps({'edits':[{'file':'a.py','search':'a = 1','replace':'a = 3'},
                                      {'file':'b.py','search':'b = 2','replace':'b = 4'}]})
        changes=code_changes.search_replace(sources,payload);b.write_text('external = 5\n')
        with self.assertRaises(ValueError):code_changes.apply_many(changes)
        self.assertEqual(a.read_text(),'a = 1\n');b.write_text('b = 2\n')
        identities=code_changes.apply_many(changes)
        self.assertEqual(len(identities),2);self.assertEqual(a.read_text(),'a = 3\n')
        from core.file_backups import restore
        for identity in reversed(identities):restore(identity)
        self.assertEqual(b.read_text(),'b = 2\n')

    def test_bad_replacement_cannot_introduce_paths_or_ambiguous_matches(self):
        path=self.root/'a.py';path.write_text('a = 1\na = 1\n');source=code_changes.snapshot(path)
        for file,search in (('../a.py','a = 1'),('a.py','a = 1'),('a.py','not there')):
            with self.assertRaises(ValueError):code_changes.search_replace([source],json.dumps({'edits':[{'file':file,'search':search,'replace':'x'}]}))

    def test_multifile_failure_rolls_back_prior_write(self):
        paths=[self.root/'a.py',self.root/'b.py']
        for path in paths:path.write_text('a = 1\n')
        changes=[(code_changes.snapshot(path),'a = 2\n') for path in paths]
        real=code_changes.apply
        def apply(source,text):
            if source.path==str(paths[1]):raise OSError('disk failure')
            return real(source,text)
        with patch.object(code_changes,'apply',side_effect=apply):
            with self.assertRaises(OSError):code_changes.apply_many(changes)
        self.assertEqual(paths[0].read_text(),'a = 1\n')

    def test_python_patch_keeps_existing_indentation_and_rejects_invalid_code(self):
        path=self.root/'a.py';path.write_text('def divide(a, b):\n    return a / b\n');source=code_changes.snapshot(path)
        payload=json.dumps({'edits':[{'file':'a.py','search':'return a / b',
            'replace':'if b == 0:\n    raise ValueError("zero")\nreturn a / b'}]})
        changes=code_changes.search_replace([source],payload)
        self.assertIn('        raise ValueError',changes[0][1]);code_changes.validate(*changes[0])
        with self.assertRaises(ValueError):code_changes.apply(source,'def broken(:\n')
        self.assertEqual(path.read_text(),source.text)

    def test_backup_registry_failure_restores_the_original_source(self):
        path=self.root/'a.py';path.write_text('a = 1\n');source=code_changes.snapshot(path)
        with patch('core.file_backups.commit',side_effect=OSError('registry full')):
            with self.assertRaises(OSError):code_changes.apply(source,'a = 2\n')
        self.assertEqual(path.read_bytes(),source.before)

    def test_test_runner_runs_real_tests_and_hides_environment_keys(self):
        (self.root/'test_demo.py').write_text('import unittest,os\nclass T(unittest.TestCase):\n def test_env(self): self.assertNotIn("BRAVE_PRIVATE_KEY",os.environ)\n')
        with patch.dict(os.environ,{'BRAVE_PRIVATE_KEY':'do-not-pass'}):
            result=run(self.root,'unittest',['discover','-s','.'],threading.Event(),timeout=5)
        self.assertTrue(result['passed']);self.assertIn('Ran 1 test',result['output'])

    def test_test_runner_timeout_stops_execution(self):
        (self.root/'test_slow.py').write_text('import unittest,time\nclass T(unittest.TestCase):\n def test_wait(self): time.sleep(20)\n')
        started=time.monotonic();result=run(self.root,'unittest',['discover','-s','.'],threading.Event(),timeout=1)
        self.assertEqual(result['reason'],'timeout');self.assertFalse(result['passed']);self.assertLess(time.monotonic()-started,5)

    def test_test_runner_permission_loss_stops_running_test(self):
        (self.root/'test_slow.py').write_text('import unittest,time\nclass T(unittest.TestCase):\n def test_wait(self): time.sleep(20)\n')
        state=[True];timer=threading.Timer(.5,lambda:state.__setitem__(0,False));timer.start()
        result=run(self.root,'unittest',['discover','-s','.'],threading.Event(),timeout=5,allowed=lambda:state[0]);timer.join()
        self.assertEqual(result['reason'],'permission');self.assertFalse(result['passed'])

    def test_totext_reassembles_overlapping_chunks_once(self):
        from core.text_import import convert
        text='A'*1000+'B'*1000+'C'*350;path=self.root/'sample.txt';path.write_text(text)
        result=convert([path],'','auto',threading.Event())
        self.assertEqual(result,'sample.txt\n'+text)

    def test_accurate_stt_waits_for_pause_and_retains_final_tail(self):
        from core.live_meeting import run
        (self.root/'model.bin').touch();stop=threading.Event()
        class Stream:
            def __init__(self,**kwargs):self.callback=kwargs['callback']
            def __enter__(self):
                for i in range(19):
                    data=np.ones((8000,1),dtype='float32')*(0 if i in (8,18) else .1)
                    self.callback(data,8000,None,None)
                stop.set();return self
            def __exit__(self,*args):pass
        with patch('core.audio_devices.resolve',return_value=None),patch('core.live_meeting.transcribe_chunk',return_value=['hello']) as transcribe:
            run(str(self.root),'en',stop,threading.Event(),lambda:True,quality='accurate',stream_factory=Stream)
        self.assertEqual([len(call.args[0]) for call in transcribe.call_args_list],[72000,80000])
        self.assertTrue(all(call.kwargs['quality']=='accurate' for call in transcribe.call_args_list))


class UITests(unittest.TestCase):
    setUpClass=classmethod(fixtures.LocalUITests.setUpClass.__func__)
    setUp=fixtures.LocalUITests.setUp
    wait_for=fixtures.LocalUITests.wait_for
    start_local=fixtures.LocalUITests.start_local
    def tearDown(self):
        for name in ('_ai_studio','_text_import','_test_runner','_slash_help'):
            dialog=getattr(self.win,name,None)
            if dialog:
                try:dialog.reject()
                except RuntimeError:pass
        QTest.qWait(10);fixtures.LocalUITests.tearDown(self)

    def test_slash_dropdown_filters_and_keyboard_selection_keeps_focus(self):
        self.win._input.setFocus();QTest.keyClicks(self.win._input,'/fa');QTest.qWait(40)
        menu=self.win._slash_menu;self.assertTrue(menu.popup.isVisible());self.assertEqual(menu.list.count(),1)
        QTest.keyClick(self.win._input,Qt.Key.Key_Tab)
        self.assertEqual(self.win._input.text(),'/fast ');self.assertFalse(menu.popup.isVisible())
        self.assertTrue(self.win._input.hasFocus())

    def test_slash_dropdown_mouse_selects_command_without_sending(self):
        self.win._input.setFocus();self.win._input.setText('/tr');QTest.qWait(40)
        menu=self.win._slash_menu
        QTest.mouseClick(menu.list.viewport(),Qt.MouseButton.LeftButton,pos=menu.list.visualItemRect(menu.list.item(0)).center())
        self.assertEqual(self.win._input.text(),'/translate ')
        self.assertFalse(menu.popup.isVisible())

    def test_slash_escape_closes_menu_without_interrupting_a_task(self):
        stop=Mock();self.win.on_interrupt=stop
        self.win._input.setFocus();self.win._input.setText('/');QTest.qWait(30)
        QTest.keyClick(self.win._input,Qt.Key.Key_Escape)
        self.assertFalse(self.win._slash_menu.popup.isVisible());stop.assert_not_called()

    def test_slash_action_dispatches_each_declared_action(self):
        from brave_slash import prepare_send
        targets={'totext':'brave_text_import.open_import','test':'brave_test_runner.open_runner',
                 'voice':'brave_local_voice.open_voice','benchmark':'brave_local_lab.open_lab'}
        for name,target in targets.items():
            self.win._input.setText('/'+name)
            with patch(target) as handler:prepare_send(self.win,'/'+name);handler.assert_called_once()
        for name in ('screen','meeting','review','models'):
            self.win._input.setText('/'+name)
            with patch('brave_ai_studio.open_studio') as handler:
                prepare_send(self.win,'/'+name);handler.assert_called_once_with(self.win,name)
        with patch.object(self.win,'_do_interrupt') as stop:prepare_send(self.win,'/cancel');stop.assert_called_once()
        runtime=self.start_local();runtime.visual_context.put(self.win._features.chat_id,['image'],['label'])
        prepare_send(self.win,'/forget');self.assertFalse(runtime.visual_context.get(self.win._features.chat_id)[0])
        prepare_send(self.win,'/help');self.assertTrue(self.win._slash_help.isVisible())

    def test_slash_and_new_dialogs_render_in_all_themes_and_languages(self):
        import brave_ui
        from brave_ai_studio import open_studio
        from brave_test_runner import open_runner
        from brave_text_import import open_import
        from brave_image_editor import ImageEditDialog
        for theme in ('dark','light','hacker'):
            for language in ('uz','en','ru'):
                brave_ui.set_theme(self.win,theme,persist=False);brave_ui.set_language(self.win,language,persist=False)
                self.win._input.setFocus();self.win._input.setText('/');QTest.qWait(30)
                objects={'menu':self.win._slash_menu.popup}
                studio=open_studio(self.win,'meeting');objects['meeting']=studio
                runner=open_runner(self.win);objects['test']=runner
                importer=open_import(self.win);objects['totext']=importer
                pixmap=QPixmap(200,100);pixmap.fill(QColor('white'))
                editor=ImageEditDialog(self.win,pixmap,lambda image:None);editor.show();objects['crop']=editor
                target=os.environ.get('BRAVE_SLASH_PREVIEWS')
                for key,widget in objects.items():
                    QTest.qWait(15)
                    self.assertLessEqual(widget.height(),self.win.screen().availableGeometry().height())
                    if target:
                        folder=Path(target);folder.mkdir(parents=True,exist_ok=True);widget.grab().save(str(folder/f'{key}-{theme}-{language}.png'))
                for widget in (editor,importer,runner,studio):widget.reject()
                QTest.qWait(10)

    def test_plan_is_a_real_prompt_without_tools_and_saved_mode_changes(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama');config_manager._patch_config(local_tools_enabled=True)
            runtime=self.start_local();runtime.submit('/plan Build a small app',[])
            self.wait_for(lambda:not runtime.busy and len(runtime.history)==2)
            payload=[body for path,body in server.requests if path=='/api/chat'][-1]
            self.assertIn('numbered plan',payload['messages'][0]['content']);self.assertEqual(payload['messages'][-1]['content'],'Build a small app')
            self.assertNotIn('tools',payload);self.assertEqual(Settings.read().profile,'balanced')

    def test_fast_uses_small_context_retention_and_no_saved_changes(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama');runtime=self.start_local()
            with patch('core.model_router.recommend',return_value=[{'name':'local','fits_estimate':True,'capabilities':['completion']}]):
                runtime.submit('/fast Say hi',[]);self.wait_for(lambda:not runtime.busy and len(runtime.history)==2)
            payload=[body for path,body in server.requests if path=='/api/chat'][-1]
            self.assertEqual(payload['options']['num_ctx'],2048);self.assertEqual(payload['keep_alive'],'5m')
            self.assertEqual(Settings.read().profile,'balanced')

    def test_think_selects_thinking_model_and_enables_supported_control(self):
        with fixtures.FakeOllama() as server:
            server.show={'capabilities':['completion','thinking'],'thinking':{'values':[False,True]}}
            Settings(server.url,'local',autostart=False).save('ollama');runtime=self.start_local()
            row={'name':'local','fits_estimate':True,'capabilities':['completion','thinking'],'thinking_values':[False,True]}
            with patch('core.model_router.recommend',return_value=[row]):
                runtime.submit('/think Check 17 times 23',[]);self.wait_for(lambda:not runtime.busy and len(runtime.history)==2)
            payload=[body for path,body in server.requests if path=='/api/chat'][-1]
            self.assertIs(payload['think'],True);self.assertEqual(payload['options']['num_ctx'],8192)
            self.assertEqual(payload['options']['num_predict'],4096)
            self.assertEqual(Settings.read().thinking,'off')

    def test_translate_targets_language_and_unknown_command_preserves_draft(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama');runtime=self.start_local()
            self.win._input.setText('/translate en Salom');self.win._send()
            self.wait_for(lambda:not runtime.busy and len(runtime.history)==2)
            payload=[body for path,body in server.requests if path=='/api/chat'][-1]
            self.assertIn('Target language: English',payload['messages'][0]['content'])
            self.win._input.setText('/bad command');self.win._send();self.assertEqual(self.win._input.text(),'/bad command')

    def test_chat_does_not_compete_with_live_meeting_and_preserves_draft(self):
        self.win._meeting_recording=True;self.win._input.setText('/fast question')
        with patch.object(self.win,'on_text_command') as send:self.win._send();send.assert_not_called()
        self.assertEqual(self.win._input.text(),'/fast question');self.win._meeting_recording=False

    def test_totext_action_opens_conversion_and_inserts_without_sending(self):
        path=Path(self.temp.name)/'sample.txt';path.write_text('Budget 42. Ali Monday.')
        self.win._drop_zone._set_file(str(path));self.win._input.setText('/totext');self.win._send()
        dialog=self.win._text_import;dialog.start();self.wait_for(lambda:bool(dialog.answer))
        self.assertIn('Budget 42',dialog.answer);self.win._input.setText('draft');dialog.insert()
        self.assertIn('draft\n\nsample.txt',self.win._input.text())

    def test_meeting_autosave_restore_notes_and_manual_corrections(self):
        from brave_ai_studio import open_studio
        studio=open_studio(self.win,'meeting');page=studio.pages['meeting']
        page.transcript.setPlainText('[00:00:00] Speaker 1: Budget 1.2.');page.live_notes.setPlainText('Ali Monday')
        self.wait_for(lambda:bool(meeting_sessions.sessions()))
        identity=page.session_id;studio.reject();QTest.qWait(20)
        studio=open_studio(self.win,'meeting');page=studio.pages['meeting']
        self.assertEqual(page.session_id,identity);self.assertIn('1.2',page.transcript.toPlainText())
        self.assertEqual(page.live_notes.toPlainText(),'Ali Monday');self.assertFalse(getattr(self.win,'_meeting_recording',False))
        page.old_term.setText('1.2');page.new_term.setText('42');page.correct_transcript()
        self.assertIn('Budget 42',page.transcript.toPlainText())

    def test_redaction_and_crop_change_only_selected_pixels(self):
        from brave_image_editor import ImageCanvas
        pixmap=QPixmap(200,100);pixmap.fill(QColor('white'));canvas=ImageCanvas(pixmap);canvas.resize(400,200)
        canvas.mode='redact';canvas.selection=QRect(100,50,100,50);self.assertTrue(canvas.apply_selection())
        image=canvas.image.toImage();self.assertEqual(image.pixelColor(60,30),QColor('black'))
        self.assertEqual(image.pixelColor(5,5),QColor('white'));canvas.undo();canvas.mode='crop'
        canvas.selection=QRect(100,50,100,50);canvas.apply_selection();self.assertEqual(canvas.image.width(),50)

    def test_screen_warmup_loads_without_chat_inference_or_saved_model_change(self):
        from brave_ai_studio import open_studio
        with fixtures.FakeOllama() as server:
            server.show={'capabilities':['completion','vision']};Settings(server.url,'local',autostart=False).save('ollama')
            page=open_studio(self.win,'screen').pages['screen']
            with patch('core.model_router.recommend',return_value=[{'name':'local','fits_estimate':True}]):
                page.warmup();self.wait_for(lambda:not page.busy)
            self.assertIn('/api/generate',[path for path,_ in server.requests]);self.assertNotIn('/api/chat',[path for path,_ in server.requests])
            self.assertEqual(Settings.read().model,'local')

    def test_test_runner_requires_approval_then_reports_real_result(self):
        from brave_test_runner import open_runner
        path=Path(self.temp.name);(path/'test_demo.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_a(self): self.assertTrue(True)\n')
        runner=open_runner(self.win,path);runner.args.setText('discover -s .')
        runner.start();self.assertIsNone(runner.worker)
        runner.approved.setChecked(True);runner.start();self.wait_for(lambda:hasattr(runner,'last_result'))
        self.assertTrue(runner.last_result['passed']);self.assertFalse(runner.approved.isChecked())


if __name__=='__main__':unittest.main()
