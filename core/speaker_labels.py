"""Offline anonymous speaker labels using WeSpeaker embeddings (CC BY 4.0).

No identity recognition. Labels are estimates, especially for short/overlapping speech.
Model attribution: https://huggingface.co/Wespeaker/wespeaker-voxceleb-resnet34-LM
"""
import hashlib
from pathlib import Path
import uuid
from core import workspace_store

REVISION = 'f0c48c298fd835726c27956a5d617bad7115627e'
SHA256 = '7bb2f06e9df17cdf1ef14ee8a15ab08ed28e8d0ef5054ee135741560df2ec068'
URL = f'https://huggingface.co/Wespeaker/wespeaker-voxceleb-resnet34-LM/resolve/{REVISION}/voxceleb_resnet34_LM.onnx'


def model_path(): return workspace_store.directory()/'speaker-models'/'wespeaker-resnet34-lm.onnx'


def prepare(cancelled, progress=lambda text:None, allowed=lambda:True):
    """Only the explicit preparation button calls this network operation."""
    import requests
    if cancelled.is_set() or not allowed():raise RuntimeError('Bekor qilindi.')
    target = model_path(); target.parent.mkdir(parents=True,exist_ok=True)
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest()==SHA256: return str(target)
    temporary = target.with_suffix('.'+uuid.uuid4().hex+'.download')
    try:
        total=0; checksum=hashlib.sha256()
        with requests.get(URL, stream=True, timeout=(15,30)) as response:
            response.raise_for_status()
            with temporary.open('wb') as stream:
                for block in response.iter_content(256*1024):
                    if cancelled.is_set() or not allowed(): raise RuntimeError('Bekor qilindi.')
                    total+=len(block)
                    if total>30_000_000: raise ValueError('Model hajmi noto‘g‘ri.')
                    stream.write(block);checksum.update(block);progress(f'{total/1e6:.1f}/26.5 MB')
        if checksum.hexdigest()!=SHA256: raise ValueError('Model tekshiruvdan o‘tmadi.')
        temporary.replace(target)
        return str(target)
    finally: temporary.unlink(missing_ok=True)


class SpeakerLabels:
    def __init__(self, threshold=.55, maximum=8):
        import onnxruntime as ort
        path=model_path()
        if not path.is_file(): raise ValueError('Avval gapiruvchi modelini tayyorlang (26.5 MB).')
        options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
        self.session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider'])
        self.threshold=threshold;self.maximum=maximum;self.centers=[];self.counts=[]

    def embedding(self, audio):
        import kaldi_native_fbank as knf
        import numpy as np
        opts=knf.FbankOptions();opts.mel_opts.num_bins=80
        opts.frame_opts.dither=0;opts.frame_opts.window_type='hamming'
        fbank=knf.OnlineFbank(opts)
        fbank.accept_waveform(16000,(np.asarray(audio,dtype=np.float32)*32768).tolist())
        fbank.input_finished()
        if fbank.num_frames_ready<20: return None
        feats=np.stack([fbank.get_frame(i) for i in range(fbank.num_frames_ready)])
        feats-=feats.mean(axis=0,keepdims=True)
        vector=self.session.run(None,{self.session.get_inputs()[0].name:feats[None].astype('float32')})[0].reshape(-1)
        norm=float(np.linalg.norm(vector))
        return vector/norm if norm>1e-8 else None

    def assign(self, vector):
        import numpy as np
        if vector is None: return '?'
        scores=[float(np.dot(vector,center)) for center in self.centers]
        best=int(np.argmax(scores)) if scores else -1
        if best<0 or (scores[best]<self.threshold and len(self.centers)<self.maximum):
            self.centers.append(vector.copy());self.counts.append(1);return str(len(self.centers))
        if scores[best]<self.threshold: return '?'
        mean=self.centers[best]*self.counts[best]+vector
        self.centers[best]=mean/np.linalg.norm(mean);self.counts[best]+=1
        return str(best+1)

    def segments(self,audio,cancelled):
        from faster_whisper.vad import get_speech_timestamps, VadOptions
        # Existing bundled Silero VAD, no network access.
        speech=get_speech_timestamps(audio,VadOptions(min_speech_duration_ms=250,min_silence_duration_ms=250))
        rows=[]
        for span in speech:
            for start in range(span['start'],span['end'],16000*3):
                if cancelled.is_set(): return []
                end=min(span['end'],start+16000*3)
                label=self.assign(self.embedding(audio[start:end]))
                if rows and rows[-1][2]==label and start-rows[-1][1]<16000*.5:
                    rows[-1]=(rows[-1][0],end,label)
                else:rows.append((start,end,label))
        return rows
