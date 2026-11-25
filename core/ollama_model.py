"""Small, validated model metadata shared by both local transports and settings."""
import re


def thinking_choice(value):
    return (isinstance(value, str) and
            re.fullmatch(r'[a-z][a-z0-9_-]{0,31}', value) is not None)


def model_info(data):
    if not isinstance(data, dict):
        raise ValueError('Ollama noto‘g‘ri javob qaytardi. Qayta urinib ko‘ring.')
    if data.get('remote_host') or data.get('remote_model'):
        raise ValueError('Offline rejim uchun lokal model tanlang.')
    raw = data.get('capabilities')
    capabilities = None
    if isinstance(raw, list) and raw and all(thinking_choice(v) for v in raw):
        capabilities = list(dict.fromkeys(raw))
    thinking = data.get('thinking')
    values = []
    if isinstance(thinking, dict) and isinstance(thinking.get('values'), list):
        for value in thinking['values']:
            if (type(value) is bool or thinking_choice(value)) and value not in values:
                values.append(value)
    # A thinking capability alone does not tell us whether booleans or named
    # levels are accepted. Older servers keep their model default.
    metadata = data.get('model_info')
    limits = []
    if isinstance(metadata, dict):
        architecture = metadata.get('general.architecture')
        key = f'{architecture}.context_length'
        candidates = [metadata[key]] if key in metadata else [
            value for name, value in metadata.items()
            if isinstance(name, str) and name.endswith('.context_length')]
        limits = [v for v in candidates if type(v) is int and 0 < v <= 10**9]
    return {'capabilities': capabilities, 'thinking_values': values,
            'context_length': min(limits) if limits else None}


def require_chat(info):
    capabilities = info.get('capabilities')
    if capabilities and 'completion' not in capabilities:
        raise ValueError('Bu model matnli chatni qo‘llamaydi. Chat modelini tanlang.')


def request_thinking(choice, info):
    """None means omit the field, letting the model use its own default."""
    desired = {'off': False, 'on': True}.get(choice, choice)
    return desired if choice != 'auto' and desired in info.get('thinking_values', []) else None


def server_version(data):
    value = data.get('version') if isinstance(data, dict) else None
    return value if isinstance(value, str) and re.fullmatch(r'\d+\.\d+\.\d+[\w.+-]{0,40}', value) else None


def response_metrics(data):
    """Allowlist numeric statistics; never retain response text or server errors."""
    result = {}
    for key in ('total_duration', 'load_duration', 'prompt_eval_duration', 'eval_duration'):
        value = data.get(key)
        if type(value) is int and 0 <= value <= 10**18:
            result[key.removesuffix('_duration')+'_s'] = value/10**9
    for key in ('prompt_eval_count', 'eval_count'):
        value = data.get(key)
        if type(value) is int and 0 <= value <= 10**12:
            result[key] = value
    if result.get('eval_s', 0) > 0 and 'eval_count' in result:
        result['tokens_per_second'] = result['eval_count']/result['eval_s']
    reason = data.get('done_reason')
    if reason is not None:
        result['done_reason'] = reason if reason in ('stop', 'length', 'load', 'unload', 'tool_calls') else 'other'
    return result
