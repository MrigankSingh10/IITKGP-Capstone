from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hr_navigator.ingestion.pages import build  # noqa: E402

print(json.dumps(build('reports/source_registry.jsonl', 'data/raw', 'data/processed',
                       'configs/bge-small-en-v1.5-tokenizer.json'), indent=2))
