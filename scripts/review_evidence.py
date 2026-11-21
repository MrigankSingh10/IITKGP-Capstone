"""Search local documents and return untrusted passages, without generating an answer."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hr_navigator.retrieval.grounded import extractive_evidence  # noqa: E402
from hr_navigator.retrieval.search import search, unsupported_query  # noqa: E402
from hr_navigator.retrieval.source_context import (  # noqa: E402
    enrich_pages, load_source_context, pair_related,
)

parser = argparse.ArgumentParser()
parser.add_argument('question')
parser.add_argument('--code')
parser.add_argument('--include-ocr-candidates', action='store_true',
                    help='Use isolated unverified OCR draft pages for testing only')
args = parser.parse_args()
if unsupported_query(args.question):
    print(json.dumps({'decision': 'unsupported_language', 'answer': 'Please ask your question in English.'}))
    sys.exit(0)
root = Path('data/processed/ocr_candidate') if args.include_ocr_candidates else Path('data/processed/accepted_ocr')
chunks = [json.loads(line) for line in (root / 'chunks_350.jsonl').read_text().splitlines()]
pages = {p['page_id']: p for p in (json.loads(line) for line in (root / 'pages.jsonl').read_text().splitlines())}
context = load_source_context()
enrich_pages(pages, context)
retrieved = search(args.question, chunks, mode='bm25', top_k=3, labour_code=args.code)
retrieved = pair_related(args.question, retrieved, chunks, context, args.code)
result = extractive_evidence(retrieved, pages)
result['candidate_ocr_enabled'] = args.include_ocr_candidates
print(json.dumps(result, indent=2, ensure_ascii=False))
