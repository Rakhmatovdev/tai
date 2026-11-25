"""Local Uzbek VITS speech. Only prepare_model() uses the network.

Voice: MuzaffarSharofitdinov/mms-tts-uzbek-girl-voice_cyrillic.
ONNX conversion: davron112/mms-tts-uzbek-girl-cyrl-onnx.
See docs/UZBEK_VOICE.md for provenance and model license notices.
"""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import threading
import unicodedata

VOICE_ID = 'brave:uzbek-female-vits'
VOICE_NAME = 'O‘zbekcha ayol ovozi · lokal AI'
REPOSITORY = 'davron112/mms-tts-uzbek-girl-cyrl-onnx'
REVISION = 'f81775a7279f9f5b8ec9904156abe75730af2182'
FILES = {
    'config.json': ('config.json', 'a8b184e8c765676ecb51d79148548f9cdc589deb3aacb00ead6e7e1e4cfc1eb3'),
    'vocab.json': ('vocab.json', '90a9d8dff52f09a5e004ceb0e2d7d89b74f1828470a7b0fbbc5fd98d196aed30'),
    'model.onnx': ('onnx/model.onnx', 'b26e607c4be29c6adf59eeb59a368be210a0352c53b7204af531cdb8d55ecd69'),
}
_cache = None
_inference_lock = threading.Lock()
_playback_lock = threading.Lock()
_download_lock = threading.Lock()


def model_directory():
    import os as _os
    import glob as _glob
    from core.workspace_store import directory
    # Asosiy joy (standart)
    primary = directory()/'tts-models'/'uzbek-female-vits'
    if all((primary/name).is_file() for name in FILES):
        return primary
    # Codex sandbox yoki boshqa LOCALAPPDATA variantlarini qidirish
    local = _os.environ.get('LOCALAPPDATA', '')
    # Codex / boshqa sandbox muhitlar pattern
    patterns = [
        _os.path.join(local, 'Packages', '*', 'LocalCache', 'Local', 'Brave',
                     'tts-models', 'uzbek-female-vits'),
        _os.path.join(_os.path.dirname(local), 'Local', 'Packages', '*',
                     'LocalCache', 'Local', 'Brave', 'tts-models', 'uzbek-female-vits'),
    ]
    for pattern in patterns:
        for match in _glob.glob(pattern):
            candidate = Path(match)
            if all((candidate/name).is_file() for name in FILES):
                return candidate
    return primary


def ready(path=None):
    root = Path(path) if path is not None else model_directory()
    return all((root/name).is_file() for name in FILES)


