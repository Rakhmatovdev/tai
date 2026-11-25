"""Real slash modes, OCR, speech quality and code tests on synthetic data only."""
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


def main():
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtTest import QTest
    from PyQt6.QtCore import QRect
    from PyQt6.QtGui import QPixmap,QColor
    from PIL import Image,ImageDraw,ImageFont
    import numpy as np
    import ui
    from brave_local_chat import LocalChat
    from brave_ai_studio import open_studio
    from brave_test_runner import open_runner
    from brave_text_import import open_import
    from brave_image_editor import ImageCanvas
    from core import workspace_store,speaker_labels,meeting_sessions
    from core.ollama_chat import Settings
    from core.offline_voice import model_directory
    from core.live_meeting import run
    from core.model_router import route
    from core.model_performance import estimates
    from memory import config_manager
    from smoke_ai_extensions import voices
    from core.local_ocr import options
    ocr_executable,ocr_languages=options()
    cfg=Settings.read();speech_model=model_directory();speaker_model=speaker_labels.model_path()
    app=QApplication.instance() or QApplication([]);results={'complete':False}
    def checkpoint():Path('logs/slash-real-smoke.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    def wait_for(predicate,seconds=240):
        until=time.monotonic()+seconds
        while not predicate() and time.monotonic()<until:QTest.qWait(20)
        if not predicate():raise RuntimeError('Slash workflow smoke timed out')
    with tempfile.TemporaryDirectory(prefix='brave-slash-smoke-') as directory:
        root=Path(directory);config=root/'settings.json'
        config.write_text(json.dumps({'chat_provider':'ollama','ollama_model':cfg.model,'ollama_url':cfg.url,
            'ollama_profile':'balanced','ollama_autostart':False,'ollama_thinking':'off','local_voice_reply':False,
            'local_stt_path':str(speech_model),'local_ocr_executable':ocr_executable,'local_ocr_languages':ocr_languages,'ui_language':'en'}))
        with (patch.object(ui,'API_FILE',config),patch.object(config_manager,'CONFIG_FILE',config),
              patch.object(workspace_store,'directory',return_value=root),patch.object(speaker_labels,'model_path',return_value=speaker_model),
              patch.object(ui.MainWindow,'_check_config',return_value=True),patch.object(ui.MainWindow,'_check_autostart',return_value=False)):
            win=ui.MainWindow('');win.show();runtime=LocalChat(win);win._local_chat=runtime
            for name,prompt,expected in [('fast','/fast What is 2 plus 2? Answer one digit.','4'),
                ('plan','/plan Give a short three-step plan to organize a project.',''),
                ('translate','/translate en Loyiha budjeti 42 dollar.','42'),
                ('think','/think What is 17 times 23? Give the result and a brief check.','391')]:
                print('Real command: /'+name,flush=True)
                before=len(runtime.history);previous_metrics=runtime.last_request
                started=time.monotonic();win._input.setText(prompt);win._send()
                wait_for(lambda:not runtime.busy and runtime.last_request is not previous_metrics)
                assert len(runtime.history)==before+2,(prompt,runtime.last_request,win._log.toPlainText()[-1200:])
                answer=runtime.history[-1]['content'];assert not expected or expected in answer,answer
                results[name]={'answer':answer,'elapsed_s':time.monotonic()-started,'model':runtime.last_request.get('model'),
                               'profile':runtime.last_request.get('profile')}
                print(name+' completed in '+str(round(time.monotonic()-started,2))+'s',flush=True)
                checkpoint()
            print('Real /totext OCR',flush=True)
            image=root/'printed-budget.png';canvas=Image.new('RGB',(1000,250),'white')
            draw=ImageDraw.Draw(canvas);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',48)
            draw.text((30,70),'Budget 42 dollars. Ali: Monday.',fill='black',font=font);canvas.save(image)
            dialog=open_import(win,[str(image)]);started=time.monotonic();dialog.start();wait_for(lambda:not dialog.worker)
            assert '42' in dialog.answer and 'Monday' in dialog.answer,dialog.status.text()
            results['totext_ocr']={'text':dialog.answer,'elapsed_s':time.monotonic()-started};checkpoint();dialog.reject()
            print('Real speech models with accurate pause-aware chunks',flush=True)
            audio=voices(root)
            audio_dialog=open_import(win,[str(root/'voice-2.wav')]);audio_dialog.language.setCurrentIndex(audio_dialog.language.findData('en'))
            audio_dialog.start();wait_for(lambda:not audio_dialog.worker)
            assert 'Monday' in audio_dialog.answer,audio_dialog.status.text()
            results['totext_audio']={'text':audio_dialog.answer};audio_dialog.reject();checkpoint()
            stop=threading.Event()
            class Stream:
                def __init__(self,**kwargs):self.callback=kwargs['callback']
                def __enter__(self):
                    for start in range(0,len(audio),8000):
                        block=audio[start:start+8000,None];self.callback(block,len(block),None,None)
                    stop.set();return self
                def __exit__(self,*args):pass
            started=time.monotonic()
            with patch('core.audio_devices.resolve',return_value=None):
                transcript=run(str(speech_model),'en',stop,threading.Event(),lambda:True,diarize=True,quality='accurate',stream_factory=Stream)
            assert 'Speaker 1:' in transcript and 'Speaker 2:' in transcript,transcript
            results['accurate_speech']={'audio_seconds':len(audio)/16000,'elapsed_s':time.monotonic()-started,'transcript':transcript}
            checkpoint()
            print('Draft persistence and restore',flush=True)
            studio=open_studio(win,'meeting');page=studio.pages['meeting'];page.transcript.setPlainText(transcript)
            page.live_notes.setPlainText('Ali will send the report Monday.');page.save_draft();identity=page.session_id
            studio.reject();QTest.qWait(20);studio=open_studio(win,'meeting');page=studio.pages['meeting']
            assert page.session_id==identity and page.transcript.toPlainText()==transcript
            assert not getattr(win,'_meeting_recording',False)
            results['meeting_recovery']={'restored':True,'notes':page.live_notes.toPlainText()}
            checkpoint()
            print('Real multi-file edit with test command and group undo',flush=True)
            target=root/'calculation.py';target.write_text('def divide(a, b):\n    return a / b\n')
            tests=root/'test_calculation.py';tests.write_text('import unittest\nfrom calculation import divide\nclass T(unittest.TestCase):\n def test_normal(self): self.assertEqual(divide(4, 2), 2)\n def test_zero(self):\n  with self.assertRaises(ValueError): divide(4, 0)\n')
            helper=root/'constants.py';helper.write_text('ZERO_MESSAGE = "bad"\n')
            review=studio.pages['review'];review.mode='multi';review.selected_paths=[str(target),str(helper)]
            review.path.setText('calculation.py · constants.py');review.fix_instruction.setText(
                'In calculation.py, explicitly raise ValueError("Cannot divide by zero") if b is zero. '
                'In constants.py set ZERO_MESSAGE to "Cannot divide by zero".')
            review.propose_fix();wait_for(lambda:not review.busy)
            assert hasattr(review,'editor'),(review.status.text(),review.answer)
            editor=review.editor;assert len(editor.changes)==2,review.answer
            originals=[path.read_bytes() for path in (target,helper)];editor.apply()
            first_backups=list(review.last_backups)
            runner=open_runner(win,root);runner.args.setText('discover -s . -p test_calculation.py');runner.approved.setChecked(True);runner.start()
            wait_for(lambda:hasattr(runner,'last_result'))
            initial=runner.last_result
            results['multi_file_tests']={'initial_passed':initial['passed'],'initial_output':initial['output']}
            manual_fix=False
            if not initial['passed']:
                # Exercise the supported review/edit/test loop; never describe
                # an incorrect model proposal as a successful automatic fix.
                from brave_code_editor import MultiCodeEditDialog
                from core.code_changes import snapshot
                fixed='def divide(a, b):\n    if b == 0:\n        raise ValueError("Cannot divide by zero")\n    return a / b\n'
                repair=MultiCodeEditDialog(review,[(snapshot(target),fixed)]);repair.open();repair.apply();manual_fix=True
                del runner.last_result;runner.approved.setChecked(True);runner.start()
                wait_for(lambda:hasattr(runner,'last_result'))
            assert runner.last_result['passed'],runner.last_result
            results['multi_file_tests'].update(passed=True,manual_review_fix=manual_fix,output=runner.last_result['output']);runner.reject()
            if manual_fix:review.undo_edit()
            review.last_backups=first_backups;review.undo_edit();assert [path.read_bytes() for path in (target,helper)]==originals
            results['multi_file_tests']['undo_restored']=True
            print('Crop and opaque redaction',flush=True)
            pixmap=QPixmap(200,100);pixmap.fill(QColor('white'));edit=ImageCanvas(pixmap);edit.resize(400,200)
            edit.mode='redact';edit.selection=QRect(100,50,100,50);edit.apply_selection()
            assert edit.image.toImage().pixelColor(60,30)==QColor('black')
            results['redaction']={'opaque_black':True}
            win._input.setFocus();win._input.setText('/');QTest.qWait(100)
            Path('design-preview/slash').mkdir(parents=True,exist_ok=True)
            win._slash_menu.popup.grab().save(str(Path('design-preview/slash/slash-menu-en.png').resolve()))
            studio.grab().save(str(Path('design-preview/slash/meeting-en.png').resolve()))
            results['default_preserved']=Settings.read().model==cfg.model and Settings.read().profile=='balanced'
            studio.reject();runtime.shutdown();win.close();app.processEvents()
    results['complete']=True
    Path('logs/slash-real-smoke.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(results,ensure_ascii=True,indent=2),flush=True)


if __name__=='__main__':main()
