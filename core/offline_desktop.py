"""Allowlisted offline tools: fixed app launches and selected-folder name search."""
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time

from core import workspace_store

APPS = {'notepad': 'Notepad', 'calculator': 'Calculator', 'paint': 'Paint',
        'files': 'File Explorer', 'vscode': 'VS Code'}
TOOLS = [
    {'type':'function','function':{'name':'open_local_app','description':'Open one allowed installed application. Requires user confirmation.',
     'parameters':{'type':'object','properties':{'app':{'type':'string','enum':list(APPS)}},'required':['app'],'additionalProperties':False}}},
    {'type':'function','function':{'name':'find_local_files','description':'Find filenames only inside the user-selected allowed folder. Does not read contents.',
     'parameters':{'type':'object','properties':{'query':{'type':'string'}},'required':['query'],'additionalProperties':False}}},
    {'type':'function','function':{'name':'local_system_status','description':'Read local CPU and memory usage.',
     'parameters':{'type':'object','properties':{},'additionalProperties':False}}},
]
NAMES = {row['function']['name'] for row in TOOLS}


def settings():
    value = workspace_store.read('offline-desktop.json', {})
    if not isinstance(value,dict):return {'enabled':False,'root':''}
    return {'enabled':value.get('enabled') is True,
            'root':value.get('root','') if isinstance(value.get('root',''),str) else ''}


def save(enabled, root):
    path = Path(root).expanduser().resolve() if root else None
    if path and not path.is_dir(): raise ValueError('Qidiruv papkasi topilmadi.')
    workspace_store.write('offline-desktop.json', {'enabled':bool(enabled), 'root':str(path) if path else ''})


def validate(name, arguments, policy):
    cfg = settings()
    if not cfg.get('enabled'): raise ValueError('Offline amallar yoqilmagan.')
    if name not in NAMES or not isinstance(arguments, dict): raise ValueError('Offline amal noto‘g‘ri.')
    required = {'app'} if name=='open_local_app' else {'query'} if name=='find_local_files' else set()
    if set(arguments)!=required: raise ValueError('Offline amal argumentlari noto‘g‘ri.')
    permission = 'files' if name=='find_local_files' else 'system'
    if not policy['permissions'].get(permission, False): raise ValueError('Amal uchun ruxsat o‘chiq.')
    if name=='open_local_app' and (not isinstance(arguments['app'],str) or arguments['app'] not in APPS): raise ValueError('Dastur ruxsat etilmagan.')
    if name=='find_local_files' and (not isinstance(arguments['query'], str) or not 1<=len(arguments['query'].strip())<=100):
        raise ValueError('Qidiruv matni 1–100 belgi bo‘lsin.')
    return cfg


def executable(app):
    if app not in APPS: raise ValueError('Dastur ruxsat etilmagan.')
    system = platform.system()
    if system=='Windows':
        windows = Path(os.environ.get('WINDIR', 'C:/Windows'))
        candidates = {
            'notepad':[windows/'System32/notepad.exe'], 'calculator':[windows/'System32/calc.exe'],
            'paint':[windows/'System32/mspaint.exe'], 'files':[windows/'explorer.exe'],
            'vscode':[Path(os.environ.get('LOCALAPPDATA', ''))/'Programs/Microsoft VS Code/Code.exe',
                      Path(os.environ.get('ProgramFiles', 'C:/Program Files'))/'Microsoft VS Code/Code.exe']}
        path = next((p for p in candidates[app] if p.is_file()), None)
        if path: return [str(path.resolve())]
    elif system=='Darwin':
        names = {'notepad':'TextEdit','calculator':'Calculator','paint':'Preview','files':'Finder','vscode':'Visual Studio Code'}
        return ['/usr/bin/open', '-a', names[app]]
    else:
        names = {'notepad':'gedit','calculator':'gnome-calculator','paint':'pinta','files':'nautilus','vscode':'code'}
        path = shutil.which(names[app])
        if path: return [str(Path(path).resolve())]
    raise ValueError('Bu dastur o‘rnatilmagan yoki topilmadi.')


def search(root, query, cancelled):
    if not root: raise ValueError('Avval qidiruv papkasini tanlang.')
    root = Path(root).resolve()
    if not root.is_dir(): raise ValueError('Qidiruv papkasi topilmadi.')
    from core.project_context import SKIP
    rows, count, clipped = [], 0, False
    deadline = time.monotonic()+3
    for folder, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP and not d.startswith('.')
                         and not (Path(folder)/d).is_symlink()
                         and not (hasattr(Path(folder)/d,'is_junction') and (Path(folder)/d).is_junction()))
        for name in sorted(files):
            if cancelled.is_set(): raise RuntimeError('Bekor qilindi.')
            count += 1
            if count>5000 or time.monotonic()>deadline: return {'files':rows, 'truncated':True}
            path = Path(folder)/name
            if name.startswith('.') or path.is_symlink(): continue
            if query.casefold() in name.casefold() and path.resolve().is_relative_to(root):
                rows.append(str(path.relative_to(root)))
                if len(rows)>=20: return {'files':rows, 'truncated':True}
    return {'files':rows, 'truncated':clipped}


def execute(name, arguments, policy, cancelled, approved=False):
    cfg = validate(name, arguments, policy)
    if cancelled.is_set(): raise RuntimeError('Bekor qilindi.')
    if name=='open_local_app':
        if not approved: raise ValueError('Dastur ochilishi tasdiqlanmadi.')
        command = executable(arguments['app'])
        if cancelled.is_set(): raise RuntimeError('Bekor qilindi.')
        subprocess.Popen(command, shell=False, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        return {'status':'launch_requested','app':arguments['app']}
    if name=='find_local_files': return search(cfg.get('root',''), arguments['query'].strip(), cancelled)
    import psutil
    memory = psutil.virtual_memory()
    return {'cpu_percent':psutil.cpu_percent(interval=None), 'ram_available_gib':round(memory.available/2**30,2),
            'ram_total_gib':round(memory.total/2**30,2)}
