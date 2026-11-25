"""Offline voice routing, model integrity, Uzbek text and cancellation regressions."""
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import numpy as np
from core import offline_voice, uzbek_tts
from core.local_jobs import Cancelled


class UzbekTextTests(unittest.TestCase):
    def test_latin_apostrophes_and_cyrillic_keep_uzbek_letters(self):
        for mark in ("'", '‘', '’', 'ʻ', 'ʼ', '`'):
            text=uzbek_tts.plain_text(f'O{mark}zbekcha g{mark}oya, shahar, choy, yaxshi, jahon.')
            self.assertEqual(uzbek_tts.cyrillic(text),'ўзбекча ғоя, шаҳар, чой, яхши, жаҳон.')
        self.assertEqual(uzbek_tts.cyrillic('Ўзбекча Ғоя'),'ўзбекча ғоя')
        self.assertEqual(uzbek_tts.cyrillic("Eshik, men, yetti, ma'lumot"),'эшик, мен, етти, маълумот')

    def test_numbers_are_spoken_and_markdown_code_and_urls_omitted(self):
        text=uzbek_tts.plain_text('**Salom** [do‘stim](https://example.com). 2026 yil, 85%. ```python\nprint(7)\n```')
        self.assertIn('ikki ming yigirma olti',text)
        self.assertIn('sakson besh foiz',text)
        self.assertNotIn('http',text)
        self.assertNotIn('print',text)
        self.assertEqual(uzbek_tts.number_words('007'),'nol nol yetti')

    def test_long_replies_remain_bounded_and_keep_complete_words(self):
        chunks=list(uzbek_tts.text_chunks('yordamchi '*100+'x'*500))
        self.assertTrue(all(len(chunk)<=180 for chunk in chunks))
        self.assertEqual(''.join(chunks).replace(' ',''),'yordamchi'*100+'x'*500)


class UzbekVoiceTests(unittest.TestCase):
    def tearDown(self):
        uzbek_tts._cache=None

    def test_selected_neural_voice_never_constructs_windows_speech(self):
        import win32com.client
        event=threading.Event()
        with patch.object(uzbek_tts,'speak') as neural,patch.object(win32com.client,'Dispatch') as sapi:
            offline_voice.speak('Salom',event,uzbek_tts.VOICE_ID)
            neural.assert_called_once_with('Salom',event)
            sapi.assert_not_called()

    def test_missing_model_never_downloads_or_falls_back(self):
        import requests
        with tempfile.TemporaryDirectory() as folder,patch.object(requests.Session,'get') as network, \
                patch.object(uzbek_tts,'prepare_model') as download:
            with self.assertRaisesRegex(ValueError,'yuklang'):
                list(uzbek_tts.synthesize('Salom',threading.Event(),folder))
            network.assert_not_called();download.assert_not_called()

    def test_cancel_before_inference_never_loads_model(self):
        event=threading.Event();event.set()
        with patch.object(uzbek_tts,'_load') as load:
            self.assertEqual(list(uzbek_tts.synthesize('Salom',event)),[])
            load.assert_not_called()

    def test_cancel_during_inference_discards_generated_audio(self):
        event=threading.Event();session=Mock()
        def run(*args):
            event.set();return [np.ones((1,1600),dtype='float32')]
        session.run.side_effect=run
        with patch.object(uzbek_tts,'_load',return_value=(session,{'с':1,'а':2,'л':3,'о':4,'м':5},16000)):
            self.assertEqual(list(uzbek_tts.synthesize('Salom',event)),[])

    def test_waiting_for_another_playback_can_be_cancelled(self):
        event=threading.Event();event.set()
        lock=threading.Lock();lock.acquire()
        try:
            with self.assertRaises(Cancelled):
                with uzbek_tts._locked(lock,event):pass
        finally:lock.release()

    def test_corrupt_files_are_rejected_before_runtime_is_created(self):
        import onnxruntime
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in uzbek_tts.FILES:(root/name).write_bytes(b'broken')
            with patch.object(onnxruntime,'InferenceSession') as runtime:
                with self.assertRaisesRegex(ValueError,'buzilgan'):uzbek_tts._load(root)
                runtime.assert_not_called()

    def test_local_runtime_inputs_follow_vits_blank_and_attention_contract(self):
        session=Mock();session.run.return_value=[np.ones((1,1600),dtype='float32')*.2]
        with patch.object(uzbek_tts,'_load',return_value=(session,{'с':1,'а':2,'л':3,'о':4,'м':5},16000)):
            chunks=list(uzbek_tts.synthesize('Salom',threading.Event()))
        inputs=session.run.call_args.args[1]
        self.assertEqual(inputs['input_ids'].tolist(),[[0,1,0,2,0,3,0,4,0,5,0]])
        self.assertEqual(inputs['input_ids'].dtype,np.int64)
        self.assertTrue((inputs['attention_mask']==1).all())
        self.assertEqual(chunks[0][1],16000)

    def test_download_hash_failure_keeps_existing_model_and_removes_partial(self):
        import requests
        data=b'incomplete download'
        response=Mock();response.headers={};response.iter_content.return_value=iter([data])
        response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'model.onnx').write_bytes(b'previous')
            with patch.object(uzbek_tts,'model_directory',return_value=root), \
                    patch.object(uzbek_tts,'FILES',{'model.onnx':('onnx/model.onnx',hashlib.sha256(b'expected').hexdigest())}), \
                    patch.object(requests.Session,'get',return_value=response):
                with self.assertRaises(ValueError):uzbek_tts.prepare_model()
            self.assertEqual((root/'model.onnx').read_bytes(),b'previous')
            self.assertFalse((root/'model.onnx.part').exists())

    def test_playback_cancel_aborts_stream_before_next_chunk(self):
        import sounddevice
        event=threading.Event();stream=Mock()
        stream.__enter__=Mock(return_value=stream);stream.__exit__=Mock(return_value=False)
        stream.write.side_effect=lambda audio:event.set()
        with patch.object(uzbek_tts,'synthesize',return_value=iter([(np.zeros(16000,dtype='float32'),16000)])), \
                patch.object(sounddevice,'OutputStream',return_value=stream),patch('core.audio_devices.resolve',return_value=None):
            uzbek_tts.speak('Salom',event)
        stream.write.assert_called_once();stream.abort.assert_called_once()


if __name__=='__main__':unittest.main()
