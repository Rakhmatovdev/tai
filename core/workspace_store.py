"""Small atomic local registries, stored outside the project checkout."""
import json
import os
from pathlib import Path
import threading
import uuid

_lock=threading.RLock()


def directory():
    root=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local'/'share')))/'Brave'
    root.mkdir(parents=True,exist_ok=True)
    return root


def read(name,default=None):
    with _lock:
        try:return json.loads((directory()/name).read_text(encoding='utf-8'))
        except (OSError,ValueError):return default if default is not None else []


def write(name,value):
    with _lock:
        target=directory()/name
        temp=target.with_name(target.name+'.'+uuid.uuid4().hex+'.tmp')
        try:
            temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
            temp.replace(target)
        finally:
            if temp.exists():temp.unlink()


def append(name,value,limit=500):
    with _lock:
        rows=read(name,[]);rows.append(value);write(name,rows if limit is None else rows[-limit:])


def update(name,transform):
    with _lock:
        rows=transform(read(name,[]));write(name,rows);return rows
