"""Runtime tool permissions controlled by the local Brave interface with educational restrictions."""
from contextlib import contextmanager
from dataclasses import dataclass
import re
import threading
from urllib.parse import urlparse

CAPABILITIES=('network','microphone','screen','camera','files','code','system')
DEFAULT_POLICY={
    'mode':'smart',
    'turbo':False,
    'permissions':{
        'network':True,
        'microphone':True,
        'screen':True,
        'camera':False,
        'files':True,
        'code':False,
        'system':False,
    },
    'educational_filter':True,
}

EDUCATIONAL_ALLOWED_DOMAINS = {
    # YouTube & Streaming
    'youtube.com',
    'youtu.be',
    'ytimg.com',
    'googlevideo.com',

    # Dictionaries & Linguistic Resources
    'cambridge.org',
    'dictionary.cambridge.org',
    'oxfordlearnersdictionaries.com',
    'oed.com',
    'merriam-webster.com',
    'learnersdictionary.com',
    'collinsdictionary.com',
    'ldoceonline.com',
    'macmillandictionary.com',
    'vocabulary.com',
    'thesaurus.com',
    'dictionary.com',
    'wordreference.com',
    'urbandictionary.com',
    'etymonline.com',

    # Pronunciation, Educational Video & English Learning
    'youglish.com',
    'ted.com',
    'ed.ted.com',
    'bbc.co.uk',
    'bbc.com',
    'britishcouncil.org',
    'learnenglish.britishcouncil.org',
    'engvid.com',
    'eslcafe.com',
    'fluentu.com',
    'englishclub.com',

    # Encyclopedias & Reference
    'wikipedia.org',
    'wiktionary.org',
    'wikimedia.org',
    'britannica.com',

    # Translation & Grammar Tools
    'translate.google.com',
    'grammarly.com',
    'deepl.com',
    'duolingo.com',
    'quizlet.com',
    'ankiweb.net',
}

EDUCATIONAL_ALLOWED_APPS = {
    'chrome', 'google chrome', 'msedge', 'edge', 'brave', 'firefox', 'opera',
    'vlc', 'notepad', 'notepad.exe', 'calc', 'calculator', 'word', 'winword'
}


def is_educational_url_allowed(url: str) -> bool:
    if not url:
        return True
    u = str(url).strip()
    if u in ('about:blank', 'blank', ''):
        return True
    if u.startswith('brave-source:') or u.startswith('tai:'):
        return True
    if not (u.startswith('http://') or u.startswith('https://') or u.startswith('//')):
        u = 'https://' + u
    try:
        parsed = urlparse(u)
        host = (parsed.hostname or '').lower()
        if not host:
            return False
        if host in EDUCATIONAL_ALLOWED_DOMAINS:
            return True
        for domain in EDUCATIONAL_ALLOWED_DOMAINS:
            if host.endswith('.' + domain):
                return True
        return False
    except Exception:
        return False


def get_educational_notice(target: str = '') -> str:
    target_str = f" ('{target}')" if target else ""
    return (
        f"TAI Ta'limiy Cheklovi: Ushbu manzil{target_str} ta'lim ro'yxatida mavjud emas. "
        "TAI faqat YouTube va tasdiqlangan ta'limiy manbalarga (Cambridge, Oxford, BBC, TED va h.k.) ruxsat beradi."
    )
_provider=None
_local=threading.local()


def bind(provider):
    global _provider
    _provider=provider


def current():
    raw=_provider() if _provider else DEFAULT_POLICY
    raw_perms = raw.get('permissions', {})
    permissions={
        key: raw_perms.get(key, DEFAULT_POLICY['permissions'].get(key, True)) is True
        for key in CAPABILITIES
    }
    mode=raw.get('mode','smart')
    return {
        'mode':mode if mode in ('ask','smart','full') else 'smart',
        'turbo':bool(raw.get('turbo')),
        'permissions':permissions,
        'educational_filter':bool(raw.get('educational_filter', True)),
    }


@contextmanager
def trusted_scope(approved):
    before=getattr(_local,'approved',False)
    _local.approved=bool(approved)
    try:yield
    finally:_local.approved=before


def may_autoconfirm():
    return getattr(_local,'approved',False) or current()['mode']=='full'


