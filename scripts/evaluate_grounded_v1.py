"""Review-only RAG run on previously used gold subset; no accuracy is auto-graded."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hr_navigator.clients.api import APIConfig, HostedClient  # noqa: E402
from hr_navigator.retrieval.draft_review import draft_for_review  # noqa: E402
from hr_navigator.retrieval.embeddings import connect, read_vector  # noqa: E402
from hr_navigator.retrieval.search import search  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('--key-file', type=Path, required=True)
parser.add_argument('--ca-file', type=Path, required=True)
parser.add_argument('--base-url', required=True)
parser.add_argument('--model', required=True)
parser.add_argument('--output', type=Path, default=Path('reports/grounded_v1_runs.jsonl'))
args = parser.parse_args()
gold_path = Path('evaluation/gold_v1.jsonl')
gold_sha = hashlib.sha256(gold_path.read_bytes()).hexdigest()
if gold_sha != Path('evaluation/gold_v1.sha256').read_text().split()[0]:
    raise SystemExit('Frozen gold checksum mismatch')
cases = {c['id']: c for c in map(json.loads, gold_path.read_text().splitlines())}
subset = json.loads(Path('reports/retrieval_accepted_ocr_metrics.json').read_text())['case_ids']
root = Path('data/processed/accepted_ocr')
manifest_sha = hashlib.sha256((root / 'manifest.json').read_bytes()).hexdigest()
chunks = [json.loads(line) for line in (root / 'chunks_350.jsonl').read_text().splitlines()]
pages = {p['page_id']: p for p in map(json.loads, (root / 'pages.jsonl').read_text().splitlines())}
db = connect('data/indexes/accepted_ocr.sqlite')
try:
    vectors = {c['chunk_id']: v for c in chunks if (v := read_vector(db, 'bge-small-en-v1.5', c['text'])) is not None}
    questions = {case_id: read_vector(db, 'bge-small-en-v1.5', cases[case_id]['question']) for case_id in subset}
finally:
    db.close()
if any(q is None for q in questions.values()):
    raise SystemExit('A cached question embedding is missing; build it before running')
done = set()
if args.output.exists():
    for line in args.output.read_text().splitlines():
        row = json.loads(line)
        if row['gold_sha256'] != gold_sha or row['index_manifest_sha256'] != manifest_sha or row['model'] != args.model:
            raise SystemExit('Existing results are for a different run configuration')
        done.add(row['case_id'])
client = HostedClient(APIConfig(args.base_url, args.model, args.key_file.read_text().strip(), str(args.ca_file), 90))
try:
    with args.output.open('a', encoding='utf-8') as f:
        for cid in subset:
            if cid in done:
                continue
            case = cases[cid]
            start = time.monotonic()
            evidence = search(case['question'], chunks, vectors, questions[cid], top_k=5, mode='hybrid_rerank')
            source = case['source']
            gold_id = (source['source_pdf_id'], source['pdf_page_number'])
            rank = next((i for i, c in enumerate(evidence, 1)
                         if (c['source_pdf_id'], c['pdf_page_number']) == gold_id), None)
            before = dict(client.usage)
            outcome = draft_for_review(client, case['question'], evidence, pages)
            usage = {k: v - before.get(k, 0) for k, v in client.usage.items()}
            row = {'case_id': cid, 'model': args.model, 'gold_sha256': gold_sha,
                   'index_manifest_sha256': manifest_sha, 'retrieval': '350-token hybrid + lexical rerank top-5',
                   'gold_page_rank': rank, 'evidence': [{'source_pdf_id': c['source_pdf_id'],
                      'pdf_page_number': c['pdf_page_number'], 'chunk_id': c['chunk_id']} for c in evidence],
                   'result': outcome, 'elapsed_seconds': round(time.monotonic() - start, 3), 'usage': usage}
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
            f.flush()
            print(cid, outcome['decision'], 'expected_page_rank', rank, flush=True)
            time.sleep(1.05)
finally:
    client.close()
