"""End-to-end local feature paths; cloud, microphone and speech are isolated."""
import asyncio
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch
from memory import config_manager
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_ollama as fixtures
from PyQt6.QtCore import QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from core.ollama_chat import Settings
from core import chat_memory,local_documents,offline_voice
from brave_history import HistoryStore
from brave_model_download import ModelPull


class StorageTests(unittest.TestCase):
    def test_memory_is_chat_scoped_and_stale_summary_is_invalidated(self):
        store=HistoryStore();self.addCleanup(store.close)
        history=[{'role':'user','content':'a'},{'role':'assistant','content':'b'}]
        memory=store.memory('one');memory.update(pinned='Keep UZ',summary='fact',covered=2,fingerprint=chat_memory.fingerprint(history))
        store.save_memory('one',memory)
        self.assertEqual(store.memory('two')['pinned'],'')
        self.assertEqual(chat_memory.validate(store.memory('one'),history)['summary'],'fact')
        history[0]['content']='edited'
        self.assertEqual(chat_memory.validate(store.memory('one'),history)['summary'],'')

    def test_branch_preserves_original_and_independent_source_previews(self):
        store=HistoryStore();self.addCleanup(store.close)
        store.append('one','user','question','12:00')
        key=store.add_source('one',{'label':'page 1','path':'doc.pdf','text':'fact'})
        store.append('one','assistant',f'answer [S1](brave-source://{key})','12:01')
        store.set_files('one',0,['doc.pdf'])
        branch=store.fork('one',2)
        self.assertEqual(store.files(branch,0),['doc.pdf'])
        body=store.messages(branch)[1][1]
        self.assertNotIn(key,body)
        newkey=body.split('brave-source://')[1].split(')')[0]
        store.delete('one')
        self.assertEqual(store.source(newkey)['text'],'fact')

    def test_clear_memory_coverage_prevents_recreating_removed_old_facts(self):
        history=[{'role':role,'content':'old fact'} for role in ('user','assistant')]
        memory={'enabled':True,'summary':'','pinned':'','covered':2,'fingerprint':chat_memory.fingerprint(history)}
        self.assertIsNone(chat_memory.summary_plan(memory,history,0))

    def test_retrieval_finds_late_text_and_obeys_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'project.txt';path.write_text('ordinary background\n'*200+'\nThe deadline budget is 42 units.',encoding='utf-8')
            rows,clipped=local_documents.retrieve([str(path)],'deadline budget',500,threading.Event())
            self.assertIn('42',rows[0]['text'])
            self.assertLessEqual(sum(len(row['text']) for row in rows),500)
            self.assertFalse(clipped)

    def test_pdf_page_sources_and_docx_text_are_extracted_locally(self):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
        from docx import Document
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'pages.pdf';writer=PdfWriter()
            for number in (1,2):
                page=writer.add_blank_page(width=300,height=300)
                font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
                page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})})
                stream=DecodedStreamObject();stream.set_data(f'BT /F1 12 Tf 20 200 Td (Budget page {number}) Tj ET'.encode())
                page[NameObject('/Contents')]=stream
            writer.write(path)
            chunks,_=local_documents.extract(path)
            self.assertTrue(any('p. 2' in row['label'] and 'page 2' in row['text'] for row in chunks))
            path=Path(folder)/'notes.docx';doc=Document();doc.add_paragraph('Launch Monday');doc.save(path)
            self.assertIn('Launch Monday',local_documents.extract(path)[0][0]['text'])

    def test_secret_files_and_unsupported_attachments_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'api_keys.json';path.write_text('{}')
            with self.assertRaises(ValueError):local_documents.validate_paths([path])
            path=Path(folder)/'program.exe';path.write_bytes(b'fake')
            with self.assertRaises(ValueError):local_documents.validate_paths([path])


class PullTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def pull(self,server,cancel=False):
        job=ModelPull(server.url,'local');results=[];progress=[]
        job.finished.connect(lambda *args:results.append(args));job.progress.connect(progress.append)
        job.start()
        if cancel:job.cancel()
        for _ in range(200):
            if results:break
            QTest.qWait(10)
        self.assertTrue(results)
        job.deleteLater()
        return results[0],progress

    def test_pull_stream_reports_layer_bytes_without_inference(self):
        with fixtures.FakeOllama() as server:
            result,progress=self.pull(server)
            self.assertEqual(result,('',False))
            self.assertEqual(progress[-1]['completed'],40)
            self.assertEqual([path for path,_ in server.requests],['/api/pull'])

    def test_cancel_is_immediate_and_never_becomes_success(self):
        with fixtures.FakeOllama() as server:
            result,_=self.pull(server,True)
            self.assertTrue(result[1])

    def test_redirect_and_disk_error_cannot_claim_success(self):
        with fixtures.FakeOllama() as server:
            server.post_overrides['/api/pull']=(302,{'status':'success'},{'Location':'https://example.com'})
            self.assertTrue(self.pull(server)[0][0])
        with fixtures.FakeOllama() as server:
            server.pull_chunks=[{'error':'no space left on disk'}]
            self.assertIn('Disk',self.pull(server)[0][0])


