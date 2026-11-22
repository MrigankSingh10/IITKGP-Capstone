import csv
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path('scripts/freeze_english_independent_review.py')
PACKET = Path('evaluation/relevance_english_independent_review.csv')


def test_freezer_requires_approval_and_preserves_fixed_questions(tmp_path):
    with PACKET.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    pages = tmp_path / 'pages.jsonl'
    pages.write_text(json.dumps({'page_id': 'test:page_0001', 'scope': 'statutory'}) + '\n')
    review = tmp_path / 'review.csv'
    output = tmp_path / 'frozen.jsonl'
    def write():
        with review.open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    def run():
        return subprocess.run([sys.executable, str(SCRIPT), '--review', str(review), '--pages', str(pages),
                               '--output', str(output)], capture_output=True)
    write()
    assert run().returncode != 0 and not output.exists()
    for row in rows:
        row.update(relevant_page_ids='test:page_0001', reviewer='test reviewer', review_status='approved')
    rows[0]['question'] += ' changed'
    write()
    assert run().returncode != 0 and not output.exists()
    rows[0]['question'] = rows[0]['question'].removesuffix(' changed')
    write()
    assert run().returncode == 0 and len(output.read_text().splitlines()) == 12
    assert run().returncode != 0
