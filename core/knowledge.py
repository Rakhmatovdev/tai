"""Versioned local document index. No scanning or model downloads are implicit."""
import hashlib
import json
import math
import sqlite3
import re
from dataclasses import replace
from pathlib import Path

from core import local_documents
from core.local_jobs import gate, Cancelled
from core.ollama_chat import OllamaClient, local_model

VERSION = 1


def digest(path, cancelled):
    result = hashlib.sha256()
    with Path(path).open('rb') as source:
        while block := source.read(262144):
            if cancelled.is_set():
                raise Cancelled('Bekor qilindi.')
            result.update(block)
    return result.hexdigest()


def embeddings(settings, model, texts, cancelled):
    if cancelled.is_set():
        raise Cancelled('Bekor qilindi.')
    client = OllamaClient(replace(settings, model=local_model(model)))
    try:
        # /show rejects remote/cloud metadata even for embedding-only models.
        info = client.describe()
        if info['capabilities'] and 'embedding' not in info['capabilities']:
            raise ValueError('Qidiruv uchun embedding modelini tanlang.')
        from core.local_http import embedding_request
        rows=embedding_request(settings.url,{'model': model, 'input': texts, 'truncate': False},cancelled).get('embeddings')
        if cancelled.is_set():
            raise Cancelled('Bekor qilindi.')
        if not isinstance(rows, list) or len(rows) != len(texts):
            raise ValueError('Embedding javobi noto‘g‘ri.')
        result = []
        for row in rows:
            if not isinstance(row, list) or not 1 <= len(row) <= 8192 or any(
                    type(v) not in (float, int) or not math.isfinite(v) for v in row):
                raise ValueError('Embedding javobi noto‘g‘ri.')
            norm = math.sqrt(sum(v*v for v in row))
            if not norm or not math.isfinite(norm):
                raise ValueError('Embedding bo‘sh.')
            result.append([v/norm for v in row])
        if len({len(row) for row in result}) != 1:
            raise ValueError('Embedding o‘lchamlari mos emas.')
        return result
    finally:
        client.close()


def model_stamp(settings,model):
    client=OllamaClient(replace(settings,model=model))
    try:
        with client.request('/api/tags') as response:rows=response.json().get('models',[])
        from core.ollama_chat import model_present
        for row in rows:
            if isinstance(row,dict) and model_present(model,[row.get('name','')]):
                value=row.get('digest','')
                return value if isinstance(value,str) and re.fullmatch(r'(sha256:)?[a-f0-9]{64}',value) else ''
        raise ValueError('Embedding modeli o‘rnatilmagan.')
    finally:client.close()


class KnowledgeStore:
    def __init__(self, path=None):
        if path is None:
            from core.workspace_store import directory
            path = directory()/'knowledge.sqlite3'
        self.db = sqlite3.connect(str(path), timeout=10)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS documents (
                path TEXT PRIMARY KEY, hash TEXT NOT NULL, version INTEGER NOT NULL,
                model TEXT NOT NULL, clipped INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS chunks (
                path TEXT NOT NULL REFERENCES documents(path) ON DELETE CASCADE,
                ordinal INTEGER NOT NULL, label TEXT NOT NULL, text TEXT NOT NULL,
                vector TEXT, PRIMARY KEY(path,ordinal));
        ''')
        if 'model_digest' not in {row[1] for row in self.db.execute('PRAGMA table_info(documents)')}:
            self.db.execute("ALTER TABLE documents ADD COLUMN model_digest TEXT NOT NULL DEFAULT ''")
            self.db.commit()

    def close(self):
        self.db.close()

    def list(self):
        return self.db.execute('''SELECT d.path,d.model,COUNT(c.ordinal),d.clipped
            FROM documents d LEFT JOIN chunks c ON c.path=d.path GROUP BY d.path ORDER BY d.path''').fetchall()

    def remove(self, paths):
        with self.db:
            self.db.executemany('DELETE FROM documents WHERE path=?', [(p,) for p in paths])

    def index(self, paths, settings, model, cancelled, progress=lambda value: None):
        paths = local_documents.validate_paths(paths)
        model = local_model(model) if model.strip() else ''
        stamp=model_stamp(settings,model) if model else ''
        for number, path in enumerate(paths):
            identity = digest(path, cancelled)
            existing = self.db.execute('SELECT hash,version,model,model_digest FROM documents WHERE path=?',(path,)).fetchone()
            if existing == (identity, VERSION, model,stamp):
                progress(f'{number+1}/{len(paths)} · {Path(path).name} · cached')
                continue
            progress(f'{number+1}/{len(paths)} · {Path(path).name}')
            chunks, clipped = local_documents.extract(path, cancelled)
            if len(chunks) > 3000:
                raise ValueError('Bitta hujjat uchun 3000 parchalik chegara oshdi.')
            vectors = []
            if model:
                for start in range(0, len(chunks), 8):
                    # Release between batches so foreground chat can take priority.
                    with gate.hold(cancelled, priority=10):
                        vectors.extend(embeddings(settings, model,
                            [row['text'] for row in chunks[start:start+8]], cancelled))
                    progress(f'{Path(path).name} · {min(start+8,len(chunks))}/{len(chunks)}')
            if cancelled.is_set():
                raise Cancelled('Bekor qilindi.')
            if digest(path, cancelled) != identity:
                raise ValueError('Fayl indekslash vaqtida o‘zgardi. Qayta urinib ko‘ring.')
            with self.db:
                self.db.execute('DELETE FROM documents WHERE path=?',(path,))
                self.db.execute('INSERT INTO documents VALUES (?,?,?,?,?,?)',(path,identity,VERSION,model,int(clipped),stamp))
                self.db.executemany('INSERT INTO chunks VALUES (?,?,?,?,?)', [
                    (path,i,row['label'],row['text'],json.dumps(vectors[i]) if model else None)
                    for i,row in enumerate(chunks)])

    def retrieve(self, paths, question, budget, cancelled, settings):
        chunks, semantic, queries, stamps, clipped = [], {}, {}, {}, False
        for path in local_documents.validate_paths(paths):
            record = self.db.execute('SELECT hash,version,model,clipped,model_digest FROM documents WHERE path=?',(path,)).fetchone()
            if not record or record[1] != VERSION or digest(path,cancelled) != record[0]:
                rows, cut = local_documents.extract(path,cancelled)
                chunks.extend(rows);clipped |= cut
                continue
            model = record[2];clipped |= bool(record[3])
            if model:
                if model not in queries:
                    stamps[model]=model_stamp(settings,model)
                    queries[model]=embeddings(settings,model,[question],cancelled)[0]
                if record[4] and stamps[model]!=record[4]:
                    raise ValueError('Qidiruv modeli o‘zgargan. Kutubxonani qayta indekslang.')
            for label,text,vector in self.db.execute('SELECT label,text,vector FROM chunks WHERE path=? ORDER BY ordinal',(path,)):
                if cancelled.is_set():raise Cancelled('Bekor qilindi.')
                if vector and model:
                    values=json.loads(vector);query=queries[model]
                    if len(values)!=len(query):raise ValueError('Qidiruv modeli o‘zgargan. Kutubxonani qayta indekslang.')
                    semantic[len(chunks)]=sum(a*b for a,b in zip(query,values))
                chunks.append({'path':path,'label':label,'text':text})
        return local_documents.rank(chunks,question,budget,semantic),clipped
