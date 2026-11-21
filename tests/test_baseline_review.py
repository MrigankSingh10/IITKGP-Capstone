import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = {'hallucination', 'reasoning error', 'evidence unavailable', 'format error',
              'hallucinated_or_incorrect', 'incomplete_or_vague', 'cutoff_abstention',
              'wrong_jurisdiction_or_entity', 'json_schema_error'}


def test_review_sheet_covers_every_run_with_valid_marks():
    runs = [json.loads(line) for line in
            (ROOT / 'reports/baseline_v1_runs.jsonl').read_text().splitlines()]
    with (ROOT / 'reports/baseline_v1_review.csv').open(newline='', encoding='utf-8') as f:
        review = list(csv.DictReader(f))
    assert {(r['case_id'], r['strategy']) for r in review} == \
        {(r['case_id'], r['strategy']) for r in runs}
    for row in review:
        assert row['correct'] in ('', '0', '1')
        if row['correct'] == '1':
            assert not row['failure_category']
        if row['failure_category']:
            assert row['failure_category'] in CATEGORIES


def test_metrics_accuracy_matches_review_sheet():
    metrics = json.loads((ROOT / 'reports/baseline_v1_metrics.json').read_text())
    with (ROOT / 'reports/baseline_v1_review.csv').open(newline='', encoding='utf-8') as f:
        review = list(csv.DictReader(f))
    for strategy, block in metrics.items():
        scored = [r for r in review if r['strategy'] == strategy and r['correct'] in ('0', '1')]
        if not scored:
            assert block['correctness'] == 'pending human review'
            continue
        assert block['scored'] == len(scored)
        assert block['correct'] == sum(r['correct'] == '1' for r in scored)
