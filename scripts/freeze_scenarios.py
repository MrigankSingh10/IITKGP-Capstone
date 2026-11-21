"""Freeze the reviewed scenario draft as evaluation/scenarios_v1 (run once, after team sign-off)."""
import argparse
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil

from hr_navigator.evaluation.scenarios import load_jsonl, validate

parser = argparse.ArgumentParser()
parser.add_argument('--draft', type=Path, default=Path('evaluation/scenarios_v0.1.jsonl'))
parser.add_argument('--fixtures', type=Path, default=Path('evaluation/scenario_fixtures_v0.1.json'))
parser.add_argument('--handbook', type=Path, default=Path('data/synthetic/acme_handbook_v0.1.json'))
parser.add_argument('--approved-by', required=True, help='Names of team members who signed off')
args = parser.parse_args()

target = Path('evaluation/scenarios_v1.jsonl')
target_fixtures = Path('evaluation/scenario_fixtures_v1.json')
if target.exists() or target_fixtures.exists():
    raise SystemExit('scenarios_v1 already exists; frozen files are never overwritten. Create v2 instead.')
cases = load_jsonl(args.draft)
fixtures = json.loads(args.fixtures.read_text(encoding='utf-8'))
handbook = json.loads(args.handbook.read_text(encoding='utf-8'))
problems = validate(cases, fixtures, handbook)
if problems:
    raise SystemExit('Draft is not valid; fix before freezing:\n' + '\n'.join(problems))

shutil.copyfile(args.draft, target)
shutil.copyfile(args.fixtures, target_fixtures)
lines = [f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.as_posix()}' for p in (target, target_fixtures)]
Path('evaluation/scenarios_v1.sha256').write_text('\n'.join(lines) + '\n')
counts = collections.Counter(c['category'] for c in cases)
decisions = collections.Counter(c['expected_decision'] for c in cases)
Path('evaluation/scenarios_v1_freeze.md').write_text(
    f"""# Scenario set v1 freeze

Frozen {dt.date.today().isoformat()} after team sign-off by: {args.approved_by}.

`scenarios_v1.jsonl` ({len(cases)} cases) and `scenario_fixtures_v1.json` were copied unchanged from the
reviewed v0.1 draft; their SHA256 values are in `scenarios_v1.sha256`. Company-policy answers depend on
Acme handbook `{handbook['version']}`; if the handbook changes, create a new scenario version instead of
editing this one.

Categories: {dict(sorted(counts.items()))}
Expected decisions: {dict(sorted(decisions.items()))}

This set complements, and does not replace, the frozen statutory set `gold_v1.jsonl`. Do not edit
frozen files and never tune prompts against this set.
""", encoding='utf-8')
print('\n'.join(lines))
