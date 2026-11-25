"""Bounded numeric inference observations for task-specific model selection."""
import math
import statistics
import time
from core import workspace_store


def number(value):return type(value) in (float,int) and math.isfinite(value) and value>0


def record(settings,task,metrics):
    if task not in ('text','code','vision') or metrics.get('status') not in ('completed',None):return
    ttft=metrics.get('first_reply_s');rate=metrics.get('tokens_per_second')
    if not number(ttft) or not number(rate) or ttft>600 or rate>100000:return
    row={'url':settings.url,'model':settings.model,'profile':settings.profile,'task':task,
         'at':time.time(),'first_reply_s':ttft,'tokens_per_second':rate,
         'residency':metrics.get('residency','unknown')}
    try:workspace_store.append('model-performance.json',row,limit=500)
    except (OSError,ValueError,TypeError,AttributeError):pass  # advisory metrics cannot break a completed answer


def estimates(settings,task):
    rows=workspace_store.read('model-performance.json',[])
    if not isinstance(rows,list):return {}
    grouped={};now=time.time()
    for row in rows:
        if not isinstance(row,dict):continue
        if not isinstance(row.get('model'),str):continue
        if row.get('url')!=settings.url or row.get('task')!=task or row.get('profile')!=settings.profile:continue
        if not number(row.get('at')) or not 0<=now-row['at']<=30*86400:continue
        if not all(number(row.get(key)) for key in ('first_reply_s','tokens_per_second')):continue
        grouped.setdefault(row.get('model'),[]).append(row)
    result={}
    for name,samples in grouped.items():
        # Compare observed warm runs when available, without mixing cold load time.
        warm=[row for row in samples if row.get('residency')=='loaded']
        selected=warm if len(warm)>=2 else samples
        if len(selected)<2:continue
        result[name]={'seconds':statistics.median(row['first_reply_s']+128/row['tokens_per_second'] for row in selected),
                      'samples':len(selected),'warm':len(warm)>=2}
    return result


def measured_order(rows,settings,task):
    measured=estimates(settings,task)
    eligible=[row for row in rows if row.get('fits_estimate')]
    if task=='code' and any(row.get('code_name') for row in eligible):
        eligible=[row for row in eligible if row.get('code_name')]
    measured_rows=[row for row in eligible if row['name'] in measured]
    if not measured_rows:return rows
    chosen=sorted(measured_rows,key=lambda row:measured[row['name']]['seconds'])
    return chosen+[row for row in rows if row not in chosen]
