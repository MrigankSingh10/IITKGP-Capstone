"""Provisional frozen-gold cited-page retrieval check, not an exhaustive relevance assessment."""
import argparse
import json
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hr_navigator.clients.api import APIConfig, HostedClient  # noqa: E402
from hr_navigator.retrieval.embeddings import connect, embed_batches, read_vector  # noqa: E402
from hr_navigator.retrieval.search import search  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('--key-file', type=Path, required=True)
parser.add_argument('--ca-file', type=Path, required=True)
parser.add_argument('--base-url', required=True)
parser.add_argument('--model', required=True)
args = parser.parse_args()
all_cases = [json.loads(x) for x in Path('evaluation/gold_v1.jsonl').read_text().splitlines()]
single = [c for c in all_cases if 'conversation_context' not in c]
cases = [single[i] for i in range(0, len(single), 4)]
db = connect('data/indexes/embeddings.sqlite')
client = HostedClient(APIConfig(args.base_url, args.model, args.key_file.read_text().strip(), str(args.ca_file), 90))
try:
    embed_batches(client, [{'text': c['question']} for c in cases], db,
                  'configs/bge-small-en-v1.5-tokenizer.json')
    qs = {c['id']: read_vector(db, args.model, c['question']) for c in cases}
    all_results = {}
    for size in (200, 350):
        chunks = [json.loads(x) for x in Path(f'data/processed/chunks_{size}.jsonl').read_text().splitlines()]
        vectors = {c['chunk_id']: v for c in chunks
                   if (v := read_vector(db, args.model, c['text'])) is not None}
        for mode in ('bm25', 'dense', 'hybrid', 'hybrid_rerank'):
            ranks, times = [], []
            for case in cases:
                start = time.perf_counter()
                kwargs = {} if mode == 'bm25' else {'vectors': vectors, 'query_vector': qs[case['id']]}
                results = search(case['question'], chunks, top_k=10, mode=mode, **kwargs)
                times.append(time.perf_counter() - start)
                source = case['source']
                correct = (source['source_pdf_id'], source['pdf_page_number'])
                rank = next((i for i, c in enumerate(results, 1)
                             if (c['source_pdf_id'], c['pdf_page_number']) == correct), None)
                ranks.append(rank)
            all_results[f'{size}_{mode}'] = {
                'queries': len(cases),
                **{f'recall_at_{k}': sum(r is not None and r <= k for r in ranks) / len(ranks)
                   for k in (3, 5, 10)},
                'mrr_at_10': sum(1 / r if r else 0 for r in ranks) / len(ranks),
                'mean_search_seconds': statistics.mean(times), 'ranks': ranks}
            print(size, mode, 'complete', flush=True)
    result = {'scope': 'provisional: one cited gold page per question, not exhaustive relevance labels',
              'case_ids': [c['id'] for c in cases], 'results': all_results}
    Path('reports/retrieval_v1_metrics.json').write_text(json.dumps(result, indent=2) + '\n')
finally:
    client.close()
    db.close()
