"""Make a separate page registry from explicitly approved OCR review rows."""
import csv
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hr_navigator.ingestion.audit import language  # noqa: E402
from hr_navigator.ingestion.pages import write_jsonl  # noqa: E402

review_path = Path('reports/sparse_ocr_review_readable.csv')
rows = list(csv.DictReader(review_path.open(encoding='utf-8', newline='')))
ids = [row['page_id'] for row in rows]
if len(ids) != len(set(ids)):
    raise ValueError('Duplicate OCR review page ID')
approved = {row['page_id']: row for row in rows if row['review_status'].strip().lower() == 'approved'}
for row in approved.values():
    if not row['reviewer'].strip() or not row['ocr_text'].strip():
        raise ValueError('Approved OCR requires a reviewer and nonempty text')
pages = [json.loads(line) for line in Path('data/processed/pages.jsonl').read_text().splitlines()]
by_id = {p['page_id']: p for p in pages}
if not set(approved).issubset(by_id):
    raise ValueError('OCR review references an unknown page')
for page_id, row in approved.items():
    page = by_id[page_id]
    if page['extraction_status'] != 'sparse':
        raise ValueError('OCR review is only applicable to sparse pages')
    page['native_text'] = page['text']
    page['text'] = row['ocr_text']
    page['character_count'] = len(page['text'].strip())
    page['language_heuristic'] = language(page['text'])
    page['extraction_status'] = 'ocr_reviewed'
    page['ocr_reviewer'] = row['reviewer'].strip()
write_jsonl('data/processed/pages_reviewed_ocr.jsonl', pages)
print(f'Wrote {len(pages)} pages with {len(approved)} reviewed OCR replacements; indexes not changed.')
