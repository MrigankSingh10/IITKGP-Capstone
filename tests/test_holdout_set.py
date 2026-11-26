import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / 'evaluation/grounding_holdout_candidates_v0.2.jsonl'
REVIEW = ROOT / 'evaluation/grounding_holdout_review_v0.2.csv'


def load():
    draft = [json.loads(line) for line in DRAFT.read_text(encoding='utf-8').splitlines()]
    with REVIEW.open(encoding='utf-8', newline='') as f:
        return draft, list(csv.DictReader(f))


def test_v02_keeps_the_eight_originals_and_adds_twelve_unreviewed_drafts():
    draft, rows = load()
    original = [json.loads(line) for line in
                (ROOT / 'evaluation/grounding_holdout_candidates_v0.1.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(draft) == 20 and [r['case_id'] for r in rows] == [d['case_id'] for d in draft]
    for old, new in zip(original, draft):
        assert {k: new[k] for k in old} == old                     # originals unchanged
    added = draft[8:]
    assert all(d['pdf_page_number'] is None and d['source_quote'] == '' for d in added)
    assert all(d['review_status'] == 'draft' for d in draft)
    assert all(r['review_verdict'] in ('approved', 'rejected') and r['reviewer'] for r in rows)   # review recorded


def test_no_question_repeats_gold_or_fresh_sets():
    draft, _ = load()
    taken = set()
    for name in ('gold_v1.jsonl', 'grounding_fresh_v1.jsonl'):
        taken |= {json.loads(line)['question'].casefold()
                  for line in (ROOT / 'evaluation' / name).read_text(encoding='utf-8').splitlines()}
    questions = [d['question'].casefold() for d in draft]
    assert len(set(questions)) == 20 and not set(questions) & taken


def _fake_corpus(tmp_path, draft):
    """A tiny page registry holding each case's quote, standing in for the local OCR corpus."""
    pages = {}
    for n, case in enumerate(draft, 1):
        number = case['pdf_page_number'] or 100 + n
        page = pages.setdefault(f"{case['source_pdf_id']}:page_{number:04d}", {
            'original_title': case['original_title'], 'source_url': case['source_url'], 'text': ''})
        page['text'] += f" ... {case['source_quote'] or 'quote for ' + case['case_id']} ..."
    path = tmp_path / 'pages.jsonl'
    path.write_text(''.join(json.dumps({'page_id': k, **v}) + '\n' for k, v in pages.items()), encoding='utf-8')
    return path


def _run(tmp_path, *extra):
    env = {**os.environ, 'PYTHONPATH': str(ROOT / 'src')}
    return subprocess.run([sys.executable, str(ROOT / 'scripts/freeze_holdout.py'), *extra],
                          cwd=tmp_path, env=env, capture_output=True, text=True)


def _setup(tmp_path, verdict_for):
    draft, rows = load()
    (tmp_path / 'evaluation').mkdir()
    for name in ('gold_v1.jsonl', 'grounding_fresh_v1.jsonl'):
        shutil.copyfile(ROOT / 'evaluation' / name, tmp_path / 'evaluation' / name)
    shutil.copyfile(DRAFT, tmp_path / 'evaluation' / DRAFT.name)
    pages = _fake_corpus(tmp_path, draft)
    for n, (row, case) in enumerate(zip(rows, draft), 1):
        row['review_verdict'], row['reviewer'] = verdict_for(n), 'Team members'
        if not case['source_quote']:
            row['pdf_page_number'], row['source_quote'] = str(100 + n), f"quote for {case['case_id']}"
    with (tmp_path / 'evaluation' / REVIEW.name).open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return pages


def test_freeze_refuses_an_unfinished_review(tmp_path):
    pages = _setup(tmp_path, lambda n: '' if n == 12 else 'approved')
    result = _run(tmp_path, '--pages', str(pages))
    assert result.returncode != 0 and 'holdout-draft-012' in result.stderr


def test_freeze_keeps_approved_drops_rejected_and_never_overwrites(tmp_path):
    pages = _setup(tmp_path, lambda n: 'rejected' if n in (3, 15) else 'approved')
    result = _run(tmp_path, '--pages', str(pages))
    assert result.returncode == 0, result.stderr
    frozen = [json.loads(line) for line in
              (tmp_path / 'evaluation/grounding_holdout_v1.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(frozen) == 18 and all(c['review_status'] == 'approved' for c in frozen)
    assert {'holdout-draft-003', 'holdout-draft-015'}.isdisjoint(c['case_id'] for c in frozen)
    assert 'holdout-draft-003' in (tmp_path / 'evaluation/grounding_holdout_v1_freeze.md').read_text()
    assert _run(tmp_path, '--pages', str(pages)).returncode != 0


def test_freeze_rejects_a_quote_not_on_the_page(tmp_path):
    pages = _setup(tmp_path, lambda n: 'approved')
    review = tmp_path / 'evaluation' / REVIEW.name
    review.write_text(review.read_text(encoding='utf-8').replace('quote for holdout-draft-010', 'made-up text'),
                      encoding='utf-8')
    result = _run(tmp_path, '--pages', str(pages))
    assert result.returncode != 0 and 'Quote does not appear' in result.stderr
