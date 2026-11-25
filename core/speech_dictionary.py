"""User-managed recognition hints and pronunciation aliases; no model training."""
import re
from core import workspace_store


def key(text):
    return ' '.join(text.casefold().translate(str.maketrans({'‘': "'", '’': "'", 'ʻ': "'", 'ʼ': "'"})).split())


def validate(rows):
    if not isinstance(rows, list) or len(rows) > 200:
        raise ValueError('Lug‘atda ko‘pi bilan 200 ta atama bo‘lishi mumkin.')
    result, aliases = [], {}
    for row in rows:
        if not isinstance(row, dict): raise ValueError('Lug‘at yozuvi noto‘g‘ri.')
        item = {name: str(row.get(name, '')).strip() for name in ('term', 'recognized', 'pronunciation')}
        if not item['term'] or any(len(v)>120 or '\n' in v or '\r' in v for v in item.values()):
            raise ValueError('Atama va talaffuz 120 belgidan oshmasin.')
        alias = key(item['recognized'] or item['term'])
        if not any(c.isalnum() for c in alias) or alias in aliases:
            raise ValueError('Tanilish varianti takrorlangan yoki noto‘g‘ri.')
        aliases[alias] = item['term']
        result.append(item)
    return result


def load():
    try: return validate(workspace_store.read('speech-dictionary.json', []))
    except ValueError: return []


def save(rows):
    workspace_store.write('speech-dictionary.json', validate(rows))


def hints(rows=None):
    rows = load() if rows is None else rows
    return ', '.join(dict.fromkeys(row['term'] for row in rows))[:500]


def substitute(text, mapping):
    if not mapping: return text
    def pattern(value):
        return ''.join("['‘’ʻʼ]" if c=="'" else r'\s+' if c==' ' else re.escape(c) for c in value)
    regex = re.compile(r'(?<!\w)(?:'+'|'.join(pattern(v) for v in sorted(mapping, key=len, reverse=True))+r')(?!\w)', re.I)
    return regex.sub(lambda match: mapping.get(key(match.group()), match.group()), text)


def correct(text, rows=None):
    rows = load() if rows is None else rows
    return substitute(text, {key(row['recognized'] or row['term']): row['term'] for row in rows})


def pronounce(text, rows=None):
    rows = load() if rows is None else rows
    return substitute(text, {key(row['term']): row['pronunciation'] for row in rows if row['pronunciation']})
