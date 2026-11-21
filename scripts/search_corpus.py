"""Search page-traceable corpus; dense modes require the supplied embeddings API."""
import argparse
import json
from pathlib import Path
import sys

from tokenizers import Tokenizer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hr_navigator.clients.api import APIConfig, HostedClient  # noqa: E402
from hr_navigator.retrieval.embeddings import connect, read_vector  # noqa: E402
from hr_navigator.retrieval.search import search  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('query')
parser.add_argument('--mode', choices=['bm25', 'dense', 'hybrid', 'hybrid_rerank'], default='bm25')
parser.add_argument('--size', choices=[200, 350], type=int, default=350)
parser.add_argument('--code')
parser.add_argument('--data-dir', type=Path, default=Path('data/processed/accepted_ocr'))
parser.add_argument('--cache-file', type=Path, default=Path('data/indexes/accepted_ocr.sqlite'))
parser.add_argument('--key-file', type=Path)
parser.add_argument('--ca-file', type=Path)
parser.add_argument('--base-url')
parser.add_argument('--model')
args = parser.parse_args()
chunks = [json.loads(x) for x in (args.data_dir / f'chunks_{args.size}.jsonl').read_text().splitlines()]
vectors, query_vector = None, None
if args.mode != 'bm25':
    tokenizer = Tokenizer.from_file('configs/bge-small-en-v1.5-tokenizer.json')
    if len(tokenizer.encode(args.query, add_special_tokens=True).ids) > 512:
        parser.error('Question exceeds the embedding model token limit')
    if not all([args.key_file, args.ca_file, args.base_url, args.model]):
        parser.error('Dense retrieval requires key-file, ca-file, base-url and model')
    if not args.cache_file.is_file():
        parser.error('Embedding cache does not exist')
    db = connect(args.cache_file)
    try:
        vectors = {c['chunk_id']: v for c in chunks
                   if (v := read_vector(db, args.model, c['text'])) is not None}
    finally:
        db.close()
    client = HostedClient(APIConfig(args.base_url, args.model, args.key_file.read_text().strip(), str(args.ca_file)))
    try:
        data = client.embed([args.query])['data']
        if len(data) != 1 or data[0].get('index') != 0:
            raise ValueError('Invalid embedding response')
        query_vector = data[0]['embedding']
    finally:
        client.close()
results = search(args.query, chunks, vectors, query_vector, labour_code=args.code, mode=args.mode)
pages = {p['page_id']: p for p in (json.loads(line) for line in (args.data_dir / 'pages.jsonl').read_text().splitlines())}
for c in results:
    result = {k: c[k] for k in ('original_title', 'pdf_page_number', 'source_url',
                                  'source_pdf_id', 'scope', 'score', 'text', 'extraction_status')}
    result['source_warnings'] = pages[c['page_id']].get('source_warnings', [])
    print(json.dumps(result, ensure_ascii=False))
