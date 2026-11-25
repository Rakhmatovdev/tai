"""Windowless desktop entry point; logs errors and focuses an existing instance."""
import ctypes
from ctypes import wintypes
import hashlib
import os
from pathlib import Path
import runpy
import sys

ROOT=Path(__file__).resolve().parent


def focus_existing(pid):
    user=ctypes.windll.user32
    kernel=ctypes.windll.kernel32
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    user.GetWindowThreadProcessId.argtypes=(wintypes.HWND,ctypes.POINTER(wintypes.DWORD))
    user.IsWindowVisible.argtypes=(wintypes.HWND,)
    user.GetWindowTextLengthW.argtypes=(wintypes.HWND,)
    user.ShowWindow.argtypes=(wintypes.HWND,ctypes.c_int)
    user.SetForegroundWindow.argtypes=(wintypes.HWND,)
    user.EnumWindows.argtypes=(callback_type,wintypes.LPARAM)
    user.GetForegroundWindow.restype=wintypes.HWND
    user.GetWindow.argtypes=(wintypes.HWND,ctypes.c_uint)
    user.GetWindow.restype=wintypes.HWND
    user.GetLastActivePopup.argtypes=(wintypes.HWND,)
    user.GetLastActivePopup.restype=wintypes.HWND
    user.GetClassNameW.argtypes=(wintypes.HWND,wintypes.LPWSTR,ctypes.c_int)
    user.AttachThreadInput.argtypes=(wintypes.DWORD,wintypes.DWORD,wintypes.BOOL)
    user.BringWindowToTop.argtypes=(wintypes.HWND,)
    user.IsIconic.argtypes=(wintypes.HWND,)
    user.AllowSetForegroundWindow.argtypes=(wintypes.DWORD,)
    focused=False
    def visit(window,param):
        nonlocal focused
        process=wintypes.DWORD()
        user.GetWindowThreadProcessId(window,ctypes.byref(process))
        class_name=ctypes.create_unicode_buffer(128)
        user.GetClassNameW(window,class_name,128)
        if process.value==pid and class_name.value.startswith('Qt') and 'QWindow' in class_name.value and not user.GetWindow(window,4) and user.GetWindowTextLengthW(window)>0:
            user.ShowWindow(window,9 if user.IsIconic(window) else 5)
            popup=user.GetLastActivePopup(window)
            if popup and user.IsWindowVisible(popup):
                popup_class=ctypes.create_unicode_buffer(128)
                user.GetClassNameW(popup,popup_class,128)
                if 'QWindow' in popup_class.value or popup_class.value=='#32770':window=popup
            foreground=user.GetForegroundWindow()
            foreground_thread=user.GetWindowThreadProcessId(foreground,None) if foreground else 0
            current_thread=kernel.GetCurrentThreadId()
            attached=False
            try:
                user.AllowSetForegroundWindow(pid)
                if foreground_thread and foreground_thread!=current_thread:
                    attached=bool(user.AttachThreadInput(current_thread,foreground_thread,True))
                user.BringWindowToTop(window)
                focused=bool(user.SetForegroundWindow(window))
            finally:
                if attached:user.AttachThreadInput(current_thread,foreground_thread,False)
            return False
        return True
    user.EnumWindows(callback_type(visit),0)
    return focused


def launch():
    log_dir=ROOT/'logs';log_dir.mkdir(exist_ok=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexW.argtypes=(wintypes.LPVOID,wintypes.BOOL,wintypes.LPCWSTR)
    kernel.CreateMutexW.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=(wintypes.HANDLE,)
    identity=hashlib.sha256(str(ROOT).casefold().encode()).hexdigest()[:20]
    handle=kernel.CreateMutexW(None,False,'Local\\Brave-'+identity)
    if not handle:raise ctypes.WinError(ctypes.get_last_error())
    try:
        if ctypes.get_last_error()==183:
            try:focus_existing(int((log_dir/'brave.pid').read_text(encoding='ascii')))
            except (OSError,ValueError):pass
            return
        (log_dir/'brave.pid').write_text(str(os.getpid()),encoding='ascii')
        os.chdir(ROOT)
        sys.path.insert(0,str(ROOT))
        # pythonw has no console. Preserve startup diagnostics in files.
        with (log_dir/'startup.log').open('w',encoding='utf-8',buffering=1) as output, (log_dir/'startup-error.log').open('w',encoding='utf-8',buffering=1) as errors:
            previous_stdout,previous_stderr=sys.stdout,sys.stderr
            sys.stdout=output;sys.stderr=errors
            try:
                runpy.run_path(str(ROOT/'main.py'),run_name='__main__')
            except Exception:
                import traceback
                traceback.print_exc()
                ctypes.windll.user32.MessageBoxW(None,'Brave ochilmadi. logs/startup-error.log faylini tekshiring.','Brave',16)
            finally:
                sys.stdout,sys.stderr=previous_stdout,previous_stderr
    finally:
        kernel.CloseHandle(handle)


if __name__=='__main__':
    launch()
