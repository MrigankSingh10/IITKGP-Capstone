import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hr_navigator.clients.api import APIConfig, HostedClient  # noqa: E402
from hr_navigator.retrieval.embeddings import connect, embed_batches  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('--key-file', type=Path, required=True)
parser.add_argument('--ca-file', type=Path, required=True)
parser.add_argument('--base-url', required=True)
parser.add_argument('--model', required=True)
args = parser.parse_args()
chunks = []
for size in (200, 350):
    for line in Path(f'data/processed/chunks_{size}.jsonl').read_text().splitlines():
        chunk = json.loads(line)
        if chunk['language_heuristic'] == 'Latin (heuristic)':
            chunks.append(chunk)
Path('data/indexes').mkdir(parents=True, exist_ok=True)
db = connect('data/indexes/embeddings.sqlite')
client = HostedClient(APIConfig(args.base_url, args.model, args.key_file.read_text().strip(), str(args.ca_file), 90))
try:
    embed_batches(client, chunks, db, 'configs/bge-small-en-v1.5-tokenizer.json')
finally:
    client.close()
    db.close()
