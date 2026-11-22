"""Reconcile the two baseline reviews into one official sheet (decided by the team).

Rules agreed by the team members:
- Marks follow the strict review, which applies the frozen gold rule "no partial correctness".
- Each wrong answer gets one official category from docs/error_taxonomy.md. Where the two reviews
  chose different categories, the taxonomy's own rule applies: the higher-precedence (more
  serious, more upstream) category is the primary one. Format errors are primary only when the
  content is otherwise acceptable.
The original sheets are kept unchanged; every decision is traceable in the output columns.
"""
import argparse
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hr_navigator.evaluation import taxonomy  # noqa: E402

REVIEWER = 'Team members (reconciled; strict rubric)'
FIELDS = ['case_id', 'strategy', 'correct', 'refusal_correct', 'failure_category', 'reviewer', 'notes',
          'mark_basis', 'category_basis', 'team_correct', 'strict_correct', 'team_category',
          'strict_category', 'team_notes', 'strict_notes']


def read(path: Path) -> dict:
    with path.open(newline='', encoding='utf-8-sig') as f:
        return {(r['case_id'], r['strategy']): r for r in csv.DictReader(f)}


def reconcile(team: dict, strict: dict) -> list[dict]:
    if set(team) != set(strict) or len(team) != 240:
        raise ValueError('Both reviews must cover the same 240 case/strategy pairs')
    rows = []
    for key in sorted(strict):
        t, s = team[key], strict[key]
        if s['correct'] not in ('0', '1') or t['correct'] not in ('0', '1'):
            raise ValueError(f'{key}: both reviews must be fully scored')
        correct = s['correct']
        mark_basis = 'agreed' if t['correct'] == s['correct'] else 'strict rubric: no partial correctness'
        t_cat = taxonomy.normalize(t['failure_category']) if t['correct'] == '0' else ''
        s_cat = taxonomy.normalize(s['failure_category']) if s['correct'] == '0' else ''
        category, category_basis = '', ''
        if correct == '0':
            found = [c for c in (s_cat, t_cat) if c]
            category = taxonomy.primary(found)
            if not category:
                raise ValueError(f'{key}: wrong answer without a category in either review')
            if len(set(found)) == 1:
                category_basis = 'agreed' if len(found) == 2 else 'only review marking it wrong'
            else:
                other = next(c for c in found if c != category)
                category_basis = f'precedence: {category} over {other}'
        rows.append({'case_id': key[0], 'strategy': key[1], 'correct': correct, 'refusal_correct': '',
                     'failure_category': category, 'reviewer': REVIEWER,
                     'notes': f'{mark_basis}; category {category_basis}' if category else mark_basis,
                     'mark_basis': mark_basis, 'category_basis': category_basis,
                     'team_correct': t['correct'], 'strict_correct': s['correct'],
                     'team_category': t['failure_category'], 'strict_category': s['failure_category'],
                     'team_notes': t.get('notes', ''), 'strict_notes': s.get('notes', '')})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--team', type=Path, default=Path('reports/baseline_v1_review_team.csv'))
    parser.add_argument('--strict', type=Path, default=Path('reports/baseline_v1_review.csv'))
    parser.add_argument('--output', type=Path, default=Path('reports/baseline_v1_review_reconciled.csv'))
    args = parser.parse_args()
    rows = reconcile(read(args.team), read(args.strict))
    with args.output.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    agreed = sum(r['mark_basis'] == 'agreed' for r in rows)
    print(f'{len(rows)} rows written to {args.output}; marks agreed on {agreed}/{len(rows)} '
          f'({agreed / len(rows):.1%}); correct {sum(r["correct"] == "1" for r in rows)}')


if __name__ == '__main__':
    main()
