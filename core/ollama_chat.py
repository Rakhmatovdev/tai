"""Bounded, local-only Ollama text transport. No tools, downloads or cloud fallback."""
from dataclasses import dataclass
import ipaddress
import json
from urllib.parse import urlsplit

import requests

from memory.config_manager import load_api_keys, _patch_config
from core.ollama_model import model_info, require_chat, request_thinking, thinking_choice


PROFILES = {
    'economy': {'num_ctx': 2048, 'num_predict': 256, 'keep_alive': 0, 'chars': 1200},
    'balanced': {'num_ctx': 4096, 'num_predict': 512, 'keep_alive': '5m', 'chars': 2800},
    'quality': {'num_ctx': 8192, 'num_predict': 1024, 'keep_alive': '10m', 'chars': 6000},
}


def model_catalog(data):
    """Normalize local inventory for both the transport and the model picker."""
    if not isinstance(data, dict) or not isinstance(data.get('models'), list):
        raise ValueError('Ollama noto‘g‘ri javob qaytardi. Qayta urinib ko‘ring.')
    rows, seen = [], set()
    for raw in data['models']:
        if not isinstance(raw, dict) or raw.get('remote_host') or raw.get('remote_model'):
            continue
        try:
            name = local_model(raw.get('name'))
        except ValueError:
            continue
        if name in seen:
            continue
        seen.add(name)
        details = raw.get('details') if isinstance(raw.get('details'), dict) else {}
        size = raw.get('size', 0)
        rows.append({'name': name, 'size': size if type(size) is int and size >= 0 else 0,
                     'parameters': str(details.get('parameter_size') or '')[:40],
                     'quantization': str(details.get('quantization_level') or '')[:40]})
    return rows


def model_present(name, names):
    return name in names or (':' not in name and name + ':latest' in names)


def provider(config=None):
    config = load_api_keys() if config is None else config
    if not isinstance(config, dict):
        config = {}
    return 'ollama' if config.get('chat_provider') == 'ollama' else 'gemini'


def local_url(value):
    """Keep offline traffic on loopback, including checks and redirects."""
    if not isinstance(value, str):
        raise ValueError('Ollama manzili lokal bo‘lishi kerak.')
    try:
        url = urlsplit(value.strip())
        host = url.hostname
        valid = host == 'localhost' or ipaddress.ip_address(host).is_loopback
        port = url.port
    except (ValueError, TypeError):
        raise ValueError('Ollama manzili lokal bo‘lishi kerak.') from None
    if (not valid or url.scheme != 'http' or url.username is not None or
            url.password is not None or url.path not in ('', '/') or url.query or url.fragment):
        raise ValueError('Ollama manzili lokal bo‘lishi kerak.')
    if port is not None and not 1 <= port <= 65535:
        raise ValueError('Ollama manzili lokal bo‘lishi kerak.')
    return value.strip().rstrip('/')


def local_model(value):
    if (not isinstance(value, str) or not value.strip() or len(value) > 200 or
            any(c.isspace() for c in value) or ':cloud' in value.lower() or
            any(c in value for c in ('?', '#', '\\'))):
        raise ValueError('Lokal model nomini kiriting.')
    return value.strip()


@dataclass(frozen=True)
class Settings:
    url: str = 'http://localhost:11434'
    model: str = 'llama3.2'
    profile: str = 'balanced'
    autostart: bool = True
    thinking: str = 'off'

    @classmethod
    def read(cls):
        cfg = load_api_keys()
        if not isinstance(cfg, dict):
            cfg = {}
        raw_profile = cfg.get('ollama_profile', 'auto')
        profile = raw_profile if isinstance(raw_profile, str) and raw_profile in ('auto', *PROFILES) else 'balanced'
        return cls(local_url(cfg.get('ollama_url', cls.url)),
                   local_model(cfg.get('ollama_model', cfg.get('llm_model', cls.model))),
                   profile, cfg.get('ollama_autostart', True) is True,
                   cfg.get('ollama_thinking', 'off') if thinking_choice(cfg.get('ollama_thinking', 'off')) else 'off')

    def save(self, selected_provider):
        url, model = local_url(self.url), local_model(self.model)
        if (self.profile not in ('auto', *PROFILES) or selected_provider not in ('gemini', 'ollama')
                or not thinking_choice(self.thinking)):
            raise ValueError('Lokal model nomini kiriting.')
        _patch_config(chat_provider=selected_provider, ollama_url=url,
                      ollama_model=model, ollama_profile=self.profile, ollama_autostart=self.autostart,
                      ollama_thinking=self.thinking)


