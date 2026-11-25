"""Verified app snapshots and deferred startup restore with a recoverable previous copy."""
import hashlib
import json
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED,BadZipFile
from core import workspace_store

FILES={'chat-history.sqlite3','knowledge.sqlite3','tasks.json','routines.json','reminders.json',
       'project-profiles.json','companion-settings.json','ui-layout.json','long-term-memory.json',
       'chat-draft.json','local-benchmarks.json','meeting-drafts.json','model-performance.json',
       'ai-extensions.json','speech-dictionary.json','slash-preferences.json','prompt-snippets.json',
       'custom-commands.json','ai-queue.json','model-comparisons.json',
       'language-tutor.json','tutor-streak.json','voice-style.json'}
MAX_BYTES=100_000_000


def preferences(cfg):
    exact={'chat_provider','reply_mode','assistant_name','user_name','theme','language','ui_theme','ui_color','ui_language','focus_mode','window_geometry'}
    return {key:value for key,value in cfg.items() if (key in exact or key.startswith(('ollama_','local_')))
            and not any(term in key.casefold() for term in ('key','token','password','secret','executable'))}


def copy_database(source,target,connection=None):
    owned=connection is None
    connection=connection or sqlite3.connect(Path(source).resolve().as_uri()+'?mode=ro',uri=True)
    destination=sqlite3.connect(target)
    try:connection.backup(destination)
    finally:
        destination.close()
        if owned:connection.close()


def backup(path,connection=None):
    from memory.config_manager import load_api_keys
    root=workspace_store.directory()
    with tempfile.TemporaryDirectory(prefix='brave-backup-') as folder:
        stage=Path(folder)
        for name in sorted(FILES):
            source=root/name
            if name=='chat-history.sqlite3' and connection is not None:copy_database(source,stage/name,connection)
            elif source.is_file():
                if source.stat().st_size>MAX_BYTES:raise ValueError('Nusxa hajmi chegaradan katta.')
                if name.endswith('.sqlite3'):copy_database(source,stage/name)
                else:shutil.copyfile(source,stage/name)
        (stage/'preferences.json').write_text(json.dumps(preferences(load_api_keys()),ensure_ascii=False),encoding='utf-8')
        entries=list(stage.iterdir())
        if sum(p.stat().st_size for p in entries)>MAX_BYTES:raise ValueError('Nusxa hajmi chegaradan katta.')
        manifest={'version':1,'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in entries}}
        target=Path(path);temporary=target.with_name(target.name+'.tmp')
        try:
            with ZipFile(temporary,'w',ZIP_DEFLATED) as archive:
                for source in entries:archive.write(source,source.name)
                archive.writestr('manifest.json',json.dumps(manifest))
            temporary.replace(target)
        finally:
            if temporary.exists():temporary.unlink()


def validate(path):
    try:
        with ZipFile(path) as archive:
            entries=archive.infolist();names=[row.filename for row in entries]
            if len(names)!=len(set(names)) or not set(names)<=FILES|{'preferences.json','manifest.json'} or 'manifest.json' not in names:
                raise ValueError('Nusxa tarkibi noto‘g‘ri.')
            if sum(row.file_size for row in entries)>MAX_BYTES:raise ValueError('Nusxa hajmi chegaradan katta.')
            manifest=json.loads(archive.read('manifest.json'))
            if manifest.get('version')!=1 or set(manifest.get('files',{}))!=set(names)-{'manifest.json'}:
                raise ValueError('Nusxa versiyasi noto‘g‘ri.')
            result={}
            for name,expected in manifest['files'].items():
                data=archive.read(name)
                if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Nusxa tekshiruvi o‘tmadi.')
                if name.endswith('.json'):
                    value=json.loads(data)
                    if not isinstance(value,(list,dict)):raise ValueError('Nusxa JSON tarkibi noto‘g‘ri.')
                if name.endswith('.sqlite3'):
                    with tempfile.TemporaryDirectory(prefix='brave-check-') as folder:
                        target=Path(folder)/name;target.write_bytes(data)
                        db=sqlite3.connect(target.resolve().as_uri()+'?mode=ro',uri=True)
                        try:
                            if db.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('Nusxa bazasi buzilgan.')
                            required={'chats','messages'} if name.startswith('chat-') else {'documents','chunks'}
                            tables={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                            if not required<=tables:raise ValueError('Nusxa bazasi mos emas.')
                        finally:db.close()
                result[name]=data
            return result
    except (BadZipFile,KeyError,TypeError,json.JSONDecodeError,sqlite3.Error) as exc:
        raise ValueError('Brave nusxasini o‘qib bo‘lmadi.') from exc


def stage_restore(path):
    validate(path)
    target=workspace_store.directory()/'pending-restore.zip'
    temporary=target.with_suffix('.tmp');shutil.copyfile(path,temporary);temporary.replace(target)


def apply_pending():
    root=workspace_store.directory();pending=root/'pending-restore.zip'
    if not pending.is_file():return False
    rows=validate(pending)
    from memory.config_manager import load_api_keys,_patch_config
    old_preferences=preferences(load_api_keys())
    rollback=root/f'before-restore-{time.time_ns()}.zip'
    backup(rollback)
    # Run before any UI store connection opens. Keep rollback even on success.
    previous={};created=[]
    try:
        for name,data in rows.items():
            if name=='preferences.json':continue
            target=root/name
            if name.endswith('.sqlite3'):
                for suffix in ('-wal','-shm'):
                    sidecar=root/(name+suffix)
                    if sidecar.is_file():
                        previous[name+suffix]=sidecar.read_bytes()
                        sidecar.unlink();created.append(name+suffix)
            previous[name]=target.read_bytes() if target.exists() else None
            temporary=root/(name+'.restore-tmp');temporary.write_bytes(data)
            temporary.replace(target);created.append(name)
        if 'preferences.json' in rows:_patch_config(**preferences(json.loads(rows['preferences.json'])))
        pending.unlink();return True
    except Exception:
        for name in created:
            if previous[name] is None:(root/name).unlink(missing_ok=True)
            else:(root/name).write_bytes(previous[name])
        _patch_config(**old_preferences)
        raise
