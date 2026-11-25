"""Opt-in local speech. Inference never downloads models or contacts a cloud."""
from pathlib import Path
import re
import threading
import time

_models={}
_lock=threading.Lock()


def model_directory(size='base'):
    if size not in ('tiny','base','small','medium'):raise ValueError('Nutq modeli noto‘g‘ri.')
    from core.workspace_store import directory
    primary = directory()/'speech-models'/size
    if (primary/'model.bin').is_file():
        return primary
    import os, glob
    local = os.environ.get('LOCALAPPDATA', '')
    patterns = [
        os.path.join(local, 'Packages', '*', 'LocalCache', 'Local', 'Brave', 'speech-models', size),
        os.path.join(os.path.dirname(local), 'Local', 'Packages', '*', 'LocalCache', 'Local', 'Brave', 'speech-models', size),
    ]
    for pattern in patterns:
        for match in glob.glob(pattern):
            candidate = Path(match)
            if (candidate/'model.bin').is_file():
                return candidate
    return primary


def prepare_model(size='base'):
    # Only called by the explicit preparation action, never by transcription.
    from faster_whisper.utils import download_model
    return download_model(size,output_dir=str(model_directory(size)))


def transcribe(audio,path,language,cancelled,partial=None,*,quality='fast',context=''):
    path=Path(path).expanduser().resolve()
    if not (path/'model.bin').is_file():
        # Fallback to model_directory resolution
        resolved = model_directory()
        if (resolved/'model.bin').is_file():
            path = resolved
        else:
            raise ValueError('Avval offline ovoz modelini tayyorlang yoki model papkasini tanlang.')
    import os
    from faster_whisper import WhisperModel
    from core.local_jobs import gate
    with gate.hold(cancelled), _lock:
        if cancelled.is_set():return ''
        key=str(path)
        threads = min(8, max(2, (os.cpu_count() or 4) - 1))
        if key not in _models:
            _models.clear()
            _models[key]=WhisperModel(key,device='cpu',compute_type='int8',local_files_only=True,cpu_threads=threads)
        if cancelled.is_set():return ''
        # beam_size=1 provides 2-3x speedup on CPU with greedy decoding, ideal for real-time conversation
        from core import speech_dictionary
        dictionary = speech_dictionary.load()
        prompt = (speech_dictionary.hints(dictionary)+' '+str(context)[-250:]).strip()
        segments,_=_models[key].transcribe(audio,language=None if language=='auto' else language,
            beam_size=5 if quality=='accurate' else 1,condition_on_previous_text=False,vad_filter=True,
            **({'initial_prompt':prompt} if prompt else {}))
        result=[]
        for segment in segments:
            if cancelled.is_set():return ''
            result.append(segment.text)
            if partial:partial(speech_dictionary.correct(' '.join(result).strip(), dictionary))
        return speech_dictionary.correct(' '.join(result).strip(), dictionary)


def capture(stop,cancelled,allowed,preview=None,auto_stop=False,on_amp=None,silence_limit=1.2):
    import numpy as np
    import sounddevice as sd
    from core.audio_devices import resolve
    from memory.config_manager import get_input_device
    frames=[];count=0
    def callback(data,n,time_info,status):
        nonlocal count
        if stop.is_set() or cancelled.is_set() or not allowed():return
        if count+n<=16000*30:
            mono = data[:,0].copy()
            frames.append(mono);count+=n
            if on_amp:
                try:
                    rms = float(np.sqrt(np.mean(mono*mono)))
                    on_amp(min(1.0, rms * 14.0))
                except Exception:
                    pass
        else:stop.set()
    device=resolve(get_input_device(),'input')
    with sd.InputStream(samplerate=16000,channels=1,dtype='float32',device=device,callback=callback):
        end=time.monotonic()+30
        last_preview=0;heard=0;silence=0;seen=0
        while not stop.is_set() and not cancelled.is_set() and allowed() and time.monotonic()<end:
            now=time.monotonic()
            current=list(frames)
            if auto_stop and len(current)>seen:
                recent=np.concatenate(current[seen:]);seen=len(current)
                duration=len(recent)/16000
                if float(np.sqrt(np.mean(recent*recent)))>.007:heard+=duration;silence=0
                else:silence+=duration
                if heard>.35 and silence>=silence_limit:stop.set()
                elif heard==0 and silence>=20.0:stop.set()
            if preview and current and now-last_preview>3 and count>16000:
                last_preview=now;preview(np.concatenate(current)[-16000*12:].copy())
            stop.wait(.04)
    if on_amp:
        try:on_amp(0.0)
        except Exception:pass
    if cancelled.is_set() or not allowed():return None
    return np.concatenate(frames) if frames else np.zeros(0,dtype='float32')


