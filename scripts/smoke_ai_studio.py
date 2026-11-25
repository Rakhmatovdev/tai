"""Explicit real-model checks for AI Studio using synthetic files/audio only."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch
import wave

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))


def synthesize(path):
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    try:
        voice=win32com.client.Dispatch('SAPI.SpVoice')
        for token in voice.GetVoices():
            if 'Zira' in token.GetDescription():voice.Voice=token;break
        stream=win32com.client.Dispatch('SAPI.SpFileStream')
        stream.Open(str(path),3,False)
        voice.AudioOutputStream=stream
        voice.Rate=-1
        voice.Speak(('This is a Brave project meeting. The budget is forty two dollars. '
                     'Ali will send the report on Monday. No other decision was made. ')*6,16)
        stream.Close()
    finally:pythoncom.CoUninitialize()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--audio',action='store_true',help='Create synthetic local SAPI audio and use installed Whisper')
    args=parser.parse_args()
    import ui
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication,QMessageBox
    from brave_ai_studio import AIStudio
    from brave_local_chat import LocalChat
    from core import workspace_store,offline_desktop,speech_dictionary
    from core.ollama_chat import Settings
    from core.offline_voice import model_directory
    from core.meeting_audio import transcribe_file
    from memory import config_manager
    import threading

    selected=Settings.read(); speech_model=model_directory()
    app=QApplication.instance() or QApplication([])
    results={}
    def wait_for(predicate,seconds=180):
        deadline=time.monotonic()+seconds
        while not predicate() and time.monotonic()<deadline:QTest.qWait(20)
        if not predicate():raise RuntimeError('AI Studio real smoke timed out')
    with tempfile.TemporaryDirectory(prefix='brave-studio-smoke-') as folder:
        root=Path(folder);config=root/'config.json'
        config.write_text(json.dumps({'chat_provider':'ollama','ollama_model':selected.model,
            'ollama_url':selected.url,'ollama_profile':'balanced','ollama_autostart':selected.autostart,
            'ollama_thinking':'off','local_tools_enabled':True,'local_voice_reply':False,'ui_language':'en'}))
        with (patch.object(ui,'API_FILE',config),patch.object(config_manager,'CONFIG_FILE',config),
              patch.object(workspace_store,'directory',return_value=root),
              patch.object(ui.MainWindow,'_check_config',return_value=True),
              patch.object(ui.MainWindow,'_check_autostart',return_value=False)):
            win=ui.MainWindow('');win.show();studio=AIStudio(win);studio.show()
            models=studio.pages['models'];models.task.setCurrentIndex(models.task.findData('code'))
            print('Checking installed-model recommendations',flush=True)
            started=time.monotonic();models.refresh();wait_for(lambda:not models.busy)
            assert models.rows,models.status.text()
            results['recommendation']={'elapsed_s':time.monotonic()-started,
                'recommended':models.rows[0]['name'],'candidates':len(models.rows)}
            models.apply()  # Only the temporary config is changed.
            review_model=Settings.read().model
            config_manager._patch_config(ollama_model=selected.model)
            speech_dictionary.save([{'term':'Brave','recognized':'brave','pronunciation':'Breyv'},
                                    {'term':'Ali','recognized':'Allie','pronunciation':'Ali'},
                                    {'term':'Ali','recognized':'Alley','pronunciation':'Ali'}])
            results['dictionary']={'recognition':speech_dictionary.correct('brave project with allie and alley'),
                                   'pronunciation':speech_dictionary.pronounce('Brave project')}
            (root/'budget-report.txt').write_text('Synthetic budget 42.',encoding='utf-8')
            offline_desktop.save(True,root)
            results['file_search']=offline_desktop.search(root,'budget',threading.Event())
            runtime=LocalChat(win);win._local_chat=runtime
            print('Checking local tool calls',flush=True)
            win._capabilities.policy['mode']='smart'
            with patch('brave_offline_actions.ask_permission',return_value=False):
                started=time.monotonic()
                runtime.submit('Use find_local_files to find filenames containing budget in the allowed folder. State the found filename.',[])
                wait_for(lambda:runtime.last_request is not None and not runtime.busy)
                assert runtime.history and 'budget-report.txt' in runtime.history[-1]['content'],{
                    'metrics':runtime.last_request,'history':runtime.history}
                results['offline_chat']={'elapsed_s':time.monotonic()-started,'answer':runtime.history[-1]['content'],
                                         'metrics':runtime.last_request}
            config_manager._patch_config(ollama_model=review_model)
            code=root/'example.py';code.write_text('def divide():\n    return 10 / 0\n',encoding='utf-8')
            print('Checking read-only code analysis',flush=True)
            before=code.read_bytes();review=studio.pages['review'];review.path.setText(str(code))
            started=time.monotonic();review.review();wait_for(lambda:not review.busy)
            assert review.answer,review.status.text();assert code.read_bytes()==before
            results['code_review']={'elapsed_s':time.monotonic()-started,'answer':review.answer,'source_unchanged':True}
            meeting=studio.pages['meeting']
            if args.audio:
                print('Checking long synthetic audio transcription',flush=True)
                assert (speech_model/'model.bin').is_file(),'Prepare a local Whisper model explicitly first.'
                audio=root/'synthetic-meeting.wav';synthesize(audio)
                with wave.open(str(audio)) as source:duration=source.getnframes()/source.getframerate()
                assert duration>30,duration
                started=time.monotonic()
                config_manager._patch_config(local_stt_path=str(speech_model))
                meeting.path.setText(str(audio));meeting.language.setCurrentIndex(meeting.language.findData('en'))
                meeting.transcribe();wait_for(lambda:not meeting.busy)
                transcript=meeting.transcript.toPlainText()
                assert transcript and '00:01:00' in transcript,meeting.status.text()
                results['transcription']={'elapsed_s':time.monotonic()-started,'audio_s':duration,'text':transcript}
            else:transcript='[00:00:00] The project budget is 42. Ali will send the report on Monday.'
            meeting.transcript.setPlainText(transcript)
            print('Checking meeting summary and action items',flush=True)
            started=time.monotonic();meeting.summarize();wait_for(lambda:not meeting.busy)
            assert meeting.answer,meeting.status.text()
            results['meeting']={'elapsed_s':time.monotonic()-started,'answer':meeting.answer}
            args.output.parent.mkdir(parents=True,exist_ok=True)
            studio.select_tab('meeting');QTest.qWait(150)
            studio.grab().save(str(args.output.with_suffix('.png')))
            studio.reject();runtime.shutdown();win.close();win.deleteLater();app.processEvents()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(results,ensure_ascii=True,indent=2),flush=True)


if __name__=='__main__':main()
