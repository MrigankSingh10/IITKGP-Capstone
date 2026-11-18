"""Summarize observable baseline metrics without inventing answer scores."""
import argparse
import collections
import csv
import json
from pathlib import Path
import statistics

parser = argparse.ArgumentParser()
parser.add_argument('--runs', type=Path, default=Path('reports/baseline_v1_runs.jsonl'))
parser.add_argument('--output', type=Path, default=Path('reports/baseline_v1_metrics.json'))
parser.add_argument('--review', type=Path, default=Path('reports/baseline_v1_review.csv'))
args = parser.parse_args()
rows = [json.loads(line) for line in args.runs.read_text().splitlines()]
groups = collections.defaultdict(list)
for row in rows:
    groups[row['strategy']].append(row)
result = {}
for name, group in groups.items():
    successful = [x for x in group if x['status'] == 'ok']
    usage = collections.Counter()
    for row in successful:
        for key, value in (row.get('usage') or {}).items():
            if isinstance(value, int) and not isinstance(value, bool):
                usage[key] += value
    result[name] = {'attempted': len(group), 'successes': len(successful),
                    'schema_valid': sum(x['schema_valid'] for x in group),
                    'mean_latency_seconds': round(statistics.mean(x['latency_seconds'] for x in group), 3),
                    'usage_reported_sum': dict(usage),
                    'correctness': 'pending human review', 'refusal_correctness': 'pending human review',
                    'cost': 'unknown; price not provided'}
args.output.write_text(json.dumps(result, indent=2) + '\n')
if not args.review.exists():
    with args.review.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['case_id', 'strategy', 'correct', 'refusal_correct',
                                               'failure_category', 'reviewer', 'notes'])
        writer.writeheader()
        for row in rows:
            writer.writerow({'case_id': row['case_id'], 'strategy': row['strategy']})
print(json.dumps(result, indent=2))
