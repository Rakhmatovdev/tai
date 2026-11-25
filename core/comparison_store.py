"""Bounded local comparison history. Loading records never starts inference."""
from datetime import datetime, timezone
import math
import uuid
from core import workspace_store
from core.ollama_chat import local_model

FILE='model-comparisons.json'
LIMIT=20


def validate(row):
    if not isinstance(row,dict):raise ValueError('Taqqoslash yozuvi noto‘g‘ri.')
    identity=row.get('id','');question=row.get('question','');created=row.get('created','')
    if not isinstance(identity,str) or len(identity)!=32 or any(c not in '0123456789abcdef' for c in identity):raise ValueError('Taqqoslash yozuvi noto‘g‘ri.')
    if not isinstance(question,str) or not 1<=len(question)<=6000 or not isinstance(created,str) or len(created)>40:raise ValueError('Taqqoslash yozuvi noto‘g‘ri.')
    if row.get('profile') not in ('economy','balanced','quality'):raise ValueError('Taqqoslash yozuvi noto‘g‘ri.')
    def pair(key):
        values=row.get(key)
        if not isinstance(values,list) or len(values)!=2:raise ValueError('Taqqoslash yozuvi noto‘g‘ri.')
        return values
    models=[local_model(value) for value in pair('models') if isinstance(value,str) and len(value)<=200]
    if len(models)!=2:raise ValueError('Taqqoslash yozuvi noto‘g‘ri.')
    results=pair('results');errors=pair('errors')
    if any(not isinstance(value,str) or len(value)>200000 for value in results) or not any(results):raise ValueError('Taqqoslash yozuvi noto‘g‘ri.')
    if any(not isinstance(value,str) or len(value)>2000 for value in errors):raise ValueError('Taqqoslash yozuvi noto‘g‘ri.')
    def number(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0
    durations=pair('durations')
    if not all(number(value) for value in durations):raise ValueError('Taqqoslash yozuvi noto‘g‘ri.')
    metrics=[]
    for value in pair('metrics'):
        if not isinstance(value,dict):raise ValueError('Taqqoslash yozuvi noto‘g‘ri.')
        clean={key:value[key] for key in ('first_reply_s','tokens_per_second') if number(value.get(key))}
        if value.get('done_reason') in ('length','stop'):clean['done_reason']=value['done_reason']
        metrics.append(clean)
    return dict(id=identity,question=question,created=created,profile=row['profile'],models=models,
                results=list(results),errors=list(errors),durations=list(durations),metrics=metrics)


def rows():
    raw=workspace_store.read(FILE,[])
    if not isinstance(raw,list):return []
    result=[];seen=set()
    for row in raw[:LIMIT]:
        try:value=validate(row)
        except (ValueError,TypeError):continue
        if value['id'] not in seen:result.append(value);seen.add(value['id'])
    return result


def save(record):
    value=validate(record)
    workspace_store.write(FILE,([value]+[row for row in rows() if row['id']!=value['id']])[:LIMIT])


def new_id():return uuid.uuid4().hex
def now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def delete(identity):workspace_store.write(FILE,[row for row in rows() if row['id']!=identity])
