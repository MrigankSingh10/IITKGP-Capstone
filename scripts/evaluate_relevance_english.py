"""Offline English-only regression on the English slice of the existing frozen pilot."""
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

sys.path[:0] = ['src', 'scripts']
from evaluate_relevance_fresh import metrics  # noqa: E402
from hr_navigator.retrieval.search import english_eligible, search  # noqa: E402

f = Path('evaluation/relevance_assistant_v1.jsonl')
digest = hashlib.sha256(f.read_bytes()).hexdigest()
assert Path(str(f) + '.sha256').read_text().strip() == digest
all_cases = [json.loads(line) for line in f.read_text().splitlines()]
cases = [case for case in all_cases if case['query_language'] == 'English']
labels = [set(case['relevant_page_ids']) for case in cases]
out = {'frozen_sha256': digest, 'scope': 'English-labeled subset only; assistant-reviewed, incomplete labels; not independent',
       'selected_queries': len(cases), 'excluded_queries': len(all_cases) - len(cases), 'results': {}}
for size in (200, 350):
    path = Path(f'data/processed/accepted_ocr/chunks_{size}.jsonl')
    chunks = [json.loads(line) for line in path.read_text().splitlines()]
    ranks, times = [], []
    for case in cases:
        start = time.perf_counter()
        result = search(case['question'], chunks, top_k=10, mode='bm25')
        times.append(time.perf_counter() - start)
        ranks.append([item['page_id'] for item in result])
    out['results'][str(size)] = {**metrics(ranks, labels),
        'total_chunks': len(chunks), 'eligible_chunks': sum(english_eligible(c) for c in chunks),
        'chunk_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'mean_local_search_seconds': statistics.mean(times)}
Path('reports/relevance_english_scope_metrics.json').write_text(json.dumps(out, indent=2) + '\n')
print(json.dumps(out, indent=2))
