"""Five local AI features: policy, protocol, audio streaming and native UI."""
import base64
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch
import wave

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_ollama as fixtures
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QMessageBox,QTableWidgetItem

from core import workspace_store,speech_dictionary,offline_desktop,meeting_audio,code_review
from core.model_recommender import rank
from core.ollama_resources import Resources,GIB
from core.ollama_chat import Settings
from brave_ai_pipeline import AnalysisJob,split_sections
from brave_ai_studio import AIStudio
from memory import config_manager


def wav_file(path, seconds=65):
    with wave.open(str(path),'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(16000)
        stream.writeframes(b'\0\0'*(seconds*16000))


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.location=patch.object(workspace_store,'directory',return_value=self.root);self.location.start()
        self.policy={'mode':'smart','permissions':{'files':True,'system':True}}

    def tearDown(self):self.location.stop();self.temp.cleanup()

    def test_model_recommendations_filter_capabilities_and_prioritize_task(self):
        catalog=[{'name':name,'size':size,'parameters':'','quantization':''} for name,size in
                 [('small',2*GIB),('coder',4*GIB),('vision',5*GIB),('embedding',GIB),('unknown',GIB)]]
        info={name:{'capabilities':caps} for name,caps in [('small',['completion']),('coder',['completion']),
             ('vision',['completion','vision']),('embedding',['embedding']),('unknown',None)]}
        resources=Resources(16*GIB,32*GIB,4*GIB,8*GIB)
        self.assertEqual(rank(catalog,info,'text',resources)[0]['name'],'small')
        self.assertEqual(rank(catalog,info,'code',resources)[0]['name'],'coder')
        self.assertEqual([row['name'] for row in rank(catalog,info,'vision',resources)],['vision'])
        self.assertFalse(any(row['name']=='embedding' for row in rank(catalog,info,'text',resources)))

    def test_dictionary_is_bounded_single_pass_and_word_scoped(self):
        rows=[{'term':'Shahzod','recognized':'shaxzod','pronunciation':'Shah zod'},
              {'term':'O‘zbekiston','recognized':"uzbekiston",'pronunciation':'O‘z be kis ton'}]
        speech_dictionary.save(rows)
        self.assertEqual(speech_dictionary.correct('SHAXZOD uzbekiston shaxzodlar.'),'Shahzod O‘zbekiston shaxzodlar.')
        self.assertIn('Shah zod',speech_dictionary.pronounce('Shahzod keldi.'))
        self.assertEqual(speech_dictionary.pronounce('Shahzodlar'),'Shahzodlar')
        self.assertIn('Shahzod',speech_dictionary.hints())
        with self.assertRaises(ValueError):speech_dictionary.save(rows+rows)
        workspace_store.write('speech-dictionary.json',{'bad':True})
        self.assertEqual(speech_dictionary.load(),[])

    def test_dictionary_apostrophes_and_no_cascading_replacements(self):
        rows=[{'term':'A','recognized':'B','pronunciation':''},{'term':'C','recognized':'A','pronunciation':''},
              {'term':'o‘g‘il','recognized':"o'g'il",'pronunciation':''}]
        self.assertEqual(speech_dictionary.correct("B O’G’IL",rows),'A o‘g‘il')

    def test_stt_uses_local_dictionary_hints_and_corrects_result(self):
        import faster_whisper
        from core import offline_voice
        speech_dictionary.save([{'term':'Shahzod','recognized':'shaxzod','pronunciation':''}])
        model=Mock();model.transcribe.return_value=(iter([Mock(text='shaxzod keldi')]),None)
        (self.root/'model.bin').touch()
        offline_voice._models.clear()
        with patch.object(faster_whisper,'WhisperModel',return_value=model):
            text=offline_voice.transcribe([0.0],str(self.root),'uz',threading.Event())
        self.assertEqual(text,'Shahzod keldi')
        self.assertIn('Shahzod',model.transcribe.call_args.kwargs['initial_prompt'])
        offline_voice._models.clear()

    def test_tts_applies_pronunciation_without_changing_source(self):
        from core import offline_voice,uzbek_tts
        speech_dictionary.save([{'term':'Brave','recognized':'breyv','pronunciation':'Breyv'}])
        original='Brave tayyor.'
        with patch.object(uzbek_tts,'speak') as speak:
            offline_voice.speak(original,threading.Event(),uzbek_tts.VOICE_ID)
        self.assertEqual(speak.call_args.args[0],'Breyv tayyor.')
        self.assertEqual(original,'Brave tayyor.')

    def test_desktop_launch_requires_opt_in_permission_and_approval(self):
        event=threading.Event()
        with patch('core.offline_desktop.subprocess.Popen') as launch:
            with self.assertRaises(ValueError):offline_desktop.execute('open_local_app',{'app':'notepad'},self.policy,event,True)
            offline_desktop.save(True,self.root)
            with self.assertRaises(ValueError):offline_desktop.execute('open_local_app',{'app':'notepad'},self.policy,event)
            with self.assertRaises(ValueError):offline_desktop.execute('open_local_app',{'app':'cmd /c anything'},self.policy,event,True)
            self.policy['permissions']['system']=False
            with self.assertRaises(ValueError):offline_desktop.execute('open_local_app',{'app':'notepad'},self.policy,event,True)
            launch.assert_not_called()
            self.policy['permissions']['system']=True
            with patch('core.offline_desktop.executable',return_value=['C:/Windows/System32/notepad.exe']):
                result=offline_desktop.execute('open_local_app',{'app':'notepad'},self.policy,event,True)
            self.assertEqual(result['status'],'launch_requested')
            self.assertEqual(launch.call_args.args[0],['C:/Windows/System32/notepad.exe'])
            self.assertFalse(launch.call_args.kwargs['shell'])

    def test_filename_search_is_scoped_bounded_and_cancellable(self):
        folder=self.root/'allowed';folder.mkdir();(folder/'report.txt').write_text('not read')
        (self.root/'outside-report.txt').write_text('outside')
        value=offline_desktop.search(folder,'report',threading.Event())
        self.assertEqual(value['files'],['report.txt'])
        for i in range(25):(folder/f'report-{i}.txt').touch()
        value=offline_desktop.search(folder,'report',threading.Event())
        self.assertEqual(len(value['files']),20);self.assertTrue(value['truncated'])
        cancel=threading.Event();cancel.set()
        with self.assertRaises(RuntimeError):offline_desktop.search(folder,'report',cancel)

    def test_long_audio_decodes_in_chunks_and_transcribes_beyond_thirty_seconds(self):
        path=self.root/'meeting.wav';wav_file(path)
        seen=[]
        def recognize(audio,model,language,cancel):
            seen.append(len(audio));return 'Budget is 42. Ali will send it Monday.'
        with patch('core.offline_voice.transcribe',side_effect=recognize):
            text=meeting_audio.transcribe_file(path,self.root,'en',threading.Event())
        self.assertEqual(seen,[480000,480000,80000])
        self.assertIn('[00:01:00]',text)
        self.assertEqual(text.count('Budget is 42'),3)

    def test_audio_cancel_and_permission_prevent_late_chunks(self):
        path=self.root/'meeting.wav';wav_file(path)
        cancel=threading.Event()
        def recognize(*args):cancel.set();return 'late text'
        with patch('core.offline_voice.transcribe',side_effect=recognize) as speech:
            self.assertEqual(meeting_audio.transcribe_file(path,self.root,'en',cancel),'')
            speech.assert_called_once()
        with self.assertRaises(ValueError):
            meeting_audio.transcribe_file(path,self.root,'en',threading.Event(),allowed=lambda:False)

    def test_code_file_read_only_lines_secrets_and_limits(self):
        path=self.root/'example.py';path.write_text('def divide(a, b):\n    return a / b\n',encoding='utf-8')
        before=path.read_bytes();sections=code_review.file_sections(path)
        self.assertIn('2:     return a / b',sections[0][1]);self.assertEqual(path.read_bytes(),before)
        secret=self.root/'api_keys.json';secret.write_text('{"key":"fake"}')
        with self.assertRaises(ValueError):code_review.file_sections(secret)
        path.write_text('password = "fake-password"',encoding='utf-8')
        self.assertNotIn('fake-password',code_review.file_sections(path)[0][1])

    def test_git_review_includes_staged_and_unstaged_changes_without_drivers(self):
        def git(*args):
            return subprocess.run(['git','-c','core.hooksPath='+str(self.root/'no-hooks'),'-c','commit.gpgsign=false',
                                   '-c','user.name=Test','-c','user.email=test@example.invalid',*args],
                                  cwd=self.root,capture_output=True,check=True,
                                  creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        git('init','-q')
        file=self.root/'example.py';file.write_text('value = 1\n')
        secret=self.root/'api_keys.json';secret.write_text('{"secret":"fake"}')
        git('add','example.py','api_keys.json');git('commit','-qm','initial')
        file.write_text('value = 2\n');git('add','example.py');file.write_text('value = 3\n')
        secret.write_text('{"secret":"changed"}')
        git('config','diff.external','must-not-execute')
        sections=code_review.diff_sections(self.root,threading.Event())
        self.assertEqual(len(sections),1);self.assertEqual(sections[0][0],'example.py')
        self.assertIn('+value = 3',sections[0][1]);self.assertIn('-value = 1',sections[0][1])
        self.assertEqual(file.read_text(),'value = 3\n')

    def test_split_analysis_covers_all_source_without_silent_truncation(self):
        text='Evidence 42. '*1000
        chunks=split_sections([('source',text)],900)
        self.assertTrue(all(len(chunk)<=900 for chunk in chunks))
        self.assertEqual(''.join(chunk.partition('\n')[2] for chunk in chunks),text)
        with self.assertRaises(ValueError):split_sections([('source','x'*200001)],900)


class StudioTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.LocalUITests.setUpClass.__func__)
    setUp=fixtures.LocalUITests.setUp
    wait_for=fixtures.LocalUITests.wait_for
    start_local=fixtures.LocalUITests.start_local

    def tearDown(self):
        studio=getattr(self,'studio',None)
        if studio:studio.reject();QTest.qWait(10)
        fixtures.LocalUITests.tearDown(self)

    def open(self):self.studio=AIStudio(self.win);self.studio.show();return self.studio

    def test_model_advice_never_generates_or_downloads_and_apply_is_explicit(self):
        with fixtures.FakeOllama() as server:
            server.show={'capabilities':['completion']}
            Settings(server.url,'local',autostart=False).save('ollama')
            page=self.open().pages['models'];page.refresh()
            self.wait_for(lambda:not page.busy)
            self.assertTrue(page.rows)
            self.assertEqual(config_manager.load_api_keys()['ollama_model'],'local')
            self.assertNotIn('/api/chat',[path for path,_ in server.requests])
            self.assertNotIn('/api/pull',[path for path,_ in server.requests])
            page.apply()
            self.assertEqual(config_manager.load_api_keys()['ollama_model'],page.rows[0]['name'])

    def test_chat_offline_tools_are_opt_in_and_approved_before_launch(self):
        with fixtures.FakeOllama() as server:
            server.show={'capabilities':['completion','tools']}
            Settings(server.url,'local',autostart=False).save('ollama')
            config_manager._patch_config(local_tools_enabled=True)
            offline_desktop.save(True,self.temp.name)
            def respond(payload):
                if payload['messages'][-1]['role']=='tool':return [{'message':{'content':'Launch requested.'},'done':True}]
                return [{'message':{'tool_calls':[{'function':{'name':'open_local_app','arguments':{'app':'notepad'}}}]},'done':True}]
            server.chat_handler=respond
            runtime=self.start_local()
            with patch('brave_offline_actions.ask_permission',return_value=True), \
                 patch('core.offline_desktop.executable',return_value=['C:/Windows/System32/notepad.exe']), \
                 patch('core.offline_desktop.subprocess.Popen') as launch:
                runtime.submit('Open notepad.',[])
                self.wait_for(lambda:not runtime.busy and len(runtime.history)==2)
                launch.assert_called_once()
            payload=next(body for path,body in server.requests if path=='/api/chat')
            self.assertIn('open_local_app',[tool['function']['name'] for tool in payload['tools']])

    def test_declining_offline_action_does_not_launch(self):
        from brave_offline_actions import execute
        offline_desktop.save(True,self.temp.name)
        with patch('brave_offline_actions.ask_permission',return_value=False), \
             patch('core.offline_desktop.subprocess.Popen') as launch:
            with self.assertRaises(ValueError):execute(self.win,'open_local_app',{'app':'notepad'},threading.Event())
            launch.assert_not_called()

    def test_permission_dialog_closes_on_cancellation(self):
        from brave_offline_actions import ask_permission
        from PyQt6.QtCore import QTimer
        cancel=threading.Event();QTimer.singleShot(30,cancel.set)
        self.assertFalse(ask_permission(self.win,'open_local_app',{'app':'notepad'},cancel,lambda:True))

    def test_late_approval_after_request_expiry_does_not_launch(self):
        from brave_offline_actions import execute
        offline_desktop.save(True,self.temp.name)
        active=[True]
        def approve(*args):active[0]=False;return True
        with patch('brave_offline_actions.ask_permission',side_effect=approve), \
             patch('core.offline_desktop.subprocess.Popen') as launch:
            with self.assertRaises(RuntimeError):execute(self.win,'open_local_app',{'app':'notepad'},threading.Event(),lambda:active[0])
            launch.assert_not_called()

    def test_cancelled_model_advice_ignores_late_worker(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama')
            entered,release=threading.Event(),threading.Event()
            def recommend(*args):entered.set();release.wait(2);return []
            page=self.open().pages['models']
            with patch('core.model_recommender.recommend',side_effect=recommend):
                page.refresh();self.wait_for(entered.is_set);page.cancel();release.set();QTest.qWait(60)
                self.assertFalse(page.busy);self.assertEqual(page.status.text(),'Bekor qilindi.')

    def test_filename_tool_survives_nested_qt_loop_after_http_finishes(self):
        with fixtures.FakeOllama() as server:
            server.show={'capabilities':['completion','tools']}
            Settings(server.url,'local',autostart=False).save('ollama')
            config_manager._patch_config(local_tools_enabled=True)
            offline_desktop.save(True,self.temp.name)
            (Path(self.temp.name)/'budget.txt').write_text('synthetic')
            def respond(payload):
                if payload['messages'][-1]['role']=='tool':return [{'message':{'content':'budget.txt'},'done':True}]
                return [{'message':{'tool_calls':[{'function':{'name':'find_local_files','arguments':{'query':'budget'}}}]},'done':True}]
            server.chat_handler=respond
            runtime=self.start_local();runtime.submit('Find budget.',[])
            self.wait_for(lambda:not runtime.busy and len(runtime.history)==2)
            self.assertEqual(runtime.history[-1]['content'],'budget.txt')
            self.assertEqual(runtime.last_request['tool_rounds'],1)

    def test_printed_tool_json_is_never_executed_as_an_action(self):
        with fixtures.FakeOllama() as server:
            server.show={'capabilities':['completion','tools']}
            Settings(server.url,'local',autostart=False).save('ollama')
            config_manager._patch_config(local_tools_enabled=True)
            offline_desktop.save(True,self.temp.name)
            server.chunks=[{'message':{'content':'{"name":"open_local_app","arguments":{"app":"notepad"}}'},'done':True}]
            runtime=self.start_local()
            with patch('core.offline_desktop.subprocess.Popen') as launch:
                runtime.submit('Show a function call.',[])
                self.wait_for(lambda:not runtime.busy)
                launch.assert_not_called()
                self.assertEqual(runtime.last_request['status'],'error')
                self.assertEqual(runtime.history,[])

    def test_pipeline_maps_all_chunks_and_reduces_to_final_answer(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama')
            server.chat_handler=lambda payload:[{'message':{'content':'Evidence budget 42.'},'done':True}]
            job=AnalysisJob([('meeting','Budget 42. '*1000)],'Summarize tasks.',self.win)
            results=[];job.finished.connect(lambda *args:results.append(args));job.start()
            self.wait_for(lambda:bool(results),timeout=7000)
            self.assertEqual(results[0],('Evidence budget 42.','',False))
            requests=[body for path,body in server.requests if path=='/api/chat']
            self.assertGreater(len(requests),2)
            self.assertEqual(len(requests),job.initial_chunks+1)
            self.assertTrue(all('tools' not in body for body in requests))

    def test_pipeline_cancel_during_stream_never_reduces_late_results(self):
        from core.local_jobs import gate
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama')
            server.pause=threading.Event()
            job=AnalysisJob([('meeting','Budget 42. '*700)],'Summarize.',self.win)
            results=[];job.finished.connect(lambda *args:results.append(args));job.start()
            self.wait_for(lambda:any(path=='/api/chat' for path,_ in server.requests))
            job.cancel();server.pause.set();QTest.qWait(50)
            self.assertEqual(results,[('','',True)]);self.assertIsNone(gate.active)
            self.assertEqual(sum(path=='/api/chat' for path,_ in server.requests),1)

    def test_meeting_and_code_review_keep_original_files_and_draft(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama')
            studio=self.open();page=studio.pages['meeting']
            page.transcript.setPlainText('[00:00:00] Ali will send the budget 42 on Monday.')
            page.summarize();self.wait_for(lambda:bool(page.answer))
            self.win._input.setText('draft');page.insert()
            self.assertEqual(self.win._input.text(),'draft\n\nSalom dunyo')
            code=Path(self.temp.name)/'sample.py';code.write_text('answer = 1 / 0\n')
            before=code.read_bytes();review=studio.pages['review'];review.path.setText(str(code))
            review.review();self.wait_for(lambda:bool(review.answer))
            self.assertEqual(code.read_bytes(),before)
            self.assertIn('1: answer',review.preview.toPlainText())

    def test_dictionary_tab_saves_and_tests_real_terms(self):
        page=self.open().pages['dictionary'];page.add({'term':'Shahzod','recognized':'shaxzod','pronunciation':'Shah zod'})
        page.save();page.sample.setText('shaxzod Shahzod');page.test()
        self.assertIn('Shahzod Shahzod',page.preview.toPlainText())
        self.assertIn('Shah zod',page.preview.toPlainText())
        self.assertEqual(speech_dictionary.load()[0]['term'],'Shahzod')

    def test_edited_transcript_invalidates_previous_analysis_without_sending(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama')
            page=self.open().pages['meeting'];page.transcript.setPlainText('Budget is 42.')
            page.summarize();self.wait_for(lambda:bool(page.answer))
            count=len(server.requests)
            page.transcript.setPlainText('Budget changed to 84.')
            self.assertEqual(page.answer,'');self.assertEqual(page.result.toPlainText(),'')
            self.assertTrue(all(not button.isEnabled() for button in page.output_buttons))
            self.assertEqual(len(server.requests),count)

    def test_studio_renders_all_tabs_themes_and_languages(self):
        import brave_ui
        for theme in ('dark','light','hacker'):
            for lang in ('uz','en','ru'):
                brave_ui.set_theme(self.win,theme,persist=False);brave_ui.set_language(self.win,lang,persist=False)
                studio=AIStudio(self.win);studio.show()
                self.assertEqual(studio.tabs.count(),6)
                for key,page in studio.pages.items():
                    studio.select_tab(key);QTest.qWait(25)
                    self.assertLessEqual(studio.height(),self.win.screen().availableGeometry().height())
                    target=os.environ.get('BRAVE_STUDIO_PREVIEWS')
                    if target:
                        root=Path(target);root.mkdir(parents=True,exist_ok=True)
                        studio.grab().save(str(root/f'studio-{key}-{theme}-{lang}.png'))
                studio.reject();QTest.qWait(5)


if __name__=='__main__':unittest.main()
