"""Review cues for literal numbers; never infer or silently correct quantities."""
import re


def numbers(text):
    text=re.sub(r'\[\d{1,2}:\d{2}(?::\d{2})?\]|\bSpeaker\s+[\d?]+:', '',text)
    values=re.findall(r'(?<!\w)(?:[$€£]\s*)?\d+(?:[.,]\d+)*(?:\s*%)?(?!\w)',text)
    return list(dict.fromkeys(value.strip() for value in values))[:20]


def correct(text,before,after):
    """Edit speech text while protecting timestamps and anonymous speaker IDs."""
    pattern=re.compile(r'(?<!\w)'+re.escape(before)+r'(?!\w)',re.I)
    count=0;rows=[]
    for line in text.splitlines(True):
        prefix=re.match(r'\[\d{1,2}:\d{2}(?::\d{2})?\]\s*',line)
        end=prefix.end() if prefix else 0
        if not before.casefold().startswith('speaker '):
            speaker=re.match(r'Speaker\s+[\d?]+:\s*',line[end:])
            if speaker:end+=speaker.end()
        changed,total=pattern.subn(lambda match:after,line[end:]);count+=total;rows.append(line[:end]+changed)
    return ''.join(rows),count
