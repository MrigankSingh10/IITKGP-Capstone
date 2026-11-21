"""Experimental document-grounded question, using local retrieval and supplied APIs."""
import argparse
import json
from pathlib import Path
import sys

from tokenizers import Tokenizer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hr_navigator.clients.api import APIConfig, HostedClient  # noqa: E402
from hr_navigator.retrieval.embeddings import connect, read_vector  # noqa: E402
from hr_navigator.retrieval.grounded import answer_with_evidence  # noqa: E402
from hr_navigator.retrieval.draft_review import draft_for_review  # noqa: E402
from hr_navigator.retrieval.search import search  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('question')
parser.add_argument('--code')
parser.add_argument('--draft-for-review', action='store_true', help='Show an unverified model-checked draft requiring human review')
parser.add_argument('--data-dir', type=Path, default=Path('data/processed/accepted_ocr'))
parser.add_argument('--cache-file', type=Path, default=Path('data/indexes/accepted_ocr.sqlite'))
parser.add_argument('--embedding-key-file', required=True, type=Path)
parser.add_argument('--embedding-ca-file', required=True, type=Path)
parser.add_argument('--embedding-base-url', required=True)
parser.add_argument('--embedding-model', required=True)
parser.add_argument('--chat-key-file', required=True, type=Path)
parser.add_argument('--chat-ca-file', required=True, type=Path)
parser.add_argument('--chat-base-url', required=True)
parser.add_argument('--chat-model', required=True)
args = parser.parse_args()
tokenizer = Tokenizer.from_file('configs/bge-small-en-v1.5-tokenizer.json')
if len(tokenizer.encode(args.question, add_special_tokens=True).ids) > 512:
    parser.error('Question exceeds the embedding model token limit')
chunks = [json.loads(line) for line in (args.data_dir / 'chunks_350.jsonl').read_text().splitlines()]
pages = {p['page_id']: p for p in (json.loads(line) for line in (args.data_dir / 'pages.jsonl').read_text().splitlines())}
if not args.cache_file.is_file():
    parser.error('Embedding cache does not exist')
db = connect(args.cache_file)
try:
    vectors = {c['chunk_id']: v for c in chunks
               if (v := read_vector(db, args.embedding_model, c['text'])) is not None}
finally:
    db.close()
embed = HostedClient(APIConfig(args.embedding_base_url, args.embedding_model,
                              args.embedding_key_file.read_text().strip(), str(args.embedding_ca_file)))
chat = None
try:
    response = embed.embed([args.question])
    data = response['data']
    if len(data) != 1 or data[0]['index'] != 0:
        raise ValueError('Invalid embedding response')
    evidence = search(args.question, chunks, vectors, data[0]['embedding'],
                      labour_code=args.code, top_k=3, mode='hybrid_rerank')
    chat = HostedClient(APIConfig(args.chat_base_url, args.chat_model,
                                  args.chat_key_file.read_text().strip(), str(args.chat_ca_file)))
    result = (draft_for_review(chat, args.question, evidence, pages) if args.draft_for_review
              else answer_with_evidence(chat, args.question, evidence, pages))
    print(json.dumps(result, ensure_ascii=False, indent=2))
finally:
    embed.close()
    if chat:
        chat.close()
