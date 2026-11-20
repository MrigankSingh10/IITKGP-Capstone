"""Summarize baseline metrics; answer accuracy comes only from the human review sheet."""
import argparse
import collections
import csv
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hr_navigator.evaluation import taxonomy  # noqa: E402


def load_review(path):
    """Return {(case_id, strategy): row} from the review sheet, validating its values."""
    review = {}
    with path.open(newline='', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            correct = (row.get('correct') or '').strip()
            category = (row.get('failure_category') or '').strip()
            if correct not in ('', '0', '1'):
                raise SystemExit(f"{row['case_id']} {row['strategy']}: correct must be 0, 1 or blank")
            try:
                taxonomy.normalize(category)
            except ValueError as exc:
                raise SystemExit(f"{row['case_id']} {row['strategy']}: {exc}") from None
            if correct == '1' and category:
                raise SystemExit(f"{row['case_id']} {row['strategy']}: correct answer has a category")
            review[(row['case_id'], row['strategy'])] = {**row, 'correct': correct,
                                                         'failure_category': category}
    return review


def cost_block(usage, count, pricing, usage_count):
    """Tokens per query always; money only when both prices are set in configs/pricing.json."""
    coverage = {'reported_calls': usage_count, 'successful_calls': count}
    if usage_count != count or not count:
        return {'usage_coverage': coverage, 'tokens_per_query': 'unknown; incomplete usage',
                'cost': 'unknown; incomplete usage'}
    per_query = {key: round(usage.get(key, 0) / count, 1)
                 for key in ('prompt_tokens', 'completion_tokens', 'total_tokens')} if count else {}
    price_in = pricing.get('input_per_million_tokens')
    price_out = pricing.get('output_per_million_tokens')
    if price_in is None or price_out is None or not count:
        return {'usage_coverage': coverage, 'tokens_per_query': per_query, 'cost': 'unknown; price not provided'}
    total = (usage.get('prompt_tokens', 0) * price_in
             + usage.get('completion_tokens', 0) * price_out) / 1_000_000
    return {'usage_coverage': coverage, 'tokens_per_query': per_query,
            'cost': {'currency': pricing.get('currency'), 'total': round(total, 6),
                     'per_query': round(total / count, 6), 'price_source': pricing.get('source')}}


def accuracy_block(group, review):
    marks = [review.get((x['case_id'], x['strategy']), {}) for x in group]
    scored = [m for m in marks if m.get('correct') in ('0', '1')]
    if not scored:
        return {'correctness': 'pending human review'}
    correct = sum(m['correct'] == '1' for m in scored)
    reviewers = sorted({m.get('reviewer', '').strip() for m in scored if m.get('reviewer', '').strip()})
    failures = collections.Counter(m['failure_category'] or 'uncategorised'
                                   for m in scored if m['correct'] == '0')
    official = collections.Counter(taxonomy.normalize(m['failure_category']) or 'uncategorised'
                                   for m in scored if m['correct'] == '0')
    return {'scored': len(scored), 'unscored': len(group) - len(scored), 'correct': correct,
            'accuracy': round(correct / len(scored), 4),
            'failure_categories': dict(sorted(failures.items())),
            'failure_categories_taxonomy': dict(sorted(official.items())), 'reviewers': reviewers}


parser = argparse.ArgumentParser()
parser.add_argument('--runs', type=Path, default=Path('reports/baseline_v1_runs.jsonl'))
parser.add_argument('--output', type=Path, default=Path('reports/baseline_v1_metrics.json'))
parser.add_argument('--review', type=Path, default=Path('reports/baseline_v1_review.csv'))
parser.add_argument('--pricing', type=Path, default=Path('configs/pricing.json'))
args = parser.parse_args()
rows = [json.loads(line) for line in args.runs.read_text().splitlines()]
review = load_review(args.review) if args.review.exists() else {}
pricing = json.loads(args.pricing.read_text()) if args.pricing.exists() else {}
groups = collections.defaultdict(list)
for row in rows:
    groups[row['strategy']].append(row)
result = {}
for name, group in groups.items():
    successful = [x for x in group if x['status'] == 'ok']
    usage = collections.Counter()
    usage_count = 0
    for row in successful:
        reported = row.get('usage') or {}
        if all(isinstance(reported.get(k), int) and not isinstance(reported.get(k), bool)
               and reported[k] >= 0 for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')):
            usage_count += 1
        for key, value in (row.get('usage') or {}).items():
            if isinstance(value, int) and not isinstance(value, bool):
                usage[key] += value
    result[name] = {'attempted': len(group), 'successes': len(successful),
                    'schema_valid': sum(x['schema_valid'] for x in group),
                    'mean_latency_seconds': round(statistics.mean(x['latency_seconds'] for x in group), 3),
                    'usage_reported_sum': dict(usage),
                    **accuracy_block(group, review),
                    **cost_block(usage, len(successful), pricing, usage_count),
                    'refusal_correctness': 'not applicable: the frozen set has no refusal cases'}
args.output.write_text(json.dumps(result, indent=2) + '\n')
if not args.review.exists():
    with args.review.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['case_id', 'strategy', 'correct', 'refusal_correct',
                                               'failure_category', 'reviewer', 'notes'])
        writer.writeheader()
        for row in rows:
            writer.writerow({'case_id': row['case_id'], 'strategy': row['strategy']})
print(json.dumps(result, indent=2))
