"""Evaluate only a frozen, reviewed grounding set; never auto-score answer correctness."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hr_navigator.clients.api import APIConfig, HostedClient  # noqa: E402
from hr_navigator.retrieval.draft_review import draft_for_review  # noqa: E402
from hr_navigator.retrieval.embeddings import connect, embed_batches, read_vector  # noqa: E402
from hr_navigator.retrieval.search import search  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def combined_sha(paths):
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path).encode())
        digest.update(Path(path).read_bytes())
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--embedding-key-file', type=Path, required=True)
    parser.add_argument('--embedding-ca-file', type=Path, required=True)
    parser.add_argument('--embedding-base-url', required=True)
    parser.add_argument('--embedding-model', required=True)
    parser.add_argument('--chat-key-file', type=Path, required=True)
    parser.add_argument('--chat-ca-file', type=Path, required=True)
    parser.add_argument('--chat-base-url', required=True)
    parser.add_argument('--chat-model', required=True)
    parser.add_argument('--output', type=Path, default=Path('reports/grounding_fresh_v1_runs.jsonl'))
    args = parser.parse_args()
    frozen = Path('evaluation/grounding_fresh_v1.jsonl')
    checksum = Path('evaluation/grounding_fresh_v1.sha256')
    if not frozen.is_file() or not checksum.is_file():
        raise SystemExit('Reviewed grounding set is not frozen; no API calls were made')
    set_sha = sha(frozen)
    if set_sha != checksum.read_text().split()[0]:
        raise SystemExit('Frozen grounding set checksum mismatch')
    cases = [json.loads(line) for line in frozen.read_text().splitlines()]
    if len(cases) != 20 or any(c.get('review_status') != 'approved' or not c.get('reviewer') for c in cases):
        raise SystemExit('Frozen cases lack per-case reviewer approval')
    root = Path('data/processed/accepted_ocr')
    index_sha = combined_sha([root / 'manifest.json', root / 'pages.jsonl', root / 'chunks_350.jsonl'])
    workflow_sha = combined_sha(['src/hr_navigator/retrieval/draft_review.py',
                               'src/hr_navigator/retrieval/grounded.py',
                               'src/hr_navigator/retrieval/search.py'])
    chunks = [json.loads(line) for line in (root / 'chunks_350.jsonl').read_text().splitlines()]
    pages = {p['page_id']: p for p in (json.loads(line) for line in (root / 'pages.jsonl').read_text().splitlines())}
    cache_path = Path('data/indexes/accepted_ocr.sqlite')
    if not cache_path.is_file():
        raise SystemExit('Accepted-OCR embedding cache is missing')
    db = connect(cache_path)
    try:
        vectors = {c['chunk_id']: v for c in chunks
                   if (v := read_vector(db, args.embedding_model, c['text'])) is not None}
    finally:
        db.close()
    eligible = [c for c in chunks if c['language_heuristic'] == 'Latin (heuristic)']
    if not eligible or any(c['chunk_id'] not in vectors for c in eligible):
        raise SystemExit('Embedding cache incomplete for eligible corpus chunks')
    completed = set()
    if args.output.exists():
        for line in args.output.read_text().splitlines():
            row = json.loads(line)
            if (row['set_sha256'], row['index_sha256'], row['workflow_sha256'], row['chat_model'], row['embedding_model']) != (set_sha,index_sha,workflow_sha,args.chat_model,args.embedding_model):
                raise SystemExit('Existing run does not match current configuration')
            completed.add(row['case_id'])
    embedding = HostedClient(APIConfig(args.embedding_base_url,args.embedding_model,
                                       args.embedding_key_file.read_text().strip(),str(args.embedding_ca_file),90))
    chat = None
    query_db = None
    try:
        query_db = connect('data/indexes/grounding_fresh_queries.sqlite')
        embed_batches(embedding, [{'text': c['question']} for c in cases], query_db,
                      'configs/bge-small-en-v1.5-tokenizer.json')
        chat = HostedClient(APIConfig(args.chat_base_url,args.chat_model,
                                      args.chat_key_file.read_text().strip(),str(args.chat_ca_file),90))
        with args.output.open('a',encoding='utf-8') as out:
            for case in cases:
                if case['case_id'] in completed:
                    continue
                query = read_vector(query_db,args.embedding_model,case['question'])
                if query is None:
                    raise ValueError('Missing query embedding')
                start = time.monotonic()
                evidence = search(case['question'],chunks,vectors,query,top_k=5,mode='hybrid_rerank')
                targets=[(case['source_pdf_id'],case['pdf_page_number'])] + [
                    (source['source_pdf_id'],source['pdf_page_number'])
                    for source in case.get('additional_sources',[])]
                ranks=[next((i for i,c in enumerate(evidence,1)
                             if (c['source_pdf_id'],c['pdf_page_number']) == target),None)
                       for target in targets]
                rank=ranks[0]
                before=dict(chat.usage)
                result=draft_for_review(chat,case['question'],evidence,pages)
                usage={k:v-before.get(k,0) for k,v in chat.usage.items()}
                row={'case_id':case['case_id'],'set_sha256':set_sha,'index_sha256':index_sha,
                     'workflow_sha256':workflow_sha,'chat_model':args.chat_model,'embedding_model':args.embedding_model,
                     'expected_page_rank':rank,'expected_page_ranks':ranks,'result':result,'elapsed_seconds':round(time.monotonic()-start,3),
                     'usage':usage,'correctness':'not_scored'}
                out.write(json.dumps(row,ensure_ascii=False)+'\n')
                out.flush()
                print(case['case_id'],result['decision'],flush=True)
                time.sleep(1.05)
    finally:
        embedding.close()
        if query_db is not None:
            query_db.close()
        if chat is not None:
            chat.close()


if __name__ == '__main__':
    main()
