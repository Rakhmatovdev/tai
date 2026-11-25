"""Local conversation storage. No API keys, activity logs or network calls."""
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


class HistoryStore:
    def __init__(self, path=':memory:'):
        if str(path) != ':memory:':
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.create_function('brave_casefold', 1, lambda value: (value or '').casefold(), deterministic=True)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, updated TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS messages (
                seq INTEGER PRIMARY KEY, chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                role TEXT NOT NULL, body TEXT NOT NULL, stamp TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS messages_chat ON messages(chat_id,seq);
            CREATE TABLE IF NOT EXISTS chat_memory (
                chat_id TEXT PRIMARY KEY REFERENCES chats(id) ON DELETE CASCADE,
                summary TEXT NOT NULL DEFAULT '', pinned TEXT NOT NULL DEFAULT '',
                covered INTEGER NOT NULL DEFAULT 0, fingerprint TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS document_sources (
                id TEXT PRIMARY KEY, chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                label TEXT NOT NULL, path TEXT NOT NULL, excerpt TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS request_files (
                chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                message_index INTEGER NOT NULL, paths TEXT NOT NULL,
                PRIMARY KEY(chat_id,message_index));
            CREATE TABLE IF NOT EXISTS memory_progress (
                chat_id TEXT PRIMARY KEY REFERENCES chats(id) ON DELETE CASCADE,offset INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS memory_facts (
                id TEXT PRIMARY KEY,chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                kind TEXT NOT NULL,body TEXT NOT NULL,source_index INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS chat_branches (
                child TEXT PRIMARY KEY REFERENCES chats(id) ON DELETE CASCADE,
                parent TEXT REFERENCES chats(id) ON DELETE SET NULL,source_index INTEGER NOT NULL,
                model TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS chat_folders (id TEXT PRIMARY KEY,name TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS chat_organization (
                chat_id TEXT PRIMARY KEY REFERENCES chats(id) ON DELETE CASCADE,
                folder_id TEXT REFERENCES chat_folders(id) ON DELETE SET NULL,pinned INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS chat_tags (
                chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,tag TEXT NOT NULL,
                PRIMARY KEY(chat_id,tag));
            CREATE TABLE IF NOT EXISTS reply_metadata (
                seq INTEGER PRIMARY KEY REFERENCES messages(seq) ON DELETE CASCADE,
                model TEXT NOT NULL,profile TEXT NOT NULL,limited INTEGER NOT NULL DEFAULT 0);
        ''')

    @staticmethod
    def new_id():
        return uuid.uuid4().hex

    def append(self, chat_id, role, body, stamp):
        if role not in ('user','assistant') or not body.strip():
            return
        updated = datetime.now(timezone(timedelta(hours=5))).isoformat(timespec='seconds')
        title = ' '.join(body.split())[:70]
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO chats VALUES (?,?,?)',(chat_id,title,updated))
            if not self.db.execute('SELECT 1 FROM messages WHERE chat_id=? LIMIT 1',(chat_id,)).fetchone():
                self.db.execute('UPDATE chats SET title=? WHERE id=?',(title,chat_id))
            self.db.execute('INSERT INTO messages(chat_id,role,body,stamp) VALUES (?,?,?,?)',(chat_id,role,body,stamp))
            self.db.execute('UPDATE chats SET updated=? WHERE id=?',(updated,chat_id))

    def search(self, query='',folder_id=None,pinned_only=False,tag='',offset=0,limit=100):
        escaped = query.casefold().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        pattern = '%'+escaped+'%'
        clauses=["(brave_casefold(c.title) LIKE ? ESCAPE '\\' OR EXISTS (SELECT 1 FROM messages WHERE chat_id=c.id AND brave_casefold(body) LIKE ? ESCAPE '\\'))"]
        args=[pattern,pattern]
        if folder_id=='':clauses.append('o.folder_id IS NULL')
        elif folder_id is not None:clauses.append('o.folder_id=?');args.append(folder_id)
        if pinned_only:clauses.append('o.pinned=1')
        if tag:clauses.append('EXISTS (SELECT 1 FROM chat_tags WHERE chat_id=c.id AND brave_casefold(tag)=?)');args.append(tag.casefold())
        return self.db.execute('SELECT c.id,c.title,c.updated FROM chats c LEFT JOIN chat_organization o ON o.chat_id=c.id WHERE '
            +' AND '.join(clauses)+' ORDER BY COALESCE(o.pinned,0) DESC,c.updated DESC,c.id LIMIT ? OFFSET ?',
            (*args,max(1,min(100,int(limit))),max(0,int(offset)))).fetchall()

    def folders(self):return self.db.execute('SELECT id,name FROM chat_folders ORDER BY brave_casefold(name)').fetchall()

    def save_folder(self,name,identity=None):
        name=name.strip()
        if not 1<=len(name)<=40 or any(ord(char)<32 for char in name):raise ValueError('Papka nomi 1–40 belgi bo‘lsin.')
        if any(old!=identity and title.casefold()==name.casefold() for old,title in self.folders()):raise ValueError('Bunday papka mavjud.')
        if identity and not any(old==identity for old,_ in self.folders()):raise ValueError('Papka topilmadi.')
        if not identity and len(self.folders())>=30:raise ValueError('Ko‘pi bilan 30 ta papka yarating.')
        identity=identity or uuid.uuid4().hex
        with self.db:self.db.execute('INSERT INTO chat_folders VALUES (?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name',(identity,name))
        return identity

    def delete_folder(self,identity):
        with self.db:self.db.execute('DELETE FROM chat_folders WHERE id=?',(identity,))

    def chat_info(self,chat_id):
        row=self.db.execute('SELECT folder_id,pinned FROM chat_organization WHERE chat_id=?',(chat_id,)).fetchone()
        tags=[r[0] for r in self.db.execute('SELECT tag FROM chat_tags WHERE chat_id=? ORDER BY brave_casefold(tag)',(chat_id,))]
        return dict(folder_id=row[0] if row else None,pinned=bool(row and row[1]),tags=tags)

    def tags(self):return [r[0] for r in self.db.execute('SELECT min(tag) FROM chat_tags GROUP BY brave_casefold(tag) ORDER BY brave_casefold(tag)')]

    def organize(self,chat_id,folder_id=None,pinned=False,tags=()):
        if not self.db.execute('SELECT 1 FROM chats WHERE id=?',(chat_id,)).fetchone():raise ValueError('Suhbat topilmadi.')
        if folder_id and not any(identity==folder_id for identity,_ in self.folders()):raise ValueError('Papka topilmadi.')
        values={}
        for tag in tags:
            tag=tag.strip()
            if not 1<=len(tag)<=32 or ',' in tag or any(ord(char)<32 for char in tag):raise ValueError('Teg 1–32 belgi bo‘lsin, vergul ishlatmang.')
            values.setdefault(tag.casefold(),tag)
        if len(values)>8:raise ValueError('Bir suhbatga ko‘pi bilan 8 ta teg qo‘ying.')
        with self.db:
            self.db.execute('INSERT INTO chat_organization VALUES (?,?,?) ON CONFLICT(chat_id) DO UPDATE SET folder_id=excluded.folder_id,pinned=excluded.pinned',(chat_id,folder_id or None,int(bool(pinned))))
            self.db.execute('DELETE FROM chat_tags WHERE chat_id=?',(chat_id,))
            self.db.executemany('INSERT INTO chat_tags VALUES (?,?)',[(chat_id,tag) for tag in values.values()])

    def record_reply(self,chat_id,metrics):
        row=self.db.execute("SELECT seq FROM messages WHERE chat_id=? AND role='assistant' ORDER BY seq DESC LIMIT 1",(chat_id,)).fetchone()
        if row:
            with self.db:self.db.execute('INSERT OR REPLACE INTO reply_metadata VALUES (?,?,?,?)',
                (row[0],str(metrics.get('model',''))[:200],str(metrics.get('profile','balanced'))[:20],int(metrics.get('done_reason')=='length')))

    def continuation(self,chat_id):
        row=self.db.execute('''SELECT m.seq,m.body,r.model,r.profile,r.limited FROM messages m
            JOIN reply_metadata r ON r.seq=m.seq WHERE m.chat_id=? AND m.role='assistant' ORDER BY m.seq DESC LIMIT 1''',(chat_id,)).fetchone()
        latest=self.db.execute("SELECT seq FROM messages WHERE chat_id=? AND role='assistant' ORDER BY seq DESC LIMIT 1",(chat_id,)).fetchone()
        if not row or not latest or row[0]!=latest[0] or not row[4]:return None
        following=self.db.execute('SELECT role,body FROM messages WHERE chat_id=? AND seq>?',(chat_id,row[0])).fetchall()
        if any(role!='user' or body!='Davom ettir' for role,body in following):return None
        question=self.db.execute("SELECT body FROM messages WHERE chat_id=? AND role='user' AND seq<? AND body!='Davom ettir' ORDER BY seq DESC LIMIT 1",(chat_id,row[0])).fetchone()
        return dict(seq=row[0],answer=row[1],model=row[2],profile=row[3],question=question[0] if question else '')

    def messages(self, chat_id):
        return self.db.execute('SELECT role,body,stamp FROM messages WHERE chat_id=? ORDER BY seq',(chat_id,)).fetchall()

    def last_answer(self,chat_id):
        row=self.db.execute("SELECT body FROM messages WHERE chat_id=? AND role='assistant' ORDER BY seq DESC LIMIT 1",(chat_id,)).fetchone()
        return row[0] if row else ''

    def search_messages(self,chat_id,query,offset=0,limit=51):
        query=query.strip().casefold()
        if not query or len(query)>200:return []
        return self.db.execute('''SELECT seq,role,substr(body,max(1,instr(brave_casefold(body),?)-80),500),stamp
            FROM messages WHERE chat_id=? AND instr(brave_casefold(body),?)>0
            ORDER BY seq LIMIT ? OFFSET ?''',
            (query,chat_id,query,max(1,min(101,int(limit))),max(0,min(2147483647,int(offset))))).fetchall()

    def message_index(self,chat_id,seq):
        if not self.db.execute('SELECT 1 FROM messages WHERE chat_id=? AND seq=?',(chat_id,seq)).fetchone():return None
        return self.db.execute('SELECT count(*) FROM messages WHERE chat_id=? AND seq<?',(chat_id,seq)).fetchone()[0]

    def rename(self, chat_id, title):
        if title.strip():
            with self.db:
                self.db.execute('UPDATE chats SET title=? WHERE id=?',(title.strip()[:100],chat_id))

    def title(self,chat_id):
        row=self.db.execute('SELECT title FROM chats WHERE id=?',(chat_id,)).fetchone()
        return row[0] if row else ''

    def delete(self, chat_id):
        with self.db:
            self.db.execute('DELETE FROM chats WHERE id=?',(chat_id,))

    def close(self):
        self.db.close()

    def memory(self, chat_id):
        row = self.db.execute('SELECT summary,pinned,covered,fingerprint,enabled FROM chat_memory WHERE chat_id=?', (chat_id,)).fetchone()
        result = dict(zip(('summary','pinned','covered','fingerprint','enabled'), row)) if row else {
            'summary': '', 'pinned': '', 'covered': 0, 'fingerprint': '', 'enabled': True}
        progress=self.db.execute('SELECT offset FROM memory_progress WHERE chat_id=?',(chat_id,)).fetchone()
        result['offset']=progress[0] if progress else 0
        return result

    def save_memory(self, chat_id, memory):
        with self.db:
            # An empty current conversation can have pinned notes before its first send.
            self.db.execute('INSERT OR IGNORE INTO chats VALUES (?,?,?)', (chat_id, 'Brave', ''))
            self.db.execute('INSERT OR REPLACE INTO chat_memory VALUES (?,?,?,?,?,?)',
                (chat_id, memory['summary'][:1600], memory['pinned'][:1000], int(memory['covered']),
                 memory['fingerprint'], int(bool(memory['enabled']))))
            self.db.execute('INSERT OR REPLACE INTO memory_progress VALUES (?,?)',(chat_id,int(memory.get('offset',0))))

    def facts(self,chat_id):
        return self.db.execute('SELECT id,kind,body,source_index FROM memory_facts WHERE chat_id=? ORDER BY rowid',(chat_id,)).fetchall()

    def add_fact(self,chat_id,kind,body,index):
        if kind not in ('fact','decision','requirement','question') or not body.strip() or len(body)>1000:
            raise ValueError('Xotira yozuvi noto‘g‘ri.')
        if not 0<=index<self.count(chat_id):raise ValueError('Manba xabari topilmadi.')
        with self.db:self.db.execute('INSERT INTO memory_facts VALUES (?,?,?,?,?)',(uuid.uuid4().hex,chat_id,kind,body,index))

    def remove_fact(self,key):
        with self.db:self.db.execute('DELETE FROM memory_facts WHERE id=?',(key,))

    def count(self,chat_id):
        return self.db.execute('SELECT COUNT(*) FROM messages WHERE chat_id=?',(chat_id,)).fetchone()[0]

    def page(self,chat_id,offset=0,limit=60):
        return self.db.execute('SELECT role,body,stamp FROM messages WHERE chat_id=? ORDER BY seq LIMIT ? OFFSET ?',
            (chat_id,max(0,min(120,limit)),max(0,offset))).fetchall()

    def fork(self, chat_id, count):
        import re
        rows = self.messages(chat_id)[:max(0, count)]
        new_id = self.new_id()
        sources={};source_rows=[]
        for _,body,_ in rows:
            for key in re.findall(r'brave-source://([a-f0-9]{32})',body):
                source=self.source(key)
                if key not in sources and source:
                    sources[key]=uuid.uuid4().hex
                    source_rows.append((sources[key],new_id,source['label'],source['path'],source['text']))
        copied=[]
        for role, body, stamp in rows:
            for old,new in sources.items():body=body.replace('brave-source://'+old,'brave-source://'+new)
            copied.append((new_id,role,body,stamp))
        memory = self.memory(chat_id)
        files=self.db.execute('SELECT message_index,paths FROM request_files WHERE chat_id=? AND message_index<?',(chat_id,count)).fetchall()
        updated=datetime.now(timezone(timedelta(hours=5))).isoformat(timespec='seconds')
        title=' '.join(rows[0][1].split())[:70] if rows else 'Brave'
        with self.db:
            self.db.execute('INSERT INTO chats VALUES (?,?,?)',(new_id,title,updated))
            self.db.executemany('INSERT INTO document_sources VALUES (?,?,?,?,?)',source_rows)
            self.db.executemany('INSERT INTO messages(chat_id,role,body,stamp) VALUES (?,?,?,?)',copied)
            self.db.execute('INSERT INTO chat_memory VALUES (?,?,?,?,?,?)',(new_id,'',memory['pinned'],0,'',int(bool(memory['enabled']))))
            self.db.executemany('INSERT INTO request_files VALUES (?,?,?)',[(new_id,index,paths) for index,paths in files])
            self.db.execute('INSERT INTO chat_branches VALUES (?,?,?,?)',(new_id,chat_id,count,''))
            self.db.executemany('INSERT INTO memory_facts VALUES (?,?,?,?,?)',[
                (uuid.uuid4().hex,new_id,kind,body,index) for _,kind,body,index in self.facts(chat_id) if index<count])
            organization=self.chat_info(chat_id)
            self.db.execute('INSERT INTO chat_organization VALUES (?,?,0)',(new_id,organization['folder_id']))
            self.db.executemany('INSERT INTO chat_tags VALUES (?,?)',[(new_id,tag) for tag in organization['tags']])
            old_sequences=self.db.execute('SELECT seq FROM messages WHERE chat_id=? ORDER BY seq LIMIT ?',(chat_id,len(rows))).fetchall()
            new_sequences=self.db.execute('SELECT seq FROM messages WHERE chat_id=? ORDER BY seq',(new_id,)).fetchall()
            for (old,),(new,) in zip(old_sequences,new_sequences):
                self.db.execute('INSERT INTO reply_metadata SELECT ?,model,profile,limited FROM reply_metadata WHERE seq=?',(new,old))
        # Citation IDs remain valid in a branch; its source previews are immutable.
        return new_id

    def branches(self,chat_id):
        parent=self.db.execute('SELECT parent FROM chat_branches WHERE child=?',(chat_id,)).fetchone()
        root=parent[0] if parent and parent[0] else chat_id
        return self.db.execute('''SELECT c.id,c.title,b.source_index,b.model FROM chats c
            LEFT JOIN chat_branches b ON b.child=c.id WHERE c.id=? OR b.parent=? ORDER BY c.updated''',(root,root)).fetchall()

    def add_source(self, chat_id, source):
        key = uuid.uuid4().hex
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO chats VALUES (?,?,?)', (chat_id, 'Brave', ''))
            self.db.execute('INSERT INTO document_sources VALUES (?,?,?,?,?)',
                            (key, chat_id, source['label'], source['path'], source['text']))
        return key

    def source(self, key):
        row = self.db.execute('SELECT label,path,excerpt FROM document_sources WHERE id=?', (key,)).fetchone()
        return dict(zip(('label','path','text'), row)) if row else None

    def set_files(self,chat_id,index,paths):
        import json
        with self.db:self.db.execute('INSERT OR REPLACE INTO request_files VALUES (?,?,?)',(chat_id,index,json.dumps(paths)))

    def files(self,chat_id,index):
        import json
        row=self.db.execute('SELECT paths FROM request_files WHERE chat_id=? AND message_index=?',(chat_id,index)).fetchone()
        return json.loads(row[0]) if row else []
