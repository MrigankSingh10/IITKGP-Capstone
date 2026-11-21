"""Score the fixed random-gold sample; only its exact questions may be embedded."""
import hashlib
import json
import sqlite3
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, 'src')
from hr_navigator.clients.api import APIConfig, HostedClient
from hr_navigator.retrieval.embeddings import connect, embed_batches, read_vector
from hr_navigator.retrieval.search import search

MODEL = 'bge-small-en-v1.5'
GOLD = Path('evaluation/gold_v1.jsonl')
PRIOR = Path('reports/random_gold_bm25_benchmark.json')
QUERY_CACHE = Path('data/indexes/random_gold_queries.sqlite')
OUT = Path('reports/random_gold_modes_benchmark.json')
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    return [json.loads(line) for line in p.read_text().splitlines()]

def main():
    prior = json.loads(PRIOR.read_text())
    assert prior['seed'] == 20261121 and prior['sample_size'] == 20
    assert sha(GOLD) == Path('evaluation/gold_v1.sha256').read_text().split()[0] == prior['gold_sha256']
    gold = {c['id']: c for c in read(GOLD)}
    ids = prior['sample_ids']
    assert len(ids) == len(set(ids)) == 20
    cases = [gold[i] for i in ids]
    for size in ('200', '350'):
        rows = prior['results'][size]['cases']
        assert [r['id'] for r in rows] == ids
        assert all(r['question'] == c['question'] and r['target_page'] == f"{c['source']['source_pdf_id']}:page_{c['source']['pdf_page_number']:04d}" for r, c in zip(rows, cases))
        assert sha(Path(f'data/processed/accepted_ocr/chunks_{size}.jsonl')) == prior['results'][size]['chunk_sha256']
    if '--embed' in sys.argv:
        db = connect(QUERY_CACHE)
        client = HostedClient(APIConfig('https://103.42.50.41:1035/v1', MODEL,
            Path('VM02_Embeddings_Access/shared-embedding-key.txt').read_text().strip(),
            'VM02_Embeddings_Access/vm02-ca.crt', 90))
        try:
            embed_batches(client, [{'text': c['question']} for c in cases], db,
                          'configs/bge-small-en-v1.5-tokenizer.json')
        finally:
            client.close(); db.close()
    db = sqlite3.connect(f'file:{Path("data/indexes/accepted_ocr.sqlite").resolve()}?mode=ro', uri=True)
    qdb = sqlite3.connect(f'file:{QUERY_CACHE.resolve()}?mode=ro', uri=True)
    try:
        queries = [read_vector(qdb, MODEL, c['question']) for c in cases]
        if any(q is None for q in queries):
            raise SystemExit('Missing query vectors; run with --embed first')
        out = {'seed': prior['seed'], 'sample_ids': ids, 'gold_sha256': sha(GOLD),
               'prior_benchmark_sha256': sha(PRIOR), 'model': MODEL,
               'label_limitations': prior['label_limitations'],
               'latency_scope': 'local search only; excludes query embedding, network and corpus/cache loading; single run per mode and query; end-to-end not measured', 'results': {}}
        modes = ('bm25', 'dense', 'hybrid', 'hybrid_rerank')
        for size in (200, 350):
            path = Path(f'data/processed/accepted_ocr/chunks_{size}.jsonl')
            chunks = read(path)
            vectors = {c['chunk_id']: v for c in chunks if (v := read_vector(db, MODEL, c['text'])) is not None}
            rows = []
            for i, (case, query) in enumerate(zip(cases, queries)):
                target = f"{case['source']['source_pdf_id']}:page_{case['source']['pdf_page_number']:04d}"
                row = {'id': case['id'], 'target_page': target}
                order = modes[i % 4:] + modes[:i % 4]
                for mode in order:
                    start = time.perf_counter()
                    kwargs = {} if mode == 'bm25' else {'vectors': vectors, 'query_vector': query}
                    pages = [r['page_id'] for r in search(case['question'], chunks, top_k=10, mode=mode, **kwargs)]
                    elapsed = time.perf_counter() - start
                    row[mode] = {'rank': pages.index(target) + 1 if target in pages else None, 'pages': pages, 'seconds': elapsed}
                rows.append(row)
                print(size, i + 1, case['id'], flush=True)
            summaries = {}
            for mode in modes:
                ranks = [r[mode]['rank'] for r in rows]
                summaries[mode] = {**{f'hit_at_{k}': sum(x is not None and x <= k for x in ranks) / len(ranks) for k in (3, 5, 10)},
                    'mrr_at_10': sum(1/x for x in ranks if x is not None) / len(ranks),
                    'mean_local_search_seconds': statistics.mean(r[mode]['seconds'] for r in rows)}
            out['results'][str(size)] = {'chunk_sha256': sha(path), 'cached_chunk_vectors': len(vectors), 'summary': summaries, 'cases': rows}
            OUT.write_text(json.dumps(out, indent=2) + '\n')
    finally:
        db.close(); qdb.close()
if __name__ == '__main__':
    main()
