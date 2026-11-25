"""Durable, bounded local inference jobs. Loading never runs or retries jobs."""
from dataclasses import asdict
from pathlib import Path
import time
import uuid
from core import workspace_store
from core.ollama_chat import Settings,PROFILES,local_url,local_model

FILE='ai-queue.json'
STATUSES={'pending','running','completed','failed','cancelled','interrupted'}


def settings(raw):
    if not isinstance(raw,dict):raise ValueError('Noto‘g‘ri model sozlamalari.')
    value=Settings(local_url(raw.get('url','')),local_model(raw.get('model','')),raw.get('profile','balanced'),raw.get('autostart') is True,raw.get('thinking','off'))
    from core.ollama_model import thinking_choice
    if value.profile not in ('auto',*PROFILES) or not thinking_choice(value.thinking):raise ValueError('Noto‘g‘ri model sozlamalari.')
    return value


def capture_paths(paths):
    if len(paths)>10:raise ValueError('1–10 ta fayl tanlang.')
    rows=[]
    for value in paths:
        path=Path(value).resolve(strict=True)
        if not path.is_file():raise ValueError('Fayl topilmadi.')
        stat=path.stat();rows.append(dict(path=str(path),size=stat.st_size,modified=stat.st_mtime_ns))
    return rows


def verify_paths(rows):
    for row in rows:
        path=Path(row['path']);stat=path.stat()
        if not path.is_file() or stat.st_size!=row['size'] or stat.st_mtime_ns!=row['modified']:
            raise ValueError('Navbatdagi fayl o‘zgargan. Uni qayta qo‘shing.')
    return [row['path'] for row in rows]


def create(title,instruction,text='',paths=(),model_settings=None,kind='analysis'):
    title,instruction,text=title.strip(),instruction.strip(),text.strip()
    if kind not in ('analysis','totext'):raise ValueError('Noto‘g‘ri vazifa turi.')
    if not 1<=len(title)<=80 or len(instruction)>4000 or len(text)>10000:raise ValueError('Nom 1–80, topshiriq 4000, matn 10000 belgidan oshmasin.')
    if kind=='analysis' and (not instruction or not (text or paths)):raise ValueError('Topshiriq va manba matni yoki fayl kiriting.')
    if kind=='totext' and not paths:raise ValueError('Fayl tanlang')
    return dict(id=uuid.uuid4().hex,title=title,instruction=instruction,text=text,files=capture_paths(paths),
        settings=asdict(model_settings or Settings.read()),kind=kind,status='pending',result='',error='',created=time.time())


def load():
    raw=workspace_store.read(FILE,[]);rows=[]
    if not isinstance(raw,list):return []
    for row in raw[:30]:
        if not isinstance(row,dict):continue
        if (any(not isinstance(row.get(key),str) for key in ('id','title','instruction','text','result','error'))
                or not 1<=len(row['id'])<=80 or not 1<=len(row['title'])<=80
                or len(row['instruction'])>4000 or len(row['text'])>10000 or len(row['result'])>200000
                or len(row['error'])>2000 or row.get('status') not in STATUSES
                or row.get('kind') not in ('analysis','totext') or not isinstance(row.get('files'),list) or len(row['files'])>10):continue
        try:settings(row.get('settings'))
        except (ValueError,TypeError):continue
        if any(not isinstance(f,dict) or not isinstance(f.get('path'),str) or len(f['path'])>1000
               or not Path(f['path']).is_absolute() or type(f.get('size')) is not int or type(f.get('modified')) is not int for f in row['files']):continue
        if any(old['id']==row['id'] for old in rows):continue
        row=dict(row)
        if row['status']=='running':row['status']='interrupted';row['error']='Ilova yopilganda vazifa uzilgan. Qayta boshlashni o‘zingiz tanlang.'
        rows.append(row)
    return rows


def save(rows):
    if len(rows)>30:raise ValueError('Navbatda ko‘pi bilan 30 ta vazifa saqlang.')
    workspace_store.write(FILE,rows)
