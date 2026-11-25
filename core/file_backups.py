"""Durable pre-write copies with conflict-aware restore."""
from pathlib import Path
import hashlib,shutil,uuid
from datetime import datetime
from core import workspace_store
def digest(path):
    if not Path(path).is_file():return None
    hasher=hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda:source.read(1024*1024),b''):hasher.update(chunk)
    return hasher.hexdigest()
def capture(path):
    path=Path(path).resolve()
    if not path.exists():return None
    identity=uuid.uuid4().hex;folder=workspace_store.directory()/'file-backups';folder.mkdir(exist_ok=True)
    saved=folder/(identity+'.bin');shutil.copy2(path,saved)
    return {'id':identity,'path':str(path),'at':datetime.now().astimezone().isoformat(timespec='seconds'),'before':digest(saved)}
def commit(record,path):
    if not record:return
    record={**record,'after':digest(path),'restored':False}
    workspace_store.append('file-backups.json',record,limit=None)
def restore(identity):
    import re
    if not re.fullmatch('[0-9a-f]{32}',identity):raise ValueError('Invalid backup')
    rows=workspace_store.read('file-backups.json',[]);record=next((r for r in rows if r['id']==identity),None)
    if not record or record.get('restored'):raise ValueError('Backup unavailable')
    target=Path(record['path']);source=workspace_store.directory()/'file-backups'/(identity+'.bin')
    if target.is_symlink() or target.resolve()!=target or digest(target)!=record['after']:raise ValueError('Fayl keyinroq o‘zgargan. Eski nusxa bilan avtomatik almashtirilmadi.')
    if digest(source)!=record['before']:raise ValueError('Backup damaged')
    temporary=target.with_name(target.name+'.'+uuid.uuid4().hex+'.restore')
    try:
        shutil.copy2(source,temporary);temporary.replace(target)
    finally:
        if temporary.exists():temporary.unlink()
    workspace_store.update('file-backups.json',lambda rows:[{**r,'restored':True} if r['id']==identity else r for r in rows])
    return str(target)

def delete(identity):
    import re
    if not re.fullmatch('[0-9a-f]{32}',identity):raise ValueError('Invalid backup')
    source=workspace_store.directory()/'file-backups'/(identity+'.bin')
    source.unlink(missing_ok=True)
    workspace_store.update('file-backups.json',lambda rows:[row for row in rows if row['id']!=identity])
