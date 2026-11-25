"""Local full-text extraction with explicit bounds, no LLM generation."""
from pathlib import Path
from core.local_documents import validate_paths,extract
from core.meeting_audio import AUDIO,transcribe_file


def combine_chunks(chunks):
    groups={}
    for row in chunks:
        label,separator,index=row['label'].rpartition(' · #')
        if not separator:label=row['label'];index='1'
        offset=(int(index)-1)*1000
        text,end=groups.get(label,('',offset))
        overlap=max(0,end-offset)
        text+=row['text'][overlap:];groups[label]=(text,offset+len(row['text']))
    return '\n\n'.join(label+'\n'+text for label,(text,_) in groups.items())


def convert(paths,model,language,cancelled,progress=lambda text:None,allowed=lambda:True):
    if not paths or len(paths)>10:raise ValueError('1–10 ta fayl tanlang.')
    rows=[];size=0
    for value in paths:
        if cancelled.is_set():return ''
        if not allowed():raise ValueError('Fayllarga ruxsat o‘chiq.')
        path=Path(value)
        progress(path.name)
        if path.suffix.lower() in AUDIO:
            text=path.name+'\n'+transcribe_file(path,model,language,cancelled,allowed=allowed,quality='accurate')
        else:
            checked=validate_paths([path])
            chunks,truncated=extract(checked[0],cancelled)
            if truncated:raise ValueError('Matn chegaraga yetdi. Faylni kichikroq qismlarga ajrating.')
            text=combine_chunks(chunks)
        if cancelled.is_set():return ''
        if not allowed():raise ValueError('Fayllarga ruxsat o‘chiq.')
        size+=len(text)
        if size>200000:raise ValueError('Matn 200 ming belgidan oshmasin.')
        rows.append(text)
    return '\n\n'.join(rows)
