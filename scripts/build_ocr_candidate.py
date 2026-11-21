"""Build isolated, unapproved OCR test corpus; never change production data or indexes."""
import csv
import hashlib
import json
from pathlib import Path
import sys

from tokenizers import Tokenizer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hr_navigator.ingestion.audit import language  # noqa: E402
from hr_navigator.ingestion.pages import make_chunks, write_jsonl  # noqa: E402

review_path = Path('reports/sparse_ocr_review_readable.csv')
with review_path.open(encoding='utf-8-sig', newline='') as f:
    rows = list(csv.DictReader(f))
ids = [r['page_id'] for r in rows]
if len(ids) != len(set(ids)):
    raise ValueError('Duplicate review page IDs')
candidates = {r['page_id']: r for r in rows if r['review_status'] in ('reviewed_user_provided', 'approved')}
if len(candidates) != 11:
    raise ValueError('Expected 11 reviewed or approved OCR candidates; inspect review sheet')
pages = [json.loads(line) for line in Path('data/processed/pages.jsonl').read_text().splitlines()]
by_id = {p['page_id']: p for p in pages}
if not set(candidates).issubset(by_id):
    raise ValueError('Unknown candidate page')
for key, row in candidates.items():
    page = by_id[key]
    if page['extraction_status'] != 'sparse' or not row['ocr_text'].strip():
        raise ValueError('Invalid candidate page or empty OCR text')
    page['native_text'] = page['text']
    page['text'] = row['ocr_text']
    page['character_count'] = len(page['text'].strip())
    page['language_heuristic'] = language(page['text'])
    page['extraction_status'] = 'ocr_candidate_unverified'
    page['ocr_review_status'] = row['review_status']
    page['source_warnings'] = [
        'OCR transcription is unverified against the source; do not treat it as an exact quotation.',
        row.get('notes', ''),
    ]
    page['ocr_source_sha256'] = hashlib.sha256(row['ocr_text'].encode()).hexdigest()
folder = Path('data/processed/ocr_candidate')
folder.mkdir(parents=True, exist_ok=True)
write_jsonl(folder / 'pages.jsonl', pages)
tokenizer = Tokenizer.from_file('configs/bge-small-en-v1.5-tokenizer.json')
counts = {}
for size, overlap in ((200, 40), (350, 60)):
    candidate_chunks = [c for page in pages if page['page_id'] in candidates
                        for c in make_chunks(page, tokenizer, size, overlap)]
    write_jsonl(folder / f'new_chunks_{size}.jsonl', candidate_chunks)
    base = [json.loads(line) for line in Path(f'data/processed/chunks_{size}.jsonl').read_text().splitlines()]
    all_chunks = [c for c in base if c['page_id'] not in candidates] + candidate_chunks
    write_jsonl(folder / f'chunks_{size}.jsonl', all_chunks)
    counts[str(size)] = {'all_chunks': len(all_chunks), 'new_ocr_chunks': len(candidate_chunks)}
manifest = {'status': 'unverified_candidate_do_not_use_for_legal_answers',
            'review_sheet_sha256': hashlib.sha256(review_path.read_bytes()).hexdigest(),
            'source_pdf_count': len({p['source_pdf_id'] for p in pages}),
            'page_document_count': len(pages), 'candidate_ocr_page_count': len(candidates),
            'chunks': counts}
(folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest, indent=2))
