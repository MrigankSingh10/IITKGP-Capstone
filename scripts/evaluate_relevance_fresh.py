"""Freeze independent page judgments and score cached-vector retrieval offline."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hr_navigator.retrieval.embeddings import read_vector  # noqa: E402
from hr_navigator.retrieval.search import search  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(ranks, labels, k=10):
    return {'queries': len(ranks), 'hit_at_10': statistics.mean(bool(set(r[:k]) & g) for r, g in zip(ranks, labels)),
            'page_recall_at_10': statistics.mean(len(set(r[:k]) & g) / len(g) for r, g in zip(ranks, labels)),
            'mrr_at_10': statistics.mean(next((1 / i for i, p in enumerate(r[:k], 1) if p in g), 0) for r, g in zip(ranks, labels))}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    f = sub.add_parser('freeze')
    f.add_argument('--review', type=Path, default=Path('evaluation/relevance_fresh_review.csv'))
    f.add_argument('--pages', type=Path, default=Path('data/processed/accepted_ocr/pages.jsonl'))
    f.add_argument('--output', type=Path, default=Path('evaluation/relevance_fresh_v1.jsonl'))
    s = sub.add_parser('score')
    s.add_argument('--frozen', type=Path, default=Path('evaluation/relevance_fresh_v1.jsonl'))
    s.add_argument('--data-dir', type=Path, default=Path('data/processed/accepted_ocr'))
    s.add_argument('--cache', type=Path, default=Path('data/indexes/accepted_ocr.sqlite'))
    s.add_argument('--model', required=True)
    s.add_argument('--output', type=Path, default=Path('reports/relevance_fresh_metrics.json'))
    a = p.parse_args()
    if a.command == 'freeze':
        if a.output.exists() or Path(str(a.output) + '.sha256').exists():
            p.error('Freeze output or checksum already exists; choose a new version')
        pages = {json.loads(x)['page_id'] for x in a.pages.read_text().splitlines()}
        rows = list(csv.DictReader(a.review.open(encoding='utf-8-sig', newline='')))
        ids = set()
        for row in rows:
            labels = [x.strip() for x in row['relevant_page_ids'].split(';') if x.strip()]
            if (not row['case_id'].strip() or row['case_id'] in ids or not row['question'].strip()
                    or not row['query_language'].strip() or row['review_status'].strip().lower() != 'approved'
                    or not row['reviewer'].strip() or not labels or len(labels) != len(set(labels))
                    or not set(labels) <= pages):
                p.error(f"Invalid or incomplete review for {row['case_id']}; need unique valid pages and named approval")
            ids.add(row['case_id'])
            row['relevant_page_ids'] = labels
        if not rows:
            p.error('Empty review')
        a.output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        Path(str(a.output) + '.sha256').write_text(sha(a.output) + '\n')
        print(f'Frozen {len(rows)} cases: {sha(a.output)}')
        return
    digest = Path(str(a.frozen) + '.sha256')
    if not a.frozen.is_file() or not digest.is_file() or digest.read_text().strip() != sha(a.frozen):
        p.error('Frozen file and matching checksum required')
    cases = [json.loads(x) for x in a.frozen.read_text().splitlines()]
    if not a.cache.is_file():
        p.error('Embedding cache missing')
    db = sqlite3.connect(f'file:{a.cache.resolve()}?mode=ro', uri=True)
    try:
        queries = [read_vector(db, a.model, c['question']) for c in cases]
        if any(v is None for v in queries):
            p.error('Query vectors missing; populate cache only after freeze, then retry')
        out = {'frozen_sha256': sha(a.frozen), 'model': a.model,
               'latency_scope': 'local search only; excludes query embedding, network and setup; end-to-end not measured',
               'results': {}}
        labels = [set(c['relevant_page_ids']) for c in cases]
        for size in (200, 350):
            path = a.data_dir / f'chunks_{size}.jsonl'
            chunks = [json.loads(x) for x in path.read_text().splitlines()]
            vectors = {c['chunk_id']: v for c in chunks if (v := read_vector(db, a.model, c['text'])) is not None}
            for mode in ('bm25', 'dense', 'hybrid', 'hybrid_rerank'):
                ranks, times = [], []
                for case, q in zip(cases, queries):
                    start = time.perf_counter()
                    kw = {} if mode == 'bm25' else {'vectors': vectors, 'query_vector': q}
                    result = search(case['question'], chunks, top_k=10, mode=mode, **kw)
                    times.append(time.perf_counter() - start)
                    ranks.append([r['page_id'] for r in result])
                scores = metrics(ranks, labels)
                scores['mean_local_search_seconds'] = statistics.mean(times)
                scores['language_slices'] = {lang: metrics([r for r, c in zip(ranks, cases) if c['query_language'] == lang],
                    [g for g, c in zip(labels, cases) if c['query_language'] == lang]) for lang in sorted({c['query_language'] for c in cases})}
                out['results'][f'{size}_{mode}'] = scores
            out.setdefault('chunk_sha256', {})[str(size)] = sha(path)
            out.setdefault('cached_chunk_vectors', {})[str(size)] = len(vectors)
        a.output.write_text(json.dumps(out, indent=2) + '\n')
    finally:
        db.close()


if __name__ == '__main__':
    main()
