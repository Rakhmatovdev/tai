"""Read-only code/diff collection; no execution, external diff drivers or writes."""
from pathlib import Path
import re
import subprocess

from core.local_documents import clean
from core.project_context import EXTENSIONS

LIMIT = 180_000


def allowed(path):
    return (path.suffix.lower() in EXTENSIONS and not path.name.startswith('.') and
            not re.search(r'api[_-]?keys?|credentials?|secrets?|\.pem$',path.name,re.I))


def file_sections(path):
    original = Path(path)
    if original.is_symlink(): raise ValueError('Havola o‘rniga asl kod faylini tanlang.')
    path = original.resolve()
    if not allowed(path) or not path.is_file() or path.stat().st_size>LIMIT:
        raise ValueError('Kod fayli qo‘llanmaydi yoki 180 KB dan katta.')
    text = clean(path.read_text(encoding='utf-8-sig'))
    if 'PRIVATE KEY-----' in text: raise ValueError('Maxfiy faylni tahlil qilib bo‘lmaydi.')
    return [(path.name, '\n'.join(f'{i}: {line}' for i,line in enumerate(text.splitlines(),1)))]


def git(root, *arguments):
    result = subprocess.run(['git','-c','core.fsmonitor=false','-c','core.pager=cat',*arguments],cwd=root,
                            capture_output=True, timeout=10, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode: raise ValueError('Git repozitoriy yoki HEAD topilmadi. Kod faylini tanlashingiz mumkin.')
    return result.stdout


def diff_sections(root, cancelled):
    root = Path(root).resolve()
    top = Path(git(root,'rev-parse','--show-toplevel').decode('utf-8').strip()).resolve()
    if top!=root: raise ValueError('Git repozitoriyning asosiy papkasini tanlang.')
    names = git(root,'diff','--name-only','-z','HEAD','--').decode('utf-8','replace').split('\0')
    paths = []
    for name in names:
        if not name: continue
        path = root/name
        if not allowed(path) or path.is_symlink() or not path.resolve().is_relative_to(root): continue
        if path.exists() and path.stat().st_size>LIMIT: raise ValueError('O‘zgargan kod fayli juda katta.')
        # Also bound the pre-change blob, including deleted files.
        try: old_size = int(git(root,'cat-file','-s','HEAD:'+name))
        except ValueError: old_size = 0  # a newly added staged file
        if old_size>LIMIT: raise ValueError('Oldingi kod fayli juda katta.')
        paths.append(name)
    if not paths: raise ValueError('Tahlil uchun kuzatilgan kod o‘zgarishlari topilmadi.')
    if len(paths)>30: raise ValueError('30 tadan ko‘p fayl o‘zgargan. Alohida faylni tanlang.')
    rows, total = [], 0
    for name in paths:
        if cancelled.is_set(): raise RuntimeError('Bekor qilindi.')
        text = git(root,'diff','--no-ext-diff','--no-textconv','--no-color','--unified=3','HEAD','--',name).decode('utf-8','replace')
        text = clean(text)
        total += len(text)
        if total>LIMIT: raise ValueError('Diff juda katta. Alohida faylni tanlang.')
        if text.strip(): rows.append((name,text))
    return rows
