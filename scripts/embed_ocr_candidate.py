"""Embed only isolated OCR candidate chunks into a separate test cache."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hr_navigator.clients.api import APIConfig, HostedClient  # noqa: E402
from hr_navigator.retrieval.embeddings import connect, embed_batches  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('--key-file', required=True, type=Path)
parser.add_argument('--ca-file', required=True, type=Path)
parser.add_argument('--base-url', required=True)
parser.add_argument('--model', required=True)
args = parser.parse_args()
chunks = []
for size in (200, 350):
    chunks += [json.loads(line) for line in Path(f'data/processed/ocr_candidate/new_chunks_{size}.jsonl').read_text().splitlines()]
chunks = [c for c in chunks if c['language_heuristic'] == 'Latin (heuristic)']
db = connect('data/indexes/ocr_candidate.sqlite')
client = HostedClient(APIConfig(args.base_url, args.model, args.key_file.read_text().strip(), str(args.ca_file), 90))
try:
    embed_batches(client, chunks, db, 'configs/bge-small-en-v1.5-tokenizer.json')
finally:
    client.close()
    db.close()
