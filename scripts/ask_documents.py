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
from hr_navigator.retrieval.search import search  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('question')
parser.add_argument('--code')
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
chunks = [json.loads(line) for line in Path('data/processed/chunks_350.jsonl').read_text().splitlines()]
pages = {p['page_id']: p for p in (json.loads(line) for line in Path('data/processed/pages.jsonl').read_text().splitlines())}
db = connect('data/indexes/embeddings.sqlite')
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
    print(json.dumps(answer_with_evidence(chat, args.question, evidence, pages), ensure_ascii=False, indent=2))
finally:
    embed.close()
    if chat:
        chat.close()
