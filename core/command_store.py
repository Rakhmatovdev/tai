"""Local command-name preferences and editable prompt templates; no executions."""
import uuid
from core import workspace_store
from core.slash_commands import registry


def preferences():
    known=registry()
    raw=workspace_store.read('slash-preferences.json',{})
    if not isinstance(raw,dict):raw={}
    def names(key,limit):
        value=raw.get(key,[])
        return list(dict.fromkeys(item for item in value if isinstance(item,str) and item in known))[:limit] if isinstance(value,list) else []
    return {'favorites':names('favorites',20),'recent':names('recent',12)}


def used(name):
    if name not in registry():return
    value=preferences();value['recent']=[name]+[item for item in value['recent'] if item!=name]
    value['recent']=value['recent'][:12]
    try:workspace_store.write('slash-preferences.json',value)
    except OSError:pass


def favorite(name):
    if name not in registry():raise ValueError('Noma’lum buyruq.')
    value=preferences();rows=value['favorites']
    if name in rows:rows.remove(name)
    elif len(rows)<20:rows.append(name)
    else:raise ValueError('Ko‘pi bilan 20 ta saralangan buyruq saqlang.')
    workspace_store.write('slash-preferences.json',value)


def snippets():
    rows=workspace_store.read('prompt-snippets.json',[])
    if not isinstance(rows,list):return []
    return [row for row in rows if isinstance(row,dict) and all(isinstance(row.get(key),str) for key in ('id','title','text'))
            and 1<=len(row['title'])<=80 and 1<=len(row['text'])<=10000][:30]


def save_snippet(identity,title,text):
    title,text=title.strip(),text.strip()
    if not 1<=len(title)<=80 or not 1<=len(text)<=10000:raise ValueError('Sarlavha 1–80, prompt 1–10000 belgi bo‘lsin.')
    rows=snippets();identity=identity or uuid.uuid4().hex
    if not any(row['id']==identity for row in rows) and len(rows)>=30:raise ValueError('Ko‘pi bilan 30 ta prompt shabloni saqlang.')
    rows=[row for row in rows if row['id']!=identity]+[{'id':identity,'title':title,'text':text}]
    workspace_store.write('prompt-snippets.json',rows);return identity


def delete_snippet(identity):workspace_store.write('prompt-snippets.json',[row for row in snippets() if row['id']!=identity])