@dataclass(frozen=True)
class Decision:
    allowed:bool
    confirm:bool
    risk:str
    capabilities:tuple


def decide(name,args,policy=None):
    policy=policy or current()
    action=str(args.get('action',args.get('intent',''))).casefold()
    reads={'list','read','search','find','stats','info','get','status','explain','analyze','current_wallpaper','get_title','get_url','get_tabs','extract_text','wait','screenshot'}
    low={'system_status','recall_memory','weather_report','web_search','flight_finder','close_camera'}
    risk='low' if name in low else 'high'
    caps=set()
    if name in ('system_status','shutdown_brave','computer_settings','computer_control','game_updater','desktop_control'):caps.add('system')
    if name=='open_app':
        app_target=str(args.get('app_name',args.get('name',''))).strip().casefold()
        if app_target and app_target not in EDUCATIONAL_ALLOWED_APPS:
            caps.add('system')
    if name in ('recall_memory','save_memory','undo','file_controller','file_processor','code_helper','dev_agent','desktop_control','game_updater'):caps.add('files')
    if name in ('code_helper','dev_agent') or (name=='desktop_control' and (action=='task' or args.get('task'))):caps.add('code')
    if name=='screen_process':caps.add('camera' if args.get('angle',args.get('source','screen'))=='camera' else 'screen')
    if name=='computer_control' and action in ('screenshot','screen_find','screen_click','smart_type'):caps.add('screen')
    if name=='code_helper' and action=='screen_debug':caps.add('screen')
    if name in ('browser_control','web_search','weather_report','flight_finder','file_processor','code_helper','dev_agent','game_updater','send_message','youtube_video','video_player'):caps.add('network')
    if name in ('save_memory','reminder','manage_monitor'):risk='low'
    if name=='reminder':caps.update(('files','system'))
    if name in ('file_controller','desktop_control','computer_settings','browser_control') and action in reads:risk='low'
    if name=='computer_control' and action in ('wait','move','screenshot','screen_find'):risk='low'
    known=low|{'save_memory','undo','screen_process','shutdown_brave','open_app','computer_settings','computer_control','game_updater','send_message','video_player','youtube_video','browser_control','desktop_control','file_controller','file_processor','code_helper','dev_agent','reminder','manage_monitor'}
    if name not in known:
        caps.update(CAPABILITIES);risk='high'

    # Educational Restriction enforcement (YouTube, educational dictionaries, etc.)
    if policy.get('educational_filter', True):
        target_url = str(args.get('url', args.get('link', args.get('target', '')))).strip()
        if name == 'browser_control' and action in ('go_to', 'new_tab', 'open') and target_url:
            if not is_educational_url_allowed(target_url):
                return Decision(False, False, 'high', tuple(sorted(caps | {'network'})))
        elif name == 'youtube_video' and target_url:
            if not is_educational_url_allowed(target_url):
                return Decision(False, False, 'high', tuple(sorted(caps | {'network'})))

    allowed=all(policy.get('permissions',{}).get(cap,True) for cap in caps)
    mode=policy.get('mode','smart')
    return Decision(allowed,allowed and (mode=='ask' or (mode=='smart' and risk=='high')),risk,tuple(sorted(caps)))


def preview(name,args):
    # Never expose credentials through the approval/audit view.
    rows=[name]
    for key,value in args.items():
        if re.search(r'api[_-]?key|token|password|secret|credential|authorization',key,re.I):value='[hidden]'
        else:
            value=str(value)
            value=re.sub(r'AIza[\w-]{20,}|sk-[\w-]{20,}', '[hidden]',value)
            value=re.sub(r'(?i)Bearer\s+[\w.-]{8,}', 'Bearer [hidden]',value)
            value=re.sub(r'(?i)(api[_-]?key|password|token|secret)\s*[:=]\s*[\"\x27]?[^\s\"\x27,;]+',r'\1=[hidden]',value)
        rows.append(f'{key}: {str(value)[:2000]}')
    return '\n'.join(rows)[:8000]


def work_budget(normal):
    return max(normal,20) if current()['turbo'] else normal


def cancelled(player):
    return bool(player is not None and getattr(player,'task_cancelled',False))
