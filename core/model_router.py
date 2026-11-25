"""Opt-in task routing, cached metadata only; never saves a model or downloads."""
import re
import threading
import time
from dataclasses import replace
from core.model_recommender import recommend

_cache = {}
_lock = threading.Lock()


def task_for(text, images=False):
    if images: return 'vision'
    return 'code' if re.search(r'```|\b(python|javascript|typescript|traceback|debug|refactor|sql|kod|code|bug|exception)\b',text,re.I) else 'text'


def route(settings, text, images, cancelled, *, force=False, tools=False, thinking=False, fast=False):
    from core.ai_extensions import settings as preferences
    if not force and not preferences()['auto_route']: return settings
    task = task_for(text, images)
    key = (settings.url, task)
    with _lock: cached = _cache.get(key)
    if cached and time.monotonic()-cached[0]<60:
        rows = cached[1]
    else:
        rows = recommend(settings, task, cancelled)
        if cancelled.is_set(): raise RuntimeError('Bekor qilindi.')
        with _lock: _cache[key] = (time.monotonic(), rows)
    if tools:rows=[row for row in rows if 'tools' in row.get('capabilities',[])]
    if thinking:rows=[row for row in rows if 'thinking' in row.get('capabilities',[])]
    if fast and not images and any('thinking' not in row.get('capabilities',[]) for row in rows):
        rows=[row for row in rows if 'thinking' not in row.get('capabilities',[])]
    if not rows:
        if thinking:raise ValueError('O‘rnatilgan Thinking modeli topilmadi. Model sozlamalarini tekshiring.')
        if images: raise ValueError('O‘rnatilgan Vision modeli topilmadi.')
        return settings
    # Favor models that fit; vision can require CPU offload and is explicit.
    choices = [row for row in rows if row['fits_estimate']]
    from core.model_performance import measured_order
    selected = measured_order(choices or rows,settings,task)[0]
    choice=settings.thinking
    if thinking:
        values=selected.get('thinking_values',[])
        choice='on' if True in values else next((value for value in ('high','medium','low') if value in values),'auto')
    return replace(settings, model=selected['name'],thinking=choice)
