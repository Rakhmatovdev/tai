"""Atomic local meeting drafts; never store raw microphone audio."""
import time
import uuid
import math
from core import workspace_store


def sessions():
    rows=workspace_store.read('meeting-drafts.json',[])
    if not isinstance(rows,list):return []
    return [row for row in rows if isinstance(row,dict) and isinstance(row.get('id'),str)
            and isinstance(row.get('transcript'),str) and len(row['transcript'])<=160000
            and type(row.get('updated')) in (int,float) and math.isfinite(row['updated'])
            and 0<=row['updated']<=time.time()+86400
            and all(isinstance(row.get(key,''),str) for key in ('path','notes','answer','language'))][-10:]


def save(identity,transcript,*,language='auto',diarize=False,notes='',answer='',path='',recording=False):
    if not isinstance(transcript,str) or len(transcript)>160000:raise ValueError('Transkript chegarasiga yetdi.')
    identity=identity or uuid.uuid4().hex
    value={'id':identity,'transcript':transcript,'language':language,'diarize':bool(diarize),
           'notes':str(notes)[:160000],'answer':str(answer)[:160000],'path':str(path)[:2000],
           'recording':bool(recording),'updated':time.time()}
    rows=[row for row in sessions() if row['id']!=identity]
    workspace_store.write('meeting-drafts.json',(rows+[value])[-10:]);return identity


def delete(identity):
    workspace_store.write('meeting-drafts.json',[row for row in sessions() if row['id']!=identity])
