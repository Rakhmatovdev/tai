"""Single selected-file edits with a diff, optimistic conflict checks and undo."""
from dataclasses import dataclass
import difflib
import hashlib
from pathlib import Path
import uuid
import shutil
from core.code_review import allowed, LIMIT
from core.local_documents import clean
from core import file_backups,workspace_store


def validate(source,text):
    if not text.strip() or len(text.encode('utf-8'))>LIMIT:raise ValueError('Tuzatish bo‘sh yoki juda katta.')
    if Path(source.path).suffix.lower() in ('.py','.pyw'):
        import ast
        try:ast.parse(text,filename=source.path)
        except SyntaxError as error:raise ValueError(f'Python sintaksis xatosi · {error.lineno}: {error.msg}') from None


def digest(data): return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Snapshot:
    path: str
    before: bytes
    text: str


def snapshot(path):
    original = Path(path).absolute()
    resolved = original.resolve()
    if original.is_symlink() or original!=resolved or not allowed(resolved):
        raise ValueError('Asl kod faylini tanlang; havolalar qo‘llanmaydi.')
    if not resolved.is_file() or resolved.stat().st_size>LIMIT:
        raise ValueError('Kod fayli mavjud emas yoki juda katta.')
    data = resolved.read_bytes()
    try: text = data.decode('utf-8-sig').replace('\r\n','\n')
    except UnicodeError: raise ValueError('UTF-8 kod faylini tanlang.') from None
    if clean(text)!=text: raise ValueError('Maxfiy qiymat bor faylga AI tuzatishi qo‘llanmaydi.')
    return Snapshot(str(resolved), data, text)


def replacement(text):
    text = text.strip()
    if text.startswith('```'):
        lines = text.splitlines()
        if len(lines)<3 or lines[-1].strip()!='```': raise ValueError('Kod bloki tugallanmagan.')
        text = '\n'.join(lines[1:-1])
    if not text or len(text.encode('utf-8'))>LIMIT or '[hidden]' in text:
        raise ValueError('Tuzatish bo‘sh, yashirilgan yoki juda katta.')
    return text+'\n'


def preview(source, new_text):
    return ''.join(difflib.unified_diff(source.text.splitlines(True),new_text.splitlines(True),
                    fromfile=source.path, tofile=source.path+' (proposed)'))


def apply(source, new_text):
    target = Path(source.path)
    if target.is_symlink() or target.resolve()!=target or digest(target.read_bytes())!=digest(source.before):
        raise ValueError('Fayl tahlildan keyin o‘zgargan. Qayta ko‘rib chiqing.')
    validate(source,new_text)
    if new_text==source.text: raise ValueError('O‘zgarish yo‘q.')
    # Preserve BOM and prevailing newline convention.
    new_text = new_text.replace('\r\n','\n')
    if b'\r\n' in source.before: new_text = new_text.replace('\n','\r\n')
    data = (b'\xef\xbb\xbf' if source.before.startswith(b'\xef\xbb\xbf') else b'')+new_text.encode('utf-8')
    record = file_backups.capture(target)
    temporary = target.with_name(target.name+'.'+uuid.uuid4().hex+'.edit')
    try:
        temporary.write_bytes(data)
        shutil.copystat(target,temporary)
        if target.is_symlink() or target.resolve()!=target or target.read_bytes()!=source.before:
            raise ValueError('Fayl o‘zgargan. Tuzatish qo‘llanmadi.')
        temporary.replace(target)
        try:file_backups.commit(record, target)
        except Exception:
            # A registry/disk error must not leave an untracked source edit.
            if target.read_bytes()==data:
                temporary.write_bytes(source.before)
                backup=workspace_store.directory()/'file-backups'/(record['id']+'.bin')
                shutil.copystat(backup,temporary);temporary.replace(target)
            raise
    finally: temporary.unlink(missing_ok=True)
    from core.undo import push_undo
    push_undo('AI edit: '+target.name, lambda:file_backups.restore(record['id']))
    return record['id']


def apply_many(changes):
    """Preflight every file; roll back already-written files on any failure."""
    if not 1<=len(changes)<=8:raise ValueError('1–8 ta kod faylini tanlang.')
    paths=[source.path for source,_ in changes]
    if len(paths)!=len(set(paths)):raise ValueError('Bir xil fayl takrorlangan.')
    for source,text in changes:
        target=Path(source.path)
        if target.is_symlink() or target.resolve()!=target or target.read_bytes()!=source.before:
            raise ValueError('Fayl tahlildan keyin o‘zgargan. Qayta ko‘rib chiqing.')
        validate(source,text)
    if all(text==source.text for source,text in changes):raise ValueError('O‘zgarish yo‘q.')
    records=[]
    try:
        for source,text in changes:
            if text!=source.text:records.append(apply(source,text))
        return records
    except Exception:
        for identity in reversed(records):file_backups.restore(identity)
        raise


def search_replace(sources,response):
    """Parse bounded exact replacements. Never accept model-supplied new paths."""
    import json
    raw=response.strip()
    if raw.startswith('```'):
        lines=raw.splitlines()
        if lines[-1].strip()!='```':raise ValueError('Tuzatish JSON tugallanmagan.')
        raw='\n'.join(lines[1:-1])
    try:value=json.loads(raw)
    except ValueError:raise ValueError('Tuzatish JSON noto‘g‘ri.') from None
    edits=value.get('edits') if isinstance(value,dict) else None
    if not isinstance(edits,list) or not 1<=len(edits)<=30:raise ValueError('Tuzatishlar ro‘yxati noto‘g‘ri.')
    by_name={Path(source.path).name:source for source in sources}
    if len(by_name)!=len(sources):raise ValueError('Tanlangan fayl nomlari takrorlanmasin.')
    replacements={name:source.text for name,source in by_name.items()}
    for edit in edits:
        if not isinstance(edit,dict) or set(edit)!={'file','search','replace'}:raise ValueError('Tuzatish maydonlari noto‘g‘ri.')
        name,search,new=edit['file'],edit['search'],edit['replace']
        if not all(isinstance(value,str) for value in (name,search,new)) or name not in replacements or not search:
            raise ValueError('Tuzatish tanlangan faylga tegishli emas.')
        if replacements[name].count(search)!=1:raise ValueError('Tuzatish manbasi aniq bitta joyga mos kelmadi.')
        text=replacements[name];position=text.index(search)
        candidate=text.replace(search,new,1)
        source=by_name[name]
        try:validate(source,candidate)
        except ValueError:
            # Models sometimes replace an unindented substring within an
            # indented Python line. Preserve that existing prefix on new lines.
            prefix=text[text.rfind('\n',0,position)+1:position]
            if (Path(source.path).suffix.lower() not in ('.py','.pyw') or not prefix or not prefix.isspace()
                    or '\n' in search or '\n' not in new or search!=search.lstrip()):raise
            candidate=text.replace(search,new.replace('\n','\n'+prefix),1)
            validate(source,candidate)
        replacements[name]=candidate
    return [(source,replacements[Path(source.path).name]) for source in sources if replacements[Path(source.path).name]!=source.text]
