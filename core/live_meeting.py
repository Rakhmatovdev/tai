"""Bounded microphone producer and local transcription consumer, no saved audio."""
import queue
import threading
import time


def transcribe_chunk(audio, offset, model_path, language, cancelled, speakers=None, *, quality='fast',context=''):
    from core.offline_voice import transcribe
    spans=speakers.segments(audio,cancelled) if speakers else [(0,len(audio),None)]
    rows=[]
    for start,end,label in spans:
        if cancelled.is_set(): return []
        options={'quality':quality,'context':context} if quality!='fast' or context else {}
        text=transcribe(audio[start:end],model_path,language,cancelled,**options)
        if text:
            seconds=int(offset+start/16000)
            speaker=f' Speaker {label}:' if label is not None else ''
            rows.append(f'[{seconds//3600:02}:{seconds//60%60:02}:{seconds%60:02}]{speaker} {text}')
    return rows


def run(model_path,language,stop,cancelled,allowed,progress=lambda text:None,*,diarize=False,stream_factory=None,quality='fast'):
    import numpy as np
    import sounddevice as sd
    from core.audio_devices import resolve
    from memory.config_manager import get_input_device
    if not allowed(): raise ValueError('Mikrofon ruxsati o‘chiq.')
    if not (__import__('pathlib').Path(model_path)/'model.bin').is_file():
        raise ValueError('Avval offline nutq modelini tayyorlang.')
    from core.speaker_labels import SpeakerLabels
    speakers=SpeakerLabels() if diarize else None
    blocks=queue.Queue(maxsize=120)  # sixty seconds, 0.5 s per block
    ended=threading.Event(); failure=[]
    def callback(data,frames,_time,status):
        if stop.is_set() or cancelled.is_set() or not allowed(): return
        if status: failure.append('Mikrofon oqimida uzilish bo‘ldi.');stop.set();return
        try: blocks.put_nowait(data[:,0].copy())
        except queue.Full: failure.append('Nutq tanish audiodan ortda qoldi. Yozuvni qayta boshlang.');stop.set()
    def capture():
        try:
            factory=stream_factory or sd.InputStream
            with factory(samplerate=16000,channels=1,dtype='float32',blocksize=8000,
                         device=resolve(get_input_device(),'input'),callback=callback):
                deadline=time.monotonic()+2*60*60
                while not stop.is_set() and not cancelled.is_set() and allowed() and time.monotonic()<deadline:
                    stop.wait(.05)
        except Exception as error: failure.append(str(error));stop.set()
        finally: ended.set()
    producer=threading.Thread(target=capture,daemon=True,name='brave-meeting-microphone');producer.start()
    pending=[];count=offset=0;rows=[]
    try:
        while not cancelled.is_set():
            if not allowed():raise ValueError('Mikrofon ruxsati o‘chiq.')
            try: block=blocks.get(timeout=.1);pending.append(block);count+=len(block)
            except queue.Empty:
                if not ended.is_set():continue
            # Emit at a pause after 3 s, wait up to 12 s through a spoken phrase.
            # Legacy fast mode keeps its bounded 8 s chunks.
            at_end=ended.is_set() and blocks.empty()
            pause=bool(pending) and float(np.sqrt(np.mean(pending[-1]**2)))<.008
            ready=(count>=16000*8 if quality=='fast' else count>=16000*12 or (count>=16000*3 and pause))
            if ready or (at_end and count):
                audio=np.concatenate(pending);pending=[];count=0
                options={'quality':quality} if quality!='fast' else {}
                rows.extend(transcribe_chunk(audio,offset,model_path,language,cancelled,speakers,**options))
                offset+=len(audio)/16000
                text='\n'.join(rows)
                if len(text)>160_000:raise ValueError('Transkript chegarasiga yetdi.')
                progress(text)
            if ended.is_set() and blocks.empty():break
        if cancelled.is_set():return ''
        if not allowed():raise ValueError('Mikrofon ruxsati o‘chiq.')
        if failure:raise ValueError(failure[0])
        return '\n'.join(rows)
    finally:stop.set();producer.join(timeout=2)
