"""Real installed-model checks; synthetic images/audio and temporary code only."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))


def voices(root):
    import numpy as np
    import pythoncom
    import win32com.client
    from core.meeting_audio import audio_chunks
    pythoncom.CoInitialize()
    clips=[]
    try:
        voice=win32com.client.Dispatch('SAPI.SpVoice')
        tokens=list(voice.GetVoices())
        selected=[next(token for token in tokens if name in token.GetDescription()) for name in ('Irina','Zira')]
        for index in (0,1,0,1):
            path=root/f'voice-{len(clips)}.wav';stream=win32com.client.Dispatch('SAPI.SpFileStream');stream.Open(str(path),3,False)
            voice.AudioOutputStream=stream;voice.Voice=selected[index];voice.Rate=-1
            phrase=('My name is David. The project budget is forty two dollars.' if index==0 else
                    'My name is Zira. I will send the report on Monday.')
            voice.Speak(phrase,16);stream.Close()
            audio=np.concatenate([audio for _,audio in audio_chunks(path,threading.Event())])
            clips.append(audio);clips.append(np.zeros(16000,dtype='float32'))
    finally:pythoncom.CoUninitialize()
    return np.concatenate(clips)


def main():
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtTest import QTest
    from PIL import Image,ImageDraw
    import numpy as np
    import ui
    from brave_ai_studio import AIStudio
    from brave_local_chat import LocalChat
    from core import workspace_store,ai_extensions,speaker_labels
    from core.ollama_chat import Settings
    from core.offline_voice import model_directory
    from core.live_meeting import run
    from core.model_router import route
    from core.local_vision import encode_images
    from memory import config_manager
    selected=Settings.read();speech_model=model_directory();speaker_model=speaker_labels.model_path()
    app=QApplication.instance() or QApplication([]);results={}
    def wait_for(predicate,seconds=240):
        end=time.monotonic()+seconds
        while not predicate() and time.monotonic()<end:QTest.qWait(20)
        if not predicate():raise RuntimeError('Extension smoke timed out')
    with tempfile.TemporaryDirectory(prefix='brave-extension-smoke-') as folder:
        root=Path(folder);config=root/'settings.json'
        config.write_text(json.dumps({'chat_provider':'ollama','ollama_url':selected.url,'ollama_model':selected.model,
            'ollama_profile':'quality','ollama_thinking':'off','ollama_autostart':False,'local_voice_reply':False,'ui_language':'en'}))
        print('Real local speaker embeddings and streaming STT',flush=True)
        audio=voices(root);stop=threading.Event()
        class Stream:
            def __init__(self,**kwargs):self.callback=kwargs['callback']
            def __enter__(self):
                for start in range(0,len(audio),8000):
                    block=audio[start:start+8000,None];self.callback(block,len(block),None,None)
                stop.set();return self
            def __exit__(self,*args):pass
        started=time.monotonic()
        with patch('core.audio_devices.resolve',return_value=None):
            transcript=run(str(speech_model),'en',stop,threading.Event(),lambda:True,diarize=True,stream_factory=Stream)
        assert 'Speaker 1:' in transcript and 'Speaker 2:' in transcript,transcript
        results['streaming_speakers']={'seconds':len(audio)/16000,'elapsed_s':time.monotonic()-started,'transcript':transcript,
                                      'source':'SAPI Irina/Zira alternating, simulated microphone transport'}
        with (patch.object(ui,'API_FILE',config),patch.object(config_manager,'CONFIG_FILE',config),
              patch.object(workspace_store,'directory',return_value=root),
              patch.object(speaker_labels,'model_path',return_value=speaker_model),
              patch.object(ui.MainWindow,'_check_config',return_value=True),patch.object(ui.MainWindow,'_check_autostart',return_value=False)):
            win=ui.MainWindow('');win.show();studio=AIStudio(win);studio.show()
            ai_extensions.save(auto_route=True)
            runtime=LocalChat(win);win._local_chat=runtime
            print('Real task routing and code diff/apply/restore',flush=True)
            before=Settings.read().model
            coder=route(Settings.read(),'python code debug',False,threading.Event())
            results['routing']={'default':before,'code_model':coder.model,'default_unchanged':Settings.read().model==before}
            target=root/'sample.py';target.write_text('def divide(a, b):\n    return a / b\n',encoding='utf-8')
            review=studio.pages['review'];review.path.setText(str(target))
            review.fix_instruction.setText('Raise ValueError with a clear message when b is zero. Preserve normal division.')
            started=time.monotonic();review.propose_fix();wait_for(lambda:not review.busy)
            assert hasattr(review,'editor'),review.status.text()
            editor=review.editor;proposed=editor.editor.toPlainText();diff=editor.diff.toPlainText()
            assert 'ValueError' in proposed,proposed
            original=target.read_bytes();editor.apply();assert target.read_bytes()!=original
            review.undo_edit();assert target.read_bytes()==original
            results['code_fix']={'elapsed_s':time.monotonic()-started,'diff':diff,'restored':True}
            print('Real screen analysis using a synthetic error screenshot',flush=True)
            image=root/'synthetic-screen.png';canvas=Image.new('RGB',(600,300),'white');draw=ImageDraw.Draw(canvas)
            draw.text((25,80),'Python console\nZeroDivisionError: division by zero',fill='black',font_size=25);canvas.save(image)
            page=studio.pages['screen'];page.encoded=encode_images([image],threading.Event())[0][0]
            page.question.setText('What Python error is visible? Answer briefly in English.')
            started=time.monotonic();page.inspect();wait_for(lambda:not page.busy)
            assert page.answer and ('zero' in page.answer.lower() or 'division' in page.answer.lower()),page.status.text()
            results['screen']={'elapsed_s':time.monotonic()-started,'answer':page.answer}
            print('Real image chat followed by a question without reattachment',flush=True)
            red=root/'red.png';Image.new('RGB',(100,100),'red').save(red)
            runtime.submit('What is the main image color? Answer with one English color word.',[str(red)],'vision')
            wait_for(lambda:not runtime.busy);assert runtime.history,runtime.last_request
            first=runtime.history[-1]['content'];assert 'red' in first.lower(),first
            runtime.submit('What was the image color? Answer one English word.',[])
            wait_for(lambda:not runtime.busy);assert len(runtime.history)==4,runtime.last_request
            second=runtime.history[-1]['content'];assert 'red' in second.lower(),second
            results['image_followup']={'first':first,'followup':second,'model':runtime.last_request.get('model'),
                                       'default_unchanged':Settings.read().model==before}
            studio.select_tab('screen');studio.grab().save(str(Path('logs/extensions-real-smoke.png').resolve()))
            runtime.shutdown();studio.reject();win.close();app.processEvents()
    Path('logs/extensions-real-smoke.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(results,ensure_ascii=True,indent=2),flush=True)


if __name__=='__main__':main()
