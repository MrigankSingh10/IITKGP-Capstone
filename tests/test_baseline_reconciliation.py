import csv
import json
from pathlib import Path
import subprocess
import sys

from hr_navigator.evaluation import taxonomy

ROOT = Path(__file__).resolve().parents[1]
RECONCILED = ROOT / 'reports/baseline_v1_review_reconciled.csv'


def rows(path):
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def test_reconciled_sheet_is_reproducible(tmp_path):
    out = tmp_path / 'reconciled.csv'
    subprocess.run([sys.executable, str(ROOT / 'scripts/reconcile_baseline_reviews.py'),
                    '--output', str(out)], cwd=ROOT, check=True, capture_output=True)
    assert out.read_text(encoding='utf-8') == RECONCILED.read_text(encoding='utf-8')


def test_marks_follow_strict_rubric_and_agreement_is_recorded():
    reconciled = rows(RECONCILED)
    strict = {(r['case_id'], r['strategy']): r for r in rows(ROOT / 'reports/baseline_v1_review.csv')}
    assert len(reconciled) == 240
    assert all(r['correct'] == strict[(r['case_id'], r['strategy'])]['correct'] for r in reconciled)
    assert sum(r['mark_basis'] == 'agreed' for r in reconciled) == 226
    assert sum(r['correct'] == '1' for r in reconciled) == 19
    assert all(r['team_correct'] == '1' and r['strict_correct'] == '0'
               for r in reconciled if r['mark_basis'] != 'agreed')


def test_every_wrong_answer_has_one_official_category_by_the_stated_rule():
    for r in rows(RECONCILED):
        if r['correct'] == '1':
            assert r['failure_category'] == ''
            continue
        assert r['failure_category'] in taxonomy.CATEGORIES
        candidates = [r['strict_category']] + ([r['team_category']] if r['team_correct'] == '0' else [])
        assert r['failure_category'] == taxonomy.primary(candidates)


def test_metrics_match_the_reconciled_sheet():
    metrics = json.loads((ROOT / 'reports/baseline_v1_metrics_reconciled.json').read_text())
    sheet = rows(RECONCILED)
    for strategy, block in metrics.items():
        mine = [r for r in sheet if r['strategy'] == strategy]
        assert block['correct'] == sum(r['correct'] == '1' for r in mine)
        counts = {}
        for r in mine:
            if r['correct'] == '0':
                counts[r['failure_category']] = counts.get(r['failure_category'], 0) + 1
        assert block['failure_categories_taxonomy'] == counts
