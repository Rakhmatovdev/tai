"""Bounded user-defined prompt commands. No actions, imports or evaluation."""
import re
from dataclasses import replace
from core import workspace_store

FILE='custom-commands.json'


def validate(name,title,template,model='',profile=''):
    from core.slash_commands import INDEX,ALIASES
    from core.ollama_chat import local_model
    name=name.strip().lstrip('/').lower();title=title.strip();template=template.strip();model=model.strip()
    if not re.fullmatch(r'[a-z][a-z0-9_]{1,23}',name):raise ValueError('Buyruq nomi: 2–24 ta lotin harfi, raqam yoki _.')
    if name in INDEX or name in ALIASES:raise ValueError('Bu buyruq nomi band.')
    if not 1<=len(title)<=80 or not 1<=len(template)<=10000:raise ValueError('Sarlavha 1–80, prompt 1–10000 belgi bo‘lsin.')
    if profile not in ('','auto','economy','balanced','quality'):raise ValueError('Noto‘g‘ri resurs profili.')
    if model:model=local_model(model)
    return dict(name=name,title=title,template=template,model=model,profile=profile)


def rows():
    raw=workspace_store.read(FILE,[]);result=[];seen=set()
    if not isinstance(raw,list):return []
    for row in raw[:100]:
        if not isinstance(row,dict):continue
        try:value=validate(**{key:row.get(key,'') for key in ('name','title','template','model','profile')})
        except (TypeError,AttributeError,ValueError):continue
        if value['name'] not in seen:result.append(value);seen.add(value['name'])
    return result[:50]


def save(old_name='',**values):
    value=validate(**values);current=rows()
    if any(row['name']==value['name'] and row['name']!=old_name for row in current):raise ValueError('Bu buyruq nomi band.')
    current=[row for row in current if row['name']!=old_name]
    if len(current)>=50:raise ValueError('Ko‘pi bilan 50 ta shaxsiy buyruq saqlang.')
    workspace_store.write(FILE,current+[value]);return value['name']


def delete(name):workspace_store.write(FILE,[row for row in rows() if row['name']!=name])


def commands():
    from core.slash_commands import Command
    return tuple(Command(row['name'],row['title'],instruction='Follow the user-defined task below. Do not claim to execute code or external actions.',
                         template=row['template'],model=row['model'],profile=row['profile']) for row in rows())


def render(command,body):
    if not command or not command.template:return body
    if '{input}' in command.template and not body.strip():raise ValueError('Buyruqdan keyin savol yoki topshiriq yozing.')
    result=command.template.replace('{input}',body) if '{input}' in command.template else command.template+('\n\n'+body if body else '')
    if len(result)>12000:raise ValueError('Shaxsiy buyruq matni 12000 belgidan oshmasin.')
    return result


def request_settings(settings,command):
    if not command or not command.template:return settings
    return replace(settings,model=command.model or settings.model,profile=command.profile or settings.profile)