def _checksum(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def prepare_model(cancelled=None, progress=None):
    """Explicit one-time download; pinned files verified before atomic replacement."""
    import requests
    cancelled = cancelled or threading.Event()
    root = model_directory()
    root.mkdir(parents=True, exist_ok=True)
    with _download_lock, requests.Session() as session:
        for name, (remote, digest) in FILES.items():
            if cancelled.is_set():
                return None
            target = root/name
            if target.is_file() and _checksum(target) == digest:
                continue
            part = target.with_suffix(target.suffix+'.part')
            try:
                url = f'https://huggingface.co/{REPOSITORY}/resolve/{REVISION}/{remote}'
                with session.get(url, stream=True, timeout=(10, 60)) as response:
                    response.raise_for_status()
                    total = int(response.headers.get('Content-Length') or 0)
                    received = 0
                    with part.open('wb') as output:
                        for chunk in response.iter_content(1024*1024):
                            if cancelled.is_set():
                                return None
                            output.write(chunk)
                            received += len(chunk)
                            if progress:
                                progress(received, total)
                if _checksum(part) != digest:
                    raise ValueError('Ovoz modeli to‘liq yuklanmadi. Qayta yuklang.')
                part.replace(target)
            finally:
                part.unlink(missing_ok=True)
    return str(root)


_ONES = ('nol', 'bir', 'ikki', 'uch', 'to‘rt', 'besh', 'olti', 'yetti', 'sakkiz', 'to‘qqiz')
_TENS = ('', 'o‘n', 'yigirma', 'o‘ttiz', 'qirq', 'ellik', 'oltmish', 'yetmish', 'sakson', 'to‘qson')


def number_words(value):
    """Spell integers so digits absent from the voice vocabulary are not lost."""
    if len(value) > 12 or (len(value) > 1 and value.startswith('0')):
        return ' '.join(_ONES[int(digit)] for digit in value)
    number = int(value)
    if number == 0:
        return _ONES[0]
    words = []
    for scale, label in ((10**9, 'milliard'), (10**6, 'million'), (1000, 'ming')):
        count, number = divmod(number, scale)
        if count:
            words.extend((number_words(str(count)), label))
    hundreds, number = divmod(number, 100)
    if hundreds:
        words.extend((_ONES[hundreds], 'yuz'))
    tens, ones = divmod(number, 10)
    if tens:
        words.append(_TENS[tens])
    if ones:
        words.append(_ONES[ones])
    return ' '.join(words)


def plain_text(text):
    text = re.sub(r'```.*?```', ' ', str(text)[:12000], flags=re.S)
    text = re.sub(r'(?<=[oOgG])[‘’ʻʼʹ`´ʽ]', "'", text)
    text = re.sub(r'!?\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'https?://\S+|<[^>]*>', ' ', text)
    text = re.sub(r'[*_#`|>]', ' ', text)
    text = text.replace('%', ' foiz ').replace('+', ' plyus ').replace('=', ' teng ')
    text = re.sub(r'\d+', lambda match: ' '+number_words(match.group())+' ', text)
    return re.sub(r'[^\S\n]+', ' ', text).strip()


_PAIRS = {"o'": 'ў', "g'": 'ғ', 'sh': 'ш', 'ch': 'ч', 'yo': 'ё',
          'yu': 'ю', 'ya': 'я', 'ye': 'е', 'ts': 'тс'}
_LETTERS = dict(zip('abvgdjziklmnoprstufxqhy', 'абвгджзиклмнопрстуфхқҳй'))


def cyrillic(text):
    """Uzbek Latin to Cyrillic, accepting common keyboard apostrophes and mixed text."""
    text = unicodedata.normalize('NFKC', text).lower()
    text = re.sub('[‘’ʻʼʹ`´ʽ]', "'", text)
    result, index = [], 0
    while index < len(text):
        pair = text[index:index+2]
        if pair in _PAIRS:
            result.append(_PAIRS[pair]); index += 2
            continue
        char = text[index]
        if char == 'e':
            result.append('э' if index == 0 or not text[index-1].isalpha() else 'е')
        elif char == "'":
            result.append('ъ')
        elif char == 'ц':
            result.append('тс')
        else:
            result.append(_LETTERS.get(char, char))
        index += 1
    return ''.join(result)


def text_chunks(text, limit=180):
    for sentence in re.split(r'[.!?;:\n]+', plain_text(text)):
        words = sentence.split()
        chunk = ''
        for word in words:
            if chunk and len(chunk)+len(word)+1 > limit:
                yield chunk
                chunk = ''
            # Bound even malformed model output without spaces.
            while len(word) > limit:
                if chunk:
                    yield chunk; chunk = ''
                yield word[:limit]; word = word[limit:]
            chunk = (chunk+' '+word).strip()
        if chunk:
            yield chunk


@contextmanager
def _locked(lock, cancelled):
    from core.local_jobs import Cancelled
    while not lock.acquire(timeout=.05):
        if cancelled.is_set():
            raise Cancelled('Bekor qilindi.')
    try:
        if cancelled.is_set():
            raise Cancelled('Bekor qilindi.')
        yield
    finally:
        lock.release()


def _load(root):
    global _cache
    key = str(root.resolve())
    if _cache and _cache[0] == key:
        return _cache[1:]
    if not ready(root):
        raise ValueError('Avval o‘zbekcha ovoz modelini yuklang.')
    for name, (_, digest) in FILES.items():
        if _checksum(root/name) != digest:
            raise ValueError('Ovoz modeli buzilgan. Uni qayta yuklang.')
    import onnxruntime as ort
    config = json.loads((root/'config.json').read_text(encoding='utf-8'))
    vocab = json.loads((root/'vocab.json').read_text(encoding='utf-8'))
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(root/'model.onnx'), sess_options=options,
                                   providers=['CPUExecutionProvider'])
    _cache = (key, session, vocab, config['sampling_rate'])
    return _cache[1:]


def synthesize(text, cancelled, path=None, *, dialect=None):
    """Yield bounded float32 waveform chunks using verified local files only."""
    import numpy as np
    from core.local_jobs import gate
    if dialect and dialect != 'adabiy':
        from core.voice_style import apply_uzbek_dialect_text
        text = apply_uzbek_dialect_text(text, dialect)
    root = Path(path) if path is not None else model_directory()
    for chunk in text_chunks(text):
        if cancelled.is_set():
            return
        with gate.hold(cancelled), _locked(_inference_lock, cancelled):
            session, vocab, rate = _load(root)
            normalized = ''.join(char for char in cyrillic(chunk) if char in vocab).strip()
            if not normalized:
                continue
            tokens = np.zeros((1, len(normalized)*2+1), dtype=np.int64)
            tokens[0, 1::2] = [vocab[char] for char in normalized]
            inputs = {'input_ids': tokens, 'attention_mask': np.ones_like(tokens)}
            audio = session.run(None, inputs)[0].reshape(-1).astype('float32')
        if cancelled.is_set():
            return
        if not np.isfinite(audio).all() or len(audio) > rate*60:
            raise ValueError('Ovoz modeli noto‘g‘ri audio qaytardi.')
        yield np.clip(audio, -1, 1), rate


def speak(text, cancelled, on_amp=None, *, style=None):
    """Worker-only playback with lookahead prefetch and optional prosody/dialect styling."""
    if cancelled.is_set():
        return
    import queue as _queue
    import numpy as np
    import sounddevice as sd
    from core.audio_devices import resolve
    from core.voice_style import (
        apply_uzbek_dialect_text, is_neutral_dsp, load_voice_style,
        normalize_voice_style, pause_duration_seconds, transform_waveform,
    )
    from memory.config_manager import get_output_device

    active_style = normalize_voice_style(style if style is not None else load_voice_style())
    if active_style.get('phonetic_dialect_tts', True) and active_style.get('dialect', 'adabiy') != 'adabiy':
        text = apply_uzbek_dialect_text(text, active_style['dialect'])
    pause_sec = pause_duration_seconds(active_style)
    neutral = is_neutral_dsp(active_style)

    device = resolve(get_output_device(), 'output')
    stream = None
    stream_rate = None
    with _locked(_playback_lock, cancelled):
        q: _queue.Queue = _queue.Queue(maxsize=2)
        synth_err: list[BaseException] = []
        stop_prefetch = threading.Event()

        def _producer():
            try:
                for item in synthesize(text, cancelled):
                    if cancelled.is_set() or stop_prefetch.is_set():
                        break
                    while not (cancelled.is_set() or stop_prefetch.is_set()):
                        try:
                            q.put(item, timeout=0.05)
                            break
                        except _queue.Full:
                            continue
            except BaseException as exc:
                synth_err.append(exc)
            finally:
                while not stop_prefetch.is_set():
                    try:
                        q.put(None, timeout=0.05)
                        break
                    except _queue.Full:
                        try:
                            q.get_nowait()
                        except _queue.Empty:
                            pass

        prod_thread = threading.Thread(target=_producer, daemon=True, name='uzbek-tts-prefetch')
        prod_thread.start()
        try:
            while True:
                if cancelled.is_set():
                    break
                try:
                    item = q.get(timeout=0.05)
                except _queue.Empty:
                    if not prod_thread.is_alive():
                        break
                    continue
                if item is None:
                    break
                audio, rate = item
                if cancelled.is_set():
                    break
                if not neutral:
                    audio = transform_waveform(audio, rate, active_style)
                if stream is None or stream_rate != rate:
                    if stream is not None:
                        try: stream.close()
                        except Exception: pass
                    stream = sd.OutputStream(samplerate=rate, channels=1, dtype='float32', device=device)
                    stream.start()
                    stream_rate = rate
                audio = np.concatenate((audio, np.zeros(int(rate * pause_sec), dtype='float32')))
                chunk_size = max(1, rate // 20)
                for start in range(0, len(audio), chunk_size):
                    if cancelled.is_set():
                        if stream is not None:
                            try: stream.abort()
                            except Exception: pass
                        return
                    block = audio[start:start+chunk_size]
                    if on_amp and len(block):
                        try:
                            rms = float(np.sqrt(np.mean(block * block)))
                            on_amp(min(1.0, rms * 8.0))
                        except Exception:
                            pass
                    stream.write(block.reshape(-1, 1))
            if synth_err and not cancelled.is_set():
                raise synth_err[0]
        finally:
            stop_prefetch.set()
            if stream is not None:
                try: stream.close()
                except Exception: pass
            if on_amp:
                try: on_amp(0.0)
                except Exception: pass


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Prepare the offline Uzbek voice once.')
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        print(prepare_model())
