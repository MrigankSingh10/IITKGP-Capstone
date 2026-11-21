"""Build a separate accepted-OCR corpus and cache without overwriting prior data."""
import hashlib
import json
import os
import tempfile
from pathlib import Path
import sqlite3
import sys

from tokenizers import Tokenizer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hr_navigator.ingestion.pages import make_chunks, write_jsonl  # noqa: E402
from hr_navigator.retrieval.embeddings import cache_key, connect, read_vector  # noqa: E402

reviewed_path = Path('data/processed/pages_reviewed_ocr.jsonl')
pages = [json.loads(line) for line in reviewed_path.read_text().splitlines()]
if len(pages) != 1767 or len({p['page_id'] for p in pages}) != len(pages):
    raise ValueError('Unexpected page registry')
reviewed = [p for p in pages if p['extraction_status'] == 'ocr_reviewed']
if len(reviewed) != 11:
    raise ValueError('Expected 11 approved OCR pages')
folder = Path('data/processed/accepted_ocr')
folder.mkdir(parents=True, exist_ok=True)
write_jsonl(folder / 'pages.jsonl', pages)
tokenizer = Tokenizer.from_file('configs/bge-small-en-v1.5-tokenizer.json')
new_chunks = []
counts = {}
for size, overlap in ((200, 40), (350, 60)):
    chunks = [chunk for page in pages for chunk in make_chunks(page, tokenizer, size, overlap)]
    write_jsonl(folder / f'chunks_{size}.jsonl', chunks)
    new_chunks += [c for c in chunks if c['extraction_status'] == 'ocr_reviewed']
    counts[str(size)] = len(chunks)
cache = Path('data/indexes/accepted_ocr.sqlite')
cache.parent.mkdir(parents=True, exist_ok=True)
fd, temp_name = tempfile.mkstemp(prefix='accepted-ocr-', suffix='.sqlite', dir=cache.parent)
os.close(fd)
temp_cache = Path(temp_name)
try:
    source_db = sqlite3.connect('data/indexes/embeddings.sqlite')
    target_db = sqlite3.connect(temp_cache)
    try:
        source_db.backup(target_db)
        candidate_db = connect('data/indexes/ocr_candidate.sqlite')
        try:
            for c in new_chunks:
                v = read_vector(candidate_db, 'bge-small-en-v1.5', c['text'])
                if v is None:
                    raise ValueError('Missing candidate embedding')
                target_db.execute('INSERT OR IGNORE INTO vectors VALUES (?, ?, ?)',
                                  (cache_key('bge-small-en-v1.5', c['text']), 'bge-small-en-v1.5', v.astype('<f4').tobytes()))
            target_db.commit()
        finally:
            candidate_db.close()
    finally:
        source_db.close()
        target_db.close()
    os.replace(temp_cache, cache)
finally:
    temp_cache.unlink(missing_ok=True)
manifest = {'source_pdf_count': len({p['source_pdf_id'] for p in pages}),
            'page_document_count': len(pages), 'accepted_ocr_pages': len(reviewed),
            'chunk_counts': counts, 'reviewed_registry_sha256': hashlib.sha256(reviewed_path.read_bytes()).hexdigest(),
            'embedding_cache': 'data/indexes/accepted_ocr.sqlite',
            'warning': 'OCR is a transcription and needs source checking; legal applicability is unverified.'}
(folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest, indent=2))
