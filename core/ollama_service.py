"""Reuse a local Ollama service, or start the installed CLI once on loopback."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

import requests

_startup_lock = threading.Lock()
_process = None


def executable():
    candidates = []
    if sys.platform == 'win32':
        for root, suffix in [('LOCALAPPDATA', 'Programs/Ollama/ollama.exe'),
                             ('ProgramFiles', 'Ollama/ollama.exe')]:
            if os.environ.get(root):
                candidates.append(Path(os.environ[root])/suffix)
        if os.environ.get('USERPROFILE'):
            candidates.append(Path(os.environ['USERPROFILE'])/'AppData/Local/Programs/Ollama/ollama.exe')
        if os.environ.get('ProgramFiles(x86)'):
            candidates.append(Path(os.environ['ProgramFiles(x86)'])/'Ollama/ollama.exe')
    else:
        candidates.extend(Path(p) for p in ('/usr/local/bin/ollama', '/usr/bin/ollama', '/opt/homebrew/bin/ollama'))
    found = shutil.which('ollama')
    if found:
        candidates.append(Path(found))
    return next((str(p.resolve()) for p in candidates if p.is_file()), None)


def can_start(url):
    from core.ollama_chat import local_url
    parsed = urlsplit(local_url(url))
    # Custom servers are user-managed; never launch a second server on their port.
    return parsed.hostname in ('localhost', '127.0.0.1') and parsed.port == 11434


def launch_server():
    binary = executable()
    if not binary:
        raise RuntimeError('Ollama topilmadi. Avval Ollama dasturini o‘rnating.')
    env = dict(os.environ, OLLAMA_HOST='127.0.0.1:11434', OLLAMA_NO_CLOUD='1')
    options = dict(env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if sys.platform == 'win32':
        options['creationflags'] = subprocess.CREATE_NO_WINDOW
    return subprocess.Popen([binary, 'serve'], **options)


def health(session, url):
    try:
        with session.get(url+'/api/tags', timeout=(.7, .8), allow_redirects=False) as response:
            if response.is_redirect or response.status_code != 200:
                raise RuntimeError('Ollama lokal serverini tekshiring. Avtomatik ishga tushirish bajarilmadi.')
            data = response.json()
            if not isinstance(data, dict) or not isinstance(data.get('models'), list):
                raise RuntimeError('Ollama lokal serverini tekshiring. Avtomatik ishga tushirish bajarilmadi.')
            return True
    except (requests.ConnectionError, requests.Timeout):
        return False
    except ValueError:
        raise RuntimeError('Ollama noto‘g‘ri javob qaytardi. Qayta urinib ko‘ring.') from None


def ensure_server(url, enabled=True, cancelled=None, stage=None, timeout=15):
    """Worker-only, bounded and cancellable. Never download models or restart services."""
    from core.ollama_chat import local_url
    url = local_url(url)
    cancelled = cancelled or threading.Event()
    if cancelled.is_set():
        return False
    with requests.Session() as session:
        session.trust_env = False
        if health(session, url):
            return not cancelled.is_set()
        if cancelled.is_set():
            return False
        if not enabled or not can_start(url):
            raise RuntimeError('Ollama ishlamayapti. Ollama ilovasini yoki ollama serve buyrug‘ini ishga tushiring.')
        # One launcher for simultaneous startup, chat and settings requests.
        deadline = time.monotonic()+timeout
        while not _startup_lock.acquire(timeout=.1):
            if cancelled.is_set():
                return False
            if time.monotonic() >= deadline:
                raise RuntimeError('Ollama ishga tushishi kutilgan vaqtda tugamadi. Qayta urinib ko‘ring.')
        try:
            if cancelled.is_set():
                return False
            if health(session, url):
                return not cancelled.is_set()
            if cancelled.is_set():
                return False
            global _process
            if stage:
                stage('starting')
            if cancelled.is_set():
                return False
            if _process is None or _process.poll() is not None:
                try:
                    _process = launch_server()
                except OSError:
                    raise RuntimeError('Ollama’ni ishga tushirib bo‘lmadi. Dastur yo‘lini va ruxsatlarni tekshiring.') from None
            while time.monotonic() < deadline:
                if cancelled.wait(.25):
                    return False
                if health(session, url):
                    return not cancelled.is_set()
                if _process.poll() is not None:
                    raise RuntimeError('Ollama ishga tushmadi. Ollama dasturini ochib qayta urinib ko‘ring.')
            raise RuntimeError('Ollama ishga tushishi kutilgan vaqtda tugamadi. Qayta urinib ko‘ring.')
        finally:
            _startup_lock.release()
