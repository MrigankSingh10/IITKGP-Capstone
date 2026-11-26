import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import locate_holdout_quotes as loc  # noqa: E402


def test_matches_despite_line_breaks_hyphenation_and_curly_quotes():
    page = {'page_id': 'abc:page_0040', 'text': 'Intro.\n70. (b) the work-\nman shall be paid compensation which\n'
                                                 'shall be equivalent to fifteen days’  average pay for every'}
    hits = loc.locate("compensation which shall be equivalent to fifteen days' average pay", [page])
    assert len(hits) == 1
    exact = hits[0][1]
    assert exact in page['text'] and exact.startswith('compensation') and exact.endswith('pay')
    assert loc.locate('the workman shall', [page])[0][1] == 'the work-\nman shall'
    assert loc.locate('not on this page', [page]) == []


def _run(cwd, *args):
    env = {**os.environ, 'PYTHONPATH': str(ROOT / 'src')}
    return subprocess.run([sys.executable, *args], cwd=cwd, env=env, capture_output=True, text=True)


def test_located_sheet_passes_the_freeze(tmp_path):
    draft = [json.loads(line) for line in
             (ROOT / 'evaluation/grounding_holdout_candidates_v0.2.jsonl').read_text(encoding='utf-8').splitlines()]
    with (ROOT / 'evaluation/grounding_holdout_review_v0.2.csv').open(encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    # Fake OCR pages: each new quote is broken across lines with a curly apostrophe, as OCR does.
    pages = {}
    for n, (case, row) in enumerate(zip(draft, rows), 1):
        number = case['pdf_page_number'] or 200 + n
        quote = case['source_quote'] or f"the rule for case {n} says fifteen days' notice applies here"
        ocr = quote.replace("'", '’').replace(' ', '\n', 1) if not case['source_quote'] else quote
        page = pages.setdefault(f"{case['source_pdf_id']}:page_{number:04d}",
                                {'original_title': case['original_title'], 'source_url': case['source_url'], 'text': ''})
        page['text'] += f' ... {ocr} ...'
        if not case['source_quote']:
            row['source_quote'] = quote                        # the reviewer's (non-OCR) wording
        row['review_verdict'], row['reviewer'] = 'approved', 'Team members'
    (tmp_path / 'evaluation').mkdir()
    for name in ('gold_v1.jsonl', 'grounding_fresh_v1.jsonl', 'grounding_holdout_candidates_v0.2.jsonl'):
        shutil.copyfile(ROOT / 'evaluation' / name, tmp_path / 'evaluation' / name)
    pages_path = tmp_path / 'pages.jsonl'
    pages_path.write_text(''.join(json.dumps({'page_id': k, **v}) + '\n' for k, v in pages.items()), encoding='utf-8')
    sheet = tmp_path / 'filled.csv'
    with sheet.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    located = _run(tmp_path, str(ROOT / 'scripts/locate_holdout_quotes.py'), '--review', str(sheet),
                   '--pages', str(pages_path))
    assert located.returncode == 0, located.stderr
    assert 'Located 20 of 20' in located.stdout
    shutil.copyfile(tmp_path / 'filled_located.csv', tmp_path / 'evaluation/grounding_holdout_review_v0.2.csv')
    frozen = _run(tmp_path, str(ROOT / 'scripts/freeze_holdout.py'), '--pages', str(pages_path))
    assert frozen.returncode == 0, frozen.stderr
    assert 'Frozen 20 hold-out cases' in frozen.stdout


def test_missing_corpus_gives_a_clear_message(tmp_path):
    sheet = ROOT / 'evaluation/grounding_holdout_review_v0.2.csv'
    result = _run(tmp_path, str(ROOT / 'scripts/locate_holdout_quotes.py'), '--review', str(sheet),
                  '--pages', str(tmp_path / 'missing.jsonl'))
    assert result.returncode != 0 and 'corpus folder is needed' in result.stderr
