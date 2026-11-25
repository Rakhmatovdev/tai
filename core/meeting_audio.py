"""Stream long user-selected audio into bounded local speech-recognition chunks."""
from pathlib import Path

AUDIO = {'.wav','.mp3','.m4a','.flac','.ogg','.aac','.mp4','.webm'}
MAX_SECONDS = 2*60*60
CHUNK_SECONDS = 30


def audio_chunks(path, cancelled, allowed=lambda:True):
    if cancelled.is_set():return
    import av
    import numpy as np
    path = Path(path).resolve()
    if path.suffix.lower() not in AUDIO or not path.is_file() or path.stat().st_size>500_000_000:
        raise ValueError('Audio fayli qo‘llanmaydi yoki 500 MB dan katta.')
    with av.open(str(path)) as container:
        if not container.streams.audio: raise ValueError('Faylda audio oqimi topilmadi.')
        if container.duration and container.duration/av.time_base>MAX_SECONDS:
            raise ValueError('Audio 2 soatdan oshmasin.')
        resampler = av.AudioResampler(format='s16',layout='mono',rate=16000)
        blocks, count, offset = [], 0, 0
        def frames():
            for frame in container.decode(audio=0):
                if cancelled.is_set(): return
                if not allowed(): raise ValueError('Fayl ruxsati o‘chiq.')
                yield from resampler.resample(frame)
            if not cancelled.is_set(): yield from resampler.resample(None)
        for frame in frames():
            if cancelled.is_set(): return
            data = frame.to_ndarray().reshape(-1).astype('float32')/32768.0
            position = 0
            while position<len(data):
                take = min(len(data)-position, CHUNK_SECONDS*16000-count)
                blocks.append(data[position:position+take]); count += take; position += take
                if offset+count>MAX_SECONDS*16000: raise ValueError('Audio 2 soatdan oshmasin.')
                if count==CHUNK_SECONDS*16000:
                    yield offset/16000, np.concatenate(blocks)
                    offset += count; blocks=[]; count=0
        if blocks and not cancelled.is_set(): yield offset/16000, np.concatenate(blocks)


def transcribe_file(path, model_path, language, cancelled, progress=lambda text: None, allowed=lambda:True, *, diarize=False,quality='fast'):
    from core.offline_voice import transcribe
    rows, size = [], 0
    from core.speaker_labels import SpeakerLabels
    speakers=SpeakerLabels() if diarize else None
    if not allowed(): raise ValueError('Fayl ruxsati o‘chiq.')
    for offset, audio in audio_chunks(path, cancelled,allowed):
        if cancelled.is_set(): return ''
        from core.live_meeting import transcribe_chunk
        options={'quality':quality} if quality!='fast' else {}
        chunk_rows=transcribe_chunk(audio,offset,model_path,language,cancelled,speakers,**options)
        if not allowed(): raise ValueError('Fayl ruxsati o‘chiq.')
        if cancelled.is_set(): return ''
        if chunk_rows:
            size += sum(map(len,chunk_rows))
            if size>160_000: raise ValueError('Transkript juda katta. Audioni qismlarga ajrating.')
            rows.extend(chunk_rows)
            progress('\n'.join(rows))
    if not rows: raise ValueError('Audiodan nutq topilmadi.')
    return '\n'.join(rows)
