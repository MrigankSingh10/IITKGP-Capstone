"""Incremental embedding cache with explicit vector and batch validation."""
import hashlib
import json
import sqlite3
import time

import numpy as np
from tokenizers import Tokenizer


def cache_key(model, text):
    return hashlib.sha256((model + '\0' + text).encode()).hexdigest()


def connect(path):
    db = sqlite3.connect(path)
    db.execute('CREATE TABLE IF NOT EXISTS vectors (key TEXT PRIMARY KEY, model TEXT NOT NULL, vector BLOB NOT NULL)')
    return db


def read_vector(db, model, text):
    row = db.execute('SELECT vector FROM vectors WHERE key=? AND model=?',
                     (cache_key(model, text), model)).fetchone()
    if row is None:
        return None
    vector = np.frombuffer(row[0], dtype='<f4').copy()
    if vector.shape != (384,) or not np.isfinite(vector).all():
        raise ValueError('Invalid cached vector')
    return vector


def embed_batches(client, chunks, db, tokenizer_path, batch_size=16, pause=0.1):
    if not 1 <= batch_size <= 16:
        raise ValueError('Batch size must be 1–16')
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    model = client.config.model
    pending = {}
    for c in chunks:
        text = c['text']
        if len(tokenizer.encode(text, add_special_tokens=True).ids) > 512:
            raise ValueError('Embedding input exceeds 512 tokens')
        key = cache_key(model, text)
        if key not in pending and read_vector(db, model, text) is None:
            pending[key] = text
    items = list(pending.items())
    for start in range(0, len(items), batch_size):
        batch = items[start:start + batch_size]
        response = client.embed([x[1] for x in batch])
        data = response.get('data', [])
        if len(data) != len(batch) or {item.get('index') for item in data} != set(range(len(batch))):
            raise ValueError('Embedding response index mismatch')
        vectors = sorted(data, key=lambda item: item['index'])
        with db:
            for (key, _), item in zip(batch, vectors):
                vector = np.asarray(item['embedding'], dtype='<f4')
                if vector.shape != (384,) or not np.isfinite(vector).all():
                    raise ValueError('Embedding dimension or values invalid')
                db.execute('INSERT OR REPLACE INTO vectors VALUES (?, ?, ?)', (key, model, vector.tobytes()))
        print(json.dumps({'completed': min(start + len(batch), len(items)), 'total': len(items)}), flush=True)
        if pause:
            time.sleep(pause)
