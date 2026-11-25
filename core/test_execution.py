"""Explicit argv-based test execution with bounded output, time and process tree."""
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time
import codecs

MAX_OUTPUT=200000


def python_for(root):
    root=Path(root)
    for path in (root/'.venv/Scripts/python.exe',root/'.venv/bin/python'):
        if path.is_file():return str(path.resolve())
    import sys
    if getattr(sys,'frozen',False):
        executable=shutil.which('python')
        if not executable:raise ValueError('Python topilmadi. Loyiha muhitini tayyorlang.')
        return executable
    return sys.executable


def command(root,kind,arguments):
    root=Path(root).expanduser().absolute()
    if root.is_symlink() or root.resolve()!=root or not root.is_dir():raise ValueError('Asl loyiha papkasini tanlang.')
    if not isinstance(arguments,(list,tuple)) or len(arguments)>40 or any(not isinstance(arg,str) or '\0' in arg or len(arg)>2000 for arg in arguments):
        raise ValueError('Test argumentlari noto‘g‘ri.')
    if kind=='unittest':argv=[python_for(root),'-m','unittest',*arguments]
    elif kind=='pytest':argv=[python_for(root),'-m','pytest',*arguments]
    elif kind=='node':
        executable=shutil.which('node')
        if not executable:raise ValueError('Node.js topilmadi.')
        argv=[executable,'--test',*arguments]
    else:raise ValueError('Qo‘llanmaydigan test turi.')
    return root,argv


def stop_tree(process):
    import psutil
    try:
        parent=psutil.Process(process.pid)
        children=parent.children(recursive=True)
        for child in reversed(children):
            try:child.kill()
            except psutil.Error:pass
        try:parent.kill()
        except psutil.Error:pass
        psutil.wait_procs(children,timeout=1)
    except psutil.Error:pass
    try:process.wait(timeout=2)
    except subprocess.TimeoutExpired:pass


def run(root,kind,arguments,cancelled,progress=lambda text:None,*,timeout=60,allowed=lambda:True):
    if type(timeout) is not int or not 1<=timeout<=300:raise ValueError('Test vaqti 1–300 soniya bo‘lsin.')
    root,argv=command(root,kind,arguments)
    if cancelled.is_set() or not allowed():raise RuntimeError('Test bajarishga ruxsat yo‘q yoki bekor qilindi.')
    # A clean environment avoids handing API keys to project test code.
    keep={'SYSTEMROOT','WINDIR','PATH','PATHEXT','TEMP','TMP','HOME','USERPROFILE','LOCALAPPDATA','APPDATA','LANG','LC_ALL'}
    environment={key:value for key,value in os.environ.items() if key.upper() in keep}
    environment.update(PYTHONIOENCODING='utf-8',PYTHONUNBUFFERED='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    process=subprocess.Popen(argv,cwd=root,env=environment,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
        shell=False,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    output=queue.Queue(maxsize=64);done=threading.Event();text='';limited=False;reason='';started=time.monotonic()
    def read():
        try:
            while True:
                block=process.stdout.read1(4096)
                if not block:break
                while not done.is_set():
                    try:output.put(block,timeout=.1);break
                    except queue.Full:pass
        except (OSError,ValueError):pass
        finally:done.set()
    reader=threading.Thread(target=read,daemon=True,name='brave-test-output');reader.start()
    decoder=codecs.getincrementaldecoder('utf-8')('replace')
    try:
        while True:
            if cancelled.is_set():reason='cancelled';break
            if not allowed():reason='permission';break
            if time.monotonic()-started>=timeout:reason='timeout';break
            try:
                block=output.get(timeout=.05)
                decoded=decoder.decode(block)
                if len(text)+len(decoded)>MAX_OUTPUT:
                    text=(text+decoded)[:MAX_OUTPUT];limited=True;reason='output_limit';progress(text);break
                text+=decoded;progress(text)
            except queue.Empty:pass
            if done.is_set() and output.empty() and process.poll() is not None:break
        if reason:stop_tree(process)
        code=process.wait(timeout=2)
        return {'argv':argv,'root':str(root),'output':text,'exit_code':code,'reason':reason or 'finished',
                'passed':code==0 and not reason,'elapsed_s':time.monotonic()-started,'truncated':limited}
    finally:
        done.set()
        if process.poll() is None:stop_tree(process)
        if process.stdout:process.stdout.close()
        reader.join(timeout=1)
