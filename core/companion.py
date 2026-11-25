"""Local preferences and explicitly configured voice routines."""
from core import workspace_store

DEFAULTS={'answer_length':'balanced','barge_in':True,'auto_recover':True}

def settings():
    raw=workspace_store.read('companion-settings.json',{})
    result={**DEFAULTS,**raw}
    if result['answer_length'] not in ('short','balanced','detailed'):result['answer_length']='balanced'
    return result

def save_settings(changes):
    workspace_store.update('companion-settings.json',lambda old:{**(old if isinstance(old,dict) else {}),**changes})

def routines():
    return workspace_store.read('routines.json',[])

def prompt():
    cfg=settings()
    length={'short':'Use concise answers, usually 1–3 sentences.','balanced':'Match the detail to the question.','detailed':'Give clear, thorough answers with steps when useful.'}[cfg['answer_length']]
    rows=['[USER CONVERSATION PREFERENCES]',length,'If the user says stop, to‘xta, bas, or стоп, stop the current response and task.']
    rows.append('When using web_search, include clickable source URLs from its result in the written answer and state the retrieval time when useful. Never invent sources or present retrieval as verification of truth.')
    for routine in routines():
        rows.append('User-configured routine '+repr(routine['name'])+': '+routine['steps'])
    rows.append('Run a routine only when the user requests its name or trigger. Use existing tools, respect local permissions, and report each result. Never claim an action succeeded before its tool result.')
    return '\n'.join(rows)
