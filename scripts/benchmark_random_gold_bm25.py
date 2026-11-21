"""Offline paired BM25 benchmark; sample fixed before any retrieval scoring."""
import hashlib
import json
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, 'src')
from hr_navigator.retrieval import search as s

SEED = 20261121
N = 20

def read(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def normal(q):
    return ' '.join(q.casefold().split())

gold_path = 'evaluation/gold_v1.jsonl'
assert sha(gold_path) == Path('evaluation/gold_v1.sha256').read_text().split()[0]
gold = read(gold_path)
prior_paths = ['evaluation/grounding_fresh_v1.jsonl', 'evaluation/relevance_assistant_v1.jsonl']
prior = {normal(c['question']) for path in prior_paths for c in read(path)}
pool = [c for c in gold if not c.get('conversation_context') and c.get('scope') == 'statutory'
        and c.get('source', {}).get('source_pdf_id') and c['source'].get('pdf_page_number')
        and not s.unsupported_query(c['question']) and normal(c['question']) not in prior]
assert len(pool) >= N
sample = random.Random(SEED).sample(pool, N)
print('seed', SEED, 'pool', len(pool), 'sample', [c['id'] for c in sample], flush=True)
out = {'seed': SEED, 'sample_size': N, 'pool_size': len(pool), 'gold_sha256': sha(gold_path),
       'prior_question_files_sha256': {p: sha(p) for p in prior_paths},
       'pool_ids': [c['id'] for c in pool], 'sample_ids': [c['id'] for c in sample],
       'method': 'statutory, English-supported, source-page labeled gold cases without conversation_context or exact casefolded whitespace-normalized prior development/pilot question; sample before scoring; same search top_k=10, English filter, page deduplication and instrument boost',
       'label_limitations': 'One cited target page per question, not exhaustive relevance judgments; frozen set approved as a whole, case review_status unreviewed, no individual legal expert review; concentrated sources/pages.',
       'latency_scope': 'local search only, includes filtering and BM25 tokenization; excludes corpus loading; alternating order; single run per query, no network', 'results': {}}
stop = s._QUERY_BOILERPLATE
for size in (200, 350):
    path = f'data/processed/accepted_ocr/chunks_{size}.jsonl'
    chunks = read(path)
    rows = []
    for i, c in enumerate(sample):
        target = f"{c['source']['source_pdf_id']}:page_{c['source']['pdf_page_number']:04d}"
        row = {'id': c['id'], 'question': c['question'], 'target_page': target}
        for mode in (('previous', 'shipped') if i % 2 == 0 else ('shipped', 'previous')):
            s._QUERY_BOILERPLATE = frozenset() if mode == 'previous' else stop
            start = time.perf_counter()
            pages = [x['page_id'] for x in s.search(c['question'], chunks, top_k=10, mode='bm25')]
            elapsed = time.perf_counter() - start
            row[mode] = {'rank': pages.index(target) + 1 if target in pages else None,
                         'pages': pages, 'seconds': elapsed}
        rows.append(row)
        print(size, i + 1, c['id'], row['previous']['rank'], row['shipped']['rank'], flush=True)
    def summary(mode):
        ranks = [r[mode]['rank'] for r in rows]
        return {**{f'hit_at_{k}': sum(x is not None and x <= k for x in ranks) / N for k in (3, 5, 10)},
                'mrr_at_10': sum(1/x for x in ranks if x is not None) / N,
                'mean_local_search_seconds': statistics.mean(r[mode]['seconds'] for r in rows)}
    paired = {}
    for k in (3, 5, 10):
        before = [r['previous']['rank'] is not None and r['previous']['rank'] <= k for r in rows]
        after = [r['shipped']['rank'] is not None and r['shipped']['rank'] <= k for r in rows]
        paired[f'hit_at_{k}'] = {'gains': sum(not a and b for a, b in zip(before, after)),
                                 'losses': sum(a and not b for a, b in zip(before, after))}
    rr = lambda rank: 1/rank if rank is not None else 0
    paired['reciprocal_rank'] = {'improved': sum(rr(r['shipped']['rank']) > rr(r['previous']['rank']) for r in rows),
                                  'worsened': sum(rr(r['shipped']['rank']) < rr(r['previous']['rank']) for r in rows),
                                  'unchanged': sum(rr(r['shipped']['rank']) == rr(r['previous']['rank']) for r in rows)}
    out['results'][str(size)] = {'chunk_sha256': sha(path), 'previous': summary('previous'), 'shipped': summary('shipped'), 'paired': paired, 'cases': rows}
    Path('reports/random_gold_bm25_benchmark.json').write_text(json.dumps(out, indent=2) + '\n')
s._QUERY_BOILERPLATE = stop
