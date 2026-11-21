"""Search local documents and return untrusted passages, without generating an answer."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hr_navigator.retrieval.grounded import extractive_evidence  # noqa: E402
from hr_navigator.retrieval.search import search  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('question')
parser.add_argument('--code')
parser.add_argument('--include-ocr-candidates', action='store_true',
                    help='Use isolated unverified OCR draft pages for testing only')
args = parser.parse_args()
root = Path('data/processed/ocr_candidate') if args.include_ocr_candidates else Path('data/processed/accepted_ocr')
chunks = [json.loads(line) for line in (root / 'chunks_350.jsonl').read_text().splitlines()]
pages = {p['page_id']: p for p in (json.loads(line) for line in (root / 'pages.jsonl').read_text().splitlines())}
retrieved = search(args.question, chunks, mode='bm25', top_k=3, labour_code=args.code)
result = extractive_evidence(retrieved, pages)
result['candidate_ocr_enabled'] = args.include_ocr_candidates
print(json.dumps(result, indent=2, ensure_ascii=False))
