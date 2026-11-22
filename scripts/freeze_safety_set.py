"""Freeze the reviewed document-only safety set as evaluation/safety_doc_v1 (run once, after sign-off)."""
import argparse
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hr_navigator.evaluation.safety_set import validate  # noqa: E402
from hr_navigator.evaluation.scenarios import load_jsonl  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('--approved-by', required=True, help='Who signed off, e.g. "Team members"')
args = parser.parse_args()

draft, fixtures_path = Path('evaluation/safety_doc_v0.1.jsonl'), Path('evaluation/safety_doc_fixtures_v0.1.json')
target, target_fixtures = Path('evaluation/safety_doc_v1.jsonl'), Path('evaluation/safety_doc_fixtures_v1.json')
if target.exists() or target_fixtures.exists():
    raise SystemExit('safety_doc_v1 already exists; frozen files are never overwritten. Create v2 instead.')
cases = load_jsonl(draft)
fixtures = json.loads(fixtures_path.read_text(encoding='utf-8'))
gold = {c['id']: c for c in load_jsonl(Path('evaluation/gold_v1.jsonl'))}
problems = validate(cases, fixtures, gold)
if problems:
    raise SystemExit('Draft is not valid; fix before freezing:\n' + '\n'.join(problems))
shutil.copyfile(draft, target)
shutil.copyfile(fixtures_path, target_fixtures)
lines = [f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.as_posix()}' for p in (target, target_fixtures)]
Path('evaluation/safety_doc_v1.sha256').write_text('\n'.join(lines) + '\n')
counts = collections.Counter(c['category'] for c in cases)
Path('evaluation/safety_doc_v1_freeze.md').write_text(
    f"""# Document-only safety set v1 freeze

Frozen {dt.date.today().isoformat()} after sign-off by: {args.approved_by}.

`safety_doc_v1.jsonl` ({len(cases)} cases) and `safety_doc_fixtures_v1.json` were copied unchanged from
the reviewed v0.1 draft; SHA256 values are in `safety_doc_v1.sha256`. Injection cases reuse frozen
`gold_v1` questions and conditions. Categories: {dict(sorted(counts.items()))}.

Do not edit frozen files and never tune the system against this set; create a new version instead.
""", encoding='utf-8')
print('\n'.join(lines))
