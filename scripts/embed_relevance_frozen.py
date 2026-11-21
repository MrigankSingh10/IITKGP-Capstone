"""Populate query-vector cache for a frozen relevance set only."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hr_navigator.clients.api import APIConfig, HostedClient  # noqa: E402
from hr_navigator.retrieval.embeddings import connect, embed_batches  # noqa: E402

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--frozen', type=Path, default=Path('evaluation/relevance_fresh_v1.jsonl'))
p.add_argument('--cache', type=Path, default=Path('data/indexes/accepted_ocr.sqlite'))
p.add_argument('--base-url', required=True)
p.add_argument('--model', required=True)
p.add_argument('--key-file', type=Path, required=True)
p.add_argument('--ca-file', type=Path, required=True)
a = p.parse_args()
hash_file = Path(str(a.frozen) + '.sha256')
if not a.frozen.is_file() or not hash_file.is_file() or hashlib.sha256(a.frozen.read_bytes()).hexdigest() != hash_file.read_text().strip():
    p.error('Frozen file and matching checksum required before embedding')
if not a.cache.is_file():
    p.error('Existing corpus cache required')
cases = [json.loads(x) for x in a.frozen.read_text().splitlines()]
client = HostedClient(APIConfig(a.base_url, a.model, a.key_file.read_text().strip(), str(a.ca_file), 90))
db = connect(a.cache)
try:
    embed_batches(client, [{'text': c['question']} for c in cases], db, 'configs/bge-small-en-v1.5-tokenizer.json')
finally:
    db.close()
    client.close()