def word_error_rate(reference,hypothesis):
    def words(text):return re.findall(r"[\w‘’']+",text.casefold().replace('‘',"'").replace('’',"'"))
    expected,actual=words(reference),words(hypothesis)
    if not expected:raise ValueError('Kutilgan matnni kiriting.')
    previous=list(range(len(actual)+1))
    for i,left in enumerate(expected,1):
        current=[i]
        for j,right in enumerate(actual,1):current.append(min(current[-1]+1,previous[j]+1,previous[j-1]+(left!=right)))
        previous=current
    return previous[-1]/len(expected)


def speak(text,cancelled,voice_id='',on_amp=None,*,style=None):
    if cancelled.is_set():return
    from core.speech_dictionary import pronounce
    text = pronounce(text)
    from core import uzbek_tts
    if voice_id==uzbek_tts.VOICE_ID:
        if on_amp is None and style is None:
            return uzbek_tts.speak(text,cancelled)
        kwargs = {}
        if on_amp is not None:
            kwargs['on_amp'] = on_amp
        if style is not None:
            kwargs['style'] = style
        return uzbek_tts.speak(text,cancelled,**kwargs)
    import platform
    if platform.system()!='Windows':
        raise RuntimeError('Bu qurilmada lokal tizim ovozi mavjud emas.')
    from core.voice_style import GENDER_MAP, SPEED_MAP, EMOTION_MAP, load_voice_style, normalize_voice_style
    active_style = normalize_voice_style(style if style is not None else load_voice_style())
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    try:
        voice=win32com.client.Dispatch('SAPI.SpVoice')
        if voice_id:
            for item in voice.GetVoices():
                if item.Id==voice_id:voice.Voice=item;break
        else:
            sapi_gender = GENDER_MAP[active_style['gender']].sapi_gender
            try:
                matched = voice.GetVoices(f'Gender={sapi_gender}')
                if matched.Count:
                    voice.Voice = matched.Item(0)
            except Exception:
                pass
        try:
            pace = SPEED_MAP[active_style['speed']]
            emo = EMOTION_MAP[active_style['emotion']]
            rate_offset = 1 if emo.speed_mult > 1.03 else (-1 if emo.speed_mult < 0.96 else 0)
            voice.Rate = max(-10, min(10, pace.sapi_rate + rate_offset))
            voice.Volume = 88 if active_style['emotion'] in ('gentle', 'loving') else 100
        except Exception:
            pass
        text=re.sub(r'```.*?```','',text,flags=re.S)
        text=re.sub(r'\[([^\]]+)\]\([^)]*\)',r'\1',text)
        # SPF_ASYNC | SPF_IS_NOT_XML: model output is never interpreted as SSML.
        if cancelled.is_set():return
        voice.Speak(text[:12000],17)
        while not voice.WaitUntilDone(50):
            if cancelled.is_set():voice.Speak('',19);break
    finally:
        pythoncom.CoUninitialize()


def voices():
    from core import uzbek_tts
    rows=[(uzbek_tts.VOICE_NAME,uzbek_tts.VOICE_ID)]
    import platform
    if platform.system()!='Windows':return rows
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    try:
        return rows+[(item.GetDescription(),item.Id) for item in win32com.client.Dispatch('SAPI.SpVoice').GetVoices()]
    finally:pythoncom.CoUninitialize()
