"""Local AI preferences and bounded, session-only visual context."""
from collections import OrderedDict
from core import workspace_store


def settings():
    raw = workspace_store.read('ai-extensions.json', {})
    if not isinstance(raw, dict): raw = {}
    return {'auto_route': raw.get('auto_route') is True,
            'remember_images': raw.get('remember_images', True) is True}


def save(**changes):
    value = settings()
    for key, state in changes.items():
        if key not in value or type(state) is not bool: raise ValueError('AI sozlamasi noto‘g‘ri.')
        value[key] = state
    workspace_store.write('ai-extensions.json', value)


class VisualContext:
    """Last successful image set per chat; no disk writes or cross-chat reuse."""
    def __init__(self): self.chats = OrderedDict();self.generation=0

    def put(self, chat_id, images, labels):
        if not images or len(images)>3 or sum(map(len, images))>24_000_000: return
        self.chats.pop(chat_id, None)
        self.chats[chat_id] = (list(images), list(labels))
        while len(self.chats)>4: self.chats.popitem(last=False)

    def get(self, chat_id):
        images, labels = self.chats.get(chat_id, ([], []))
        return list(images), list(labels)

    def clear(self, chat_id=None):
        self.generation+=1
        if chat_id is None: self.chats.clear()
        else: self.chats.pop(chat_id, None)
