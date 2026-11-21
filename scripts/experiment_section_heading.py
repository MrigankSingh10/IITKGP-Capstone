"""Compare explicit section-heading ranking on local development data only."""
import json
import statistics
import sys
sys.path[:0] = ['src', 'scripts']
from hr_navigator.retrieval import search as s

cases = [json.loads(x) for x in open('evaluation/grounding_fresh_v1.jsonl')]
cases = [c for c in cases if c.get('source_pdf_id') and c.get('pdf_page_number') and c.get('expected_decision') == 'review_required']
match = s.section_heading_matches
for size in (200, 350):
    chunks = [json.loads(x) for x in open(f'data/processed/accepted_ocr/chunks_{size}.jsonl')]
    labels = [f"{c['source_pdf_id']}:page_{c['pdf_page_number']:04d}" for c in cases]
    for name, function in [('baseline', lambda q, c: set()), ('section_heading', match)]:
        s.section_heading_matches = function
        ranks = [[x['page_id'] for x in s.search(c['question'], chunks, top_k=10, mode='bm25')] for c in cases]
        positions = [r.index(label) + 1 if label in r else None for r, label in zip(ranks, labels)]
        scores = {f'hit_at_{k}': statistics.mean(p is not None and p <= k for p in positions) for k in (3, 5, 10)}
        scores['mrr_at_10'] = statistics.mean(1 / p if p else 0 for p in positions)
        print(size, name, scores, flush=True)
s.section_heading_matches = match
