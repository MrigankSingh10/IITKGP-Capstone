"""Import a supplied row-by-row baseline review without assuming independent verification."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import re

parser = argparse.ArgumentParser()
parser.add_argument('review', type=Path)
args = parser.parse_args()
parsed = []
for line in args.review.read_text(encoding='utf-8').splitlines():
    if re.match(r'^draft-\d{3}\t', line):
        parts = line.split('\t', 5)
    elif re.match(r'^\|\s*draft-\d{3}\s*\|', line):
        parts = line.strip().strip('|').split('|', 5)
    else:
        continue
    if len(parts) != 6:
        raise ValueError('Malformed review row')
    case, strategy, valid, score, category, note = [part.strip() for part in parts]
    if score not in ('0', '1') or valid not in ('True', 'False'):
        raise ValueError('Invalid score or JSON-valid field')
    parsed.append({'case_id': case, 'strategy': strategy, 'valid': valid == 'True',
                   'score': score, 'category': category, 'note': note})
runs = {(x['case_id'], x['strategy']): x for x in (
    json.loads(line) for line in Path('reports/baseline_v1_runs.jsonl').read_text().splitlines())}
reviews = {(x['case_id'], x['strategy']): x for x in parsed}
if len(parsed) != len(reviews) or set(reviews) != set(runs):
    raise ValueError('Supplied rows do not match saved baseline runs exactly')
if any(reviews[key]['valid'] != run['schema_valid'] for key, run in runs.items()):
    raise ValueError('Supplied JSON-valid flags disagree with saved measurements')
for name, score_col in [('reports/baseline_review_readable.csv', 'correct_1_or_0'),
                        ('reports/baseline_v1_review.csv', 'correct')]:
    path = Path(name)
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = list(reader)
    if len(rows) != len(reviews) or {(r['case_id'], r['strategy']) for r in rows} != set(reviews):
        raise ValueError(f'Review sheet rows differ: {name}')
    for row in rows:
        review = reviews[(row['case_id'], row['strategy'])]
        if row.get('reviewer', '').strip() and row.get(score_col, '') != review['score']:
            raise ValueError(f'Existing conflicting review in {name}')
        row[score_col] = review['score']
        row['failure_category'] = review['category']
        row['reviewer'] = 'User-provided evaluation (reviewer not identified)'
        row['notes'] = review['note']
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
counts = Counter((x['strategy'], x['score']) for x in parsed)
print('Imported rows:', len(parsed), 'pass:', sum(x['score'] == '1' for x in parsed),
      'fail:', sum(x['score'] == '0' for x in parsed))
print('By strategy:', dict(counts))
print('JSON schema failures:', sum(not x['valid'] for x in parsed))
