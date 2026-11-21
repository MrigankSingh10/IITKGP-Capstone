"""Local development smoke test; not an independently reviewed retrieval benchmark."""
import json
from pathlib import Path
import time
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hr_navigator.retrieval.search import search  # noqa: E402

candidate_root = Path('data/processed/ocr_candidate')
manifest = json.loads((candidate_root / 'manifest.json').read_text())
if manifest['status'] != 'unverified_candidate_do_not_use_for_legal_answers':
    raise ValueError('Not an isolated OCR candidate corpus')
base = [json.loads(x) for x in Path('data/processed/chunks_350.jsonl').read_text().splitlines()]
candidate = [json.loads(x) for x in (candidate_root / 'chunks_350.jsonl').read_text().splitlines()]
new = [json.loads(x) for x in (candidate_root / 'new_chunks_350.jsonl').read_text().splitlines()]
source_id = new[0]['source_pdf_id']
queries = [
    (3, 'annexure appropriate government rules nomination fresh nomination'),
    (5, 'central government rules registration establishment cancellation closure'),
    (6, 'NSSB term of office committee transaction of business'),
    (8, 'Gig Platform Workers smooth functioning social security schemes'),
    (9, 'arrangements other countries transfer money paid compensation'),
    (11, 'central government schemes gig workers life disability accident insurance'),
]
results = []
for expected_page, query in queries:
    row = {'expected_source_pdf_id': source_id, 'expected_pdf_page': expected_page, 'query': query}
    for name, chunks in (('original', base), ('ocr_candidate', candidate)):
        start = time.perf_counter()
        found = search(query, chunks, top_k=10, mode='bm25', labour_code='Code on Social Security')
        rank = next((n for n, c in enumerate(found, 1)
                     if c['source_pdf_id'] == source_id and c['pdf_page_number'] == expected_page), None)
        row[name] = {'rank_at_10': rank, 'elapsed_seconds': round(time.perf_counter() - start, 3)}
    results.append(row)
result = {'status': 'internal integration smoke test; queries selected with knowledge of pages, not a benchmark',
          'results': results}
Path('reports/ocr_candidate_smoke.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