class ExtendedUITests(unittest.TestCase):
    setUpClass=classmethod(fixtures.LocalUITests.setUpClass.__func__)
    setUp=fixtures.LocalUITests.setUp
    wait_for=fixtures.LocalUITests.wait_for
    start_local=fixtures.LocalUITests.start_local
    def tearDown(self):
        manager=getattr(self.win,'_backend_manager',None)
        if manager:manager.shutdown();QTest.qWait(80)
        if getattr(self.win,'_local_voice',None):self.win._local_voice.cancel()
        fixtures.LocalUITests.tearDown(self)

    def test_old_turns_are_summarized_without_saving_hidden_summary_as_reply(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama')
            runtime=self.start_local()
            for index in range(12):
                for role in ('user','assistant'):
                    body=f'{index} '+('older fact '*25)
                    self.win._features.store.append(self.win._features.chat_id,role,body,'12:00')
            runtime.change_chat(self.win._features.store.messages(self.win._features.chat_id))
            def answer(payload):
                content='Remember budget 42.' if payload['messages'][0]['content'].startswith('Summarize') else 'Final visible reply'
                return [{'message':{'content':content},'done':True}]
            server.chat_handler=answer
            self.win._input.setText('What was agreed?');self.win._send()
            self.wait_for(lambda:len(self.win._features.store.messages(self.win._features.chat_id))==26 and not runtime.busy)
            memory=self.win._features.store.memory(self.win._features.chat_id)
            self.assertGreater(memory['covered'],0)
            self.assertIn('42',memory['summary'])
            main=[body for path,body in server.requests if path=='/api/chat'][-1]
            self.assertIn('Remember budget 42',main['messages'][0]['content'])
            rows=self.win._features.store.messages(self.win._features.chat_id)
            self.assertEqual(len(rows),26)
            self.assertEqual(rows[-1][1],'Final visible reply')

    def test_cancelled_summary_is_not_committed_or_followed_by_a_user_request(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama')
            runtime=self.start_local()
            runtime.history=[{'role':role,'content':'older '*100} for _ in range(8) for role in ('user','assistant')]
            server.pause=threading.Event()
            runtime.submit('hello',[])
            self.wait_for(lambda:runtime.phase=='memory' and bool(runtime.job))
            self.wait_for(lambda:any(path=='/api/chat' for path,_ in server.requests))
            runtime.cancel();server.pause.set();QTest.qWait(50)
            self.assertEqual(self.win._features.store.memory(self.win._features.chat_id)['summary'],'')
            self.assertEqual(sum(path=='/api/chat' for path,_ in server.requests),1)

    def test_large_history_uses_one_bounded_summary_without_unloading_between_requests(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url, 'local', profile='economy', autostart=False).save('ollama')
            runtime = self.start_local()
            runtime.history = [{'role': role, 'content': 'older fact ' * 200}
                               for _ in range(12) for role in ('user', 'assistant')]
            server.chat_handler = lambda payload: [
                {'message': {'content': 'Saved facts.' if payload['messages'][0]['content'].startswith('Summarize')
                             else 'Visible answer.'}, 'done': True}]
            runtime.submit('hello', [])
            self.wait_for(lambda: not runtime.busy)
            requests = [body for path, body in server.requests if path == '/api/chat']
            self.assertEqual(len(requests), 2)
            summary, answer = requests
            self.assertTrue(summary['messages'][0]['content'].startswith('Summarize'))
            self.assertLessEqual(summary['options']['num_predict'], 256)
            segment = summary['messages'][-1]['content'].split('Older conversation segment:\n')[1]
            self.assertLessEqual(len(segment), 1200)
            self.assertEqual(summary['keep_alive'], '1m')
            self.assertEqual(answer['keep_alive'], 0)
            self.assertEqual(runtime.history[-1]['content'], 'Visible answer.')
            # The remainder is deferred, not marked as already summarized.
            memory = self.win._features.store.memory(self.win._features.chat_id)
            self.assertLess(memory['covered'], 24)

    def test_documents_are_local_cited_and_source_preview_is_persisted(self):
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama');runtime=self.start_local()
            path=Path(self.temp.name)/'project.txt';path.write_text('Budget is 42 units.',encoding='utf-8')
            server.chunks=[{'message':{'content':'Budget: 42 [S1]'},'done':True}]
            self.win._drop_zone._set_file(str(path));self.win._input.setText('What is the budget?');self.win._send()
            self.wait_for(lambda:len(runtime.history)==2 and not runtime.busy)
            payload=next(body for url,body in server.requests if url=='/api/chat')
            self.assertIn('Budget is 42',payload['messages'][0]['content'])
            answer=self.win._features.store.messages(self.win._features.chat_id)[-1][1]
            self.assertIn('brave-source://',answer)
            key=answer.split('brave-source://')[1].split(')')[0]
            self.assertIn('42',self.win._features.store.source(key)['text'])
            self.assertEqual(self.win._features.store.files(self.win._features.chat_id,0),[str(path)])

    def test_regenerate_forks_original_history_and_sends_once(self):
        from brave_conversation import branch_last
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama');runtime=self.start_local()
            original=self.win._features.chat_id
            for role,body in [('user','before'),('assistant','prior'),('user','again'),('assistant','old answer')]:
                self.win._features.store.append(original,role,body,'12:00')
            self.win._features.switch_chat(original);QTest.qWait(20)
            before=self.win._features.store.messages(original)
            self.assertTrue(branch_last(self.win))
            new_id=self.win._features.chat_id
            self.wait_for(lambda:len(self.win._features.store.messages(new_id))==4)
            self.assertEqual(self.win._features.store.messages(original),before)
            self.assertNotEqual(new_id,original)
            self.assertEqual(sum(path=='/api/chat' for path,_ in server.requests),1)

    def test_edit_opens_unsent_draft_in_branch(self):
        from brave_conversation import branch_last
        runtime=self.start_local();old=self.win._features.chat_id
        self.win._features.store.append(old,'user','old question','12:00')
        with patch('brave_conversation.QInputDialog.getMultiLineText',return_value=('edited question',True)):
            self.assertTrue(branch_last(self.win,True))
        self.assertEqual(self.win._input.text(),'edited question')
        self.assertEqual(self.win._features.store.messages(self.win._features.chat_id),[])
        self.assertEqual(self.win._features.store.messages(old)[0][1],'old question')

    def test_provider_change_cancels_pending_regeneration_instead_of_sending_a_draft(self):
        from brave_conversation import branch_last
        self.start_local();old=self.win._features.chat_id
        self.win._features.store.append(old,'user','private local question','12:00')
        self.assertTrue(branch_last(self.win))
        self.win._active_provider='gemini'
        with patch.object(self.win,'_send') as send:
            QTest.qWait(140)
            send.assert_not_called()
        self.assertEqual(self.win._input.text(),'private local question')

    def test_backend_switch_closes_old_loop_preserves_draft_and_never_seeds_cloud(self):
        from brave_backend import BackendManager
        runtime=self.start_local();closed=threading.Event();seed=Mock()
        win=self.win
        class Adapter:
            def __init__(self):object.__setattr__(self,'_win',win)
            def __getattr__(self,name):return getattr(win,name)
            def __setattr__(self,name,value):setattr(win,name,value)
            def write_log(self,text):win._log.append_log(text)
        class Live:
            def __init__(self,bridge):
                bridge.can_change_chat=lambda:True;bridge.can_send_text=lambda:True;bridge.on_chat_change=seed
            async def run(self):
                try:await asyncio.Event().wait()
                finally:closed.set()
        manager=BackendManager(Adapter(),Live);self.win._backend_manager=manager
        self.win._input.setText('private draft')
        self.assertTrue(manager.switch('gemini'))
        self.wait_for(lambda:not manager.busy)
        seed.assert_not_called()
        self.assertEqual(self.win._input.text(),'private draft')
        proxy=manager.proxy
        self.assertTrue(manager.switch('ollama'))
        self.wait_for(lambda:not manager.busy and self.win._active_provider=='ollama')
        self.assertTrue(closed.is_set())
        proxy.write_log('OLD_RUNTIME_MUST_NOT_WRITE');QTest.qWait(20)
        self.assertNotIn('OLD_RUNTIME_MUST_NOT_WRITE',self.win._log.toPlainText())
        self.assertEqual(self.win._input.text(),'private draft')

    def test_local_voice_transcript_is_reviewable_and_cancel_discards_late_result(self):
        from brave_local_voice import LocalVoice
        self.start_local();voice=LocalVoice(self.win);self.win._local_voice=voice
        path=Path(self.temp.name)/'stt';path.mkdir();(path/'model.bin').touch()
        gate=threading.Event()
        def capture(stop,cancelled,allowed):gate.wait(1);return [0.0]*1600
        with patch('brave_local_voice.offline_voice.capture',side_effect=capture),patch('brave_local_voice.offline_voice.transcribe',return_value='hello offline'):
            voice.record(str(path),'en');revision=voice.revision
            voice.cancel();gate.set();QTest.qWait(60)
            self.assertNotEqual(voice.revision,revision)
            self.assertFalse(voice.busy)
            self.assertEqual(self.win._features.store.messages(self.win._features.chat_id),[])

    def test_main_microphone_sends_offline_turn_and_reads_local_reply(self):
        path=Path(self.temp.name)/'stt';path.mkdir();(path/'model.bin').touch()
        with fixtures.FakeOllama() as server:
            Settings(server.url,'local',autostart=False).save('ollama')
            config_manager._patch_config(local_stt_path=str(path),local_stt_language='uz',local_voice_reply=True)
            runtime=self.start_local()
            self.win._capabilities.policy['permissions']['network']=False
            spoken=threading.Event()
            with patch.object(offline_voice,'capture',return_value=[0.0]*1600) as capture, \
                    patch.object(offline_voice,'transcribe',return_value='Salom Brave') as recognize, \
                    patch.object(offline_voice,'speak',side_effect=lambda *args:spoken.set()) as speak:
                self.win._mute_btn.click()
                self.wait_for(lambda:len(runtime.history)==2 and spoken.is_set())
                self.assertEqual([row['content'] for row in runtime.history],['Salom Brave','Salom dunyo'])
                self.assertTrue(capture.call_args.kwargs['auto_stop'])
                self.assertEqual(recognize.call_args.args[2],'uz')
                self.assertEqual(speak.call_args.args[0],'Salom dunyo')
                self.assertEqual(self.win._active_provider,'ollama')
                self.assertFalse(self.win._text_only)
                self.assertTrue(self.win.can_send_text())

    def test_direct_voice_preserves_draft_created_during_recognition(self):
        runtime=self.start_local();voice=self.win._local_voice
        voice.direct_chat=self.win._features.chat_id;voice.busy=True
        self.win._input.setText('my unsent draft')
        voice.completed(voice.revision,'recognized words','')
        self.assertEqual(self.win._input.text(),'my unsent draft')
        self.assertIn('recognized words',self.win._log.toPlainText())
        self.assertEqual(runtime.history,[])

    def test_cancel_and_revoked_microphone_never_send_direct_transcript(self):
        runtime=self.start_local();voice=self.win._local_voice
        for cancel in (True,False):
            voice.direct_chat=self.win._features.chat_id;voice.busy=True;revision=voice.revision
            if cancel:voice.cancel()
            else:self.win._capabilities.policy['permissions']['microphone']=False
            voice.completed(revision,'must not send','')
            self.assertEqual(runtime.history,[])
            self.assertEqual(self.win._input.text(),'')

    def test_local_reply_mode_survives_restart_without_changing_cloud_mode(self):
        config_manager._patch_config(reply_mode='voice',local_voice_reply=True)
        self.win._features.enable_persistence()
        runtime=self.start_local()
        self.win._reply_mode.setCurrentIndex(self.win._reply_mode.findData('text'))
        self.assertFalse(config_manager.load_api_keys()['local_voice_reply'])
        self.assertEqual(config_manager.load_api_keys()['reply_mode'],'voice')
        self.win._reply_mode.setCurrentIndex(self.win._reply_mode.findData('voice'))
        self.assertTrue(config_manager.load_api_keys()['local_voice_reply'])
        runtime.shutdown();runtime.deleteLater()
        self.start_local()
        self.assertFalse(self.win._text_only)
        self.assertEqual(self.win._reply_mode.currentData(),'voice')

    def test_settings_applies_provider_switch_without_restart(self):
        from brave_settings import open_settings
        self.start_local()
        manager=Mock();manager.can_switch.return_value=True;manager.switch.return_value=True
        self.win._backend_manager=manager
        open_settings(self.win,'ai');form=self.win._quick_drawer.forms['ai']
        form.provider.setCurrentIndex(form.provider.findData('gemini'));form.key.setText('fake-key')
        form.apply()
        manager.switch.assert_called_once_with('gemini',refresh=True)
        self.assertNotIn('qayta oching',form.status.text())

    def test_neural_uzbek_voice_selection_saves_and_preview_uses_it(self):
        from brave_local_voice import VoiceDialog
        from core import uzbek_tts
        self.start_local()
        with patch.object(offline_voice,'voices',return_value=[]),patch.object(uzbek_tts,'ready',return_value=True):
            dialog=VoiceDialog(self.win)
            QTest.qWait(20)
            dialog.tts.setCurrentIndex(dialog.tts.findData(uzbek_tts.VOICE_ID))
            with patch.object(dialog.voice,'say') as speak:
                dialog.preview_voice()
                self.assertEqual(speak.call_args.kwargs,{'voice_id':uzbek_tts.VOICE_ID,'force':True})
            dialog.save()
            self.assertEqual(config_manager.load_api_keys()['local_voice_id'],uzbek_tts.VOICE_ID)
            dialog.reject();dialog.deleteLater()

    def test_failed_cloud_start_does_not_loop_and_can_return_to_local(self):
        from brave_backend import BackendManager
        self.start_local()
        factory=Mock(side_effect=RuntimeError('dependency unavailable'))
        manager=BackendManager(type('Adapter',(),{'_win':self.win})(),factory)
        self.win._backend_manager=manager
        self.assertTrue(manager.switch('gemini'))
        self.wait_for(lambda:not manager.busy)
        factory.assert_called_once()
        self.assertTrue(manager.can_switch())
        self.assertTrue(manager.switch('ollama'))
        self.assertEqual(self.win._active_provider,'ollama')

    def test_new_dialogs_render_all_themes_and_languages(self):
        import brave_ui
        from brave_i18n import translate
        from brave_local_voice import VoiceDialog
        from brave_model_download import DownloadDialog
        from brave_settings import open_settings
        from brave_conversation import memory_dialog,source_dialog
        self.start_local()
        with fixtures.FakeOllama() as server,patch('brave_local_voice.offline_voice.voices',return_value=[('Local voice','test')]):
            Settings(server.url,'local',autostart=False).save('ollama')
            source=self.win._features.store.add_source(self.win._features.chat_id,{'label':'plan.pdf · p. 2','path':'plan.pdf','text':'Budget is 42 units.'})
            for theme in ('dark','light','hacker'):
                brave_ui.set_theme(self.win,theme,persist=False)
                for lang in ('uz','en','ru'):
                    brave_ui.set_language(self.win,lang,persist=False)
                    open_settings(self.win,'ai');form=self.win._quick_drawer.forms['ai']
                    download=DownloadDialog(form);download.show();QTest.qWait(10)
                    self.assertEqual(download.windowTitle(),translate('Model yuklash'))
                    self.capture(download,f'brave-model-download-{theme}-{lang}.png');download.reject();download.deleteLater()
                    self.win._quick_drawer.accept()
                    voice=VoiceDialog(self.win);voice.show();QTest.qWait(10)
                    self.assertEqual(voice.windowTitle(),translate('Offline ovoz'))
                    self.capture(voice,f'brave-offline-voice-{theme}-{lang}.png');voice.reject();voice.deleteLater()
                    def close_memory():
                        dialog=QApplication.activeModalWidget()
                        self.capture(dialog,f'brave-chat-memory-{theme}-{lang}.png');dialog.reject()
                    QTimer.singleShot(20,close_memory);memory_dialog(self.win)
                    def close_source():
                        dialog=QApplication.activeModalWidget()
                        self.capture(dialog,f'brave-source-{theme}-{lang}.png');dialog.reject()
                    QTimer.singleShot(20,close_source);source_dialog(self.win,source)

    def capture(self,dialog,name):
        self.assertFalse(dialog.grab().isNull())
        if os.environ.get('BRAVE_UI_PREVIEWS'):
            target=Path(os.environ['BRAVE_UI_PREVIEWS']);target.mkdir(parents=True,exist_ok=True)
            dialog.grab().save(str(target/name))


class VoicePolicyTests(unittest.TestCase):
    def test_missing_model_never_downloads_during_transcription(self):
        with tempfile.TemporaryDirectory() as folder,patch('core.offline_voice.prepare_model') as download:
            with self.assertRaises(ValueError):offline_voice.transcribe([],folder,'en',threading.Event())
            download.assert_not_called()

    def test_system_speech_treats_model_output_as_plain_text(self):
        import win32com.client
        voice=Mock();voice.WaitUntilDone.return_value=True
        with patch.object(win32com.client,'Dispatch',return_value=voice):
            offline_voice.speak('<audio src="https://example.com"/> [label](https://example.com)',threading.Event())
        self.assertEqual(voice.Speak.call_args.args[1],17)

    def test_cancelled_playback_never_opens_a_speech_output(self):
        import win32com.client
        cancelled=threading.Event();cancelled.set()
        with patch.object(win32com.client,'Dispatch') as dispatch:
            offline_voice.speak('late reply',cancelled)
            dispatch.assert_not_called()

    def test_speech_model_is_loaded_from_local_files_only(self):
        import faster_whisper
        model=Mock();model.transcribe.return_value=(iter([Mock(text='hello')]),None)
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder)/'model.bin').touch()
            with patch.object(faster_whisper,'WhisperModel',return_value=model) as factory:
                self.assertEqual(offline_voice.transcribe([0.0],folder,'en',threading.Event()),'hello')
                self.assertTrue(factory.call_args.kwargs['local_files_only'])
        offline_voice._models.clear()


if __name__=='__main__':unittest.main()
