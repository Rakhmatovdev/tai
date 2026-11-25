"""Process-local payload counters; these are not billing measurements."""
import threading,time
_lock=threading.Lock();_started=time.monotonic()
_counts={'audio_sent':0,'audio_received':0,'chat_bytes':0,'chat_requests':0,'side_calls':0}
def add(key,value=1):
    with _lock:_counts[key]=_counts.get(key,0)+max(0,int(value))
def snapshot():
    with _lock:return {**_counts,'seconds':int(time.monotonic()-_started)}