def chat_payload(settings, messages, info):
    require_chat(info)
    profile = PROFILES[settings.profile]
    options = {key: profile[key] for key in ('num_ctx', 'num_predict')}
    if info.get('context_length'):
        options['num_ctx'] = min(options['num_ctx'], info['context_length'])
    payload = {'model': settings.model, 'messages': messages, 'stream': True,
               'keep_alive': profile['keep_alive'], 'options': options}
    thinking = request_thinking(settings.thinking, info)
    if thinking is not None:
        payload['think'] = thinking
    return payload


def bounded_messages(history, text, profile, lang='uz'):
    limit = PROFILES[profile]['chars']
    if len(text) > limit:
        raise ValueError('Xabar juda uzun. Uni qisqartiring yoki Sifat profilini tanlang.')
    system = ('You are Brave, a helpful local text assistant. Reply in the user’s language '
              f'(interface language: {lang}). You have no tools, browser, microphone or file access. '
              'Do not claim to perform actions. Be concise and accurate.')
    # Keep complete exchanges. The transcript in SQLite remains untouched.
    budget = limit - len(text)
    turns = []
    for index in range(len(history)-2, -1, -2):
        pair = history[index:index+2]
        if len(pair) != 2 or pair[0]['role'] != 'user' or pair[1]['role'] != 'assistant':
            continue
        size = sum(len(m['content']) for m in pair)
        if size > budget or len(turns) >= 20:
            break
        budget -= size
        turns[0:0] = pair
    return [{'role': 'system', 'content': system}, *turns, {'role': 'user', 'content': text}]


class OllamaClient:
    def __init__(self, settings):
        self.settings = settings
        local_url(settings.url)
        local_model(settings.model)
        self.session = requests.Session()
        self.session.trust_env = False  # Local requests must not use HTTP proxies.
        self.response = None
        self.info = model_info({})

    def close(self):
        try:
            if self.response is not None:
                self.response.close()
            self.session.close()
        except (OSError, ValueError):
            pass

    def request(self, path, payload=None, stream=False):
        try:
            response = self.session.request('GET' if payload is None else 'POST',
                self.settings.url + path, json=payload, stream=stream,
                timeout=(3, 120 if stream else 8), allow_redirects=False)
            if response.is_redirect:
                response.close()
                raise ValueError('Ollama lokal manzildan boshqa joyga yo‘naltirdi.')
            response.raise_for_status()
            return response
        except requests.exceptions.ConnectionError:
            raise RuntimeError('Ollama ishlamayapti. Ollama ilovasini yoki ollama serve buyrug‘ini ishga tushiring.') from None
        except requests.exceptions.Timeout:
            raise RuntimeError('Ollama javob vaqti tugadi. Yengilroq model yoki Tejamkor profilini tanlang.') from None
        except requests.exceptions.HTTPError as exc:
            code = exc.response.status_code
            exc.response.close()
            raise RuntimeError('Model topilmadi. Avval uni Ollama orqali yuklang.' if code == 404 else
                               f'Ollama HTTP {code}. Model va xotira holatini tekshiring.') from None

    def models(self):
        return [row['name'] for row in self.catalog()]

    def catalog(self):
        with self.request('/api/tags') as response:
            return model_catalog(response.json())

    def verify(self):
        names = self.models()
        name = self.settings.model
        if not model_present(name, names):
            raise ValueError('Model topilmadi. Avval uni Ollama orqali yuklang.')
        with self.request('/api/show', {'model': name}) as response:
            self.info = model_info(response.json())
            require_chat(self.info)
        return names

    def describe(self):
        with self.request('/api/show', {'model': self.settings.model}) as response:
            return model_info(response.json())

    def stream(self, messages, cancelled):
        if cancelled.is_set():
            return
        self.verify()
        if cancelled.is_set():
            return
        settings = self.settings
        if settings.profile == 'auto':
            from core.ollama_resources import AutoProfile, sample_resources
            settings = AutoProfile().resolve(settings, sample_resources())
        payload = chat_payload(settings, messages, self.info)
        # Ollama chooses CPU/GPU placement; do not force all layers into VRAM.
        with self.request('/api/chat', payload, stream=True) as response:
            self.response = response
            done = False
            for raw in response.iter_lines(chunk_size=1):
                if cancelled.is_set():
                    return
                if not raw:
                    continue
                data = json.loads(raw)
                if data.get('error'):
                    raise RuntimeError('Ollama javob bera olmadi. Model va bo‘sh xotirani tekshiring.')
                text = data.get('message', {}).get('content', '')
                if text:
                    yield text
                if data.get('done'):
                    done = True
                    break
            if not done and not cancelled.is_set():
                raise RuntimeError('Ollama javobi uzildi. Qayta urinib ko‘ring.')

    def unload(self):
        with self.request('/api/generate', {'model': self.settings.model, 'keep_alive': 0,
                                             'stream': False}):
            pass
