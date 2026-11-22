"""Freeze the new English relevance review after independent human sign-off."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

QUESTION_SHA256 = 'e0d53a111cdae69d4be5f23d51b25a644eb29fa837855c46fd099bb0068bea49'
FIELDS = ['case_id', 'question', 'query_language', 'relevant_page_ids', 'reviewer', 'review_status', 'notes']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review', type=Path, default=Path('evaluation/relevance_english_independent_review.csv'))
    parser.add_argument('--pages', type=Path, default=Path('data/processed/accepted_ocr/pages.jsonl'))
    parser.add_argument('--output', type=Path, default=Path('evaluation/relevance_english_independent_v1.jsonl'))
    args = parser.parse_args()
    checksum = Path(str(args.output) + '.sha256')
    if args.output.exists() or checksum.exists():
        parser.error('Output or checksum exists; choose a new version')
    with args.review.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != FIELDS:
            parser.error('Review schema does not match the packet')
        rows = list(reader)
    questions = [[r['case_id'], r['question'], r['query_language']] for r in rows]
    payload = json.dumps(questions, ensure_ascii=False, separators=(',', ':')).encode()
    if hashlib.sha256(payload).hexdigest() != QUESTION_SHA256:
        parser.error('Questions, IDs, languages or order differ from the packet')
    pages = {p['page_id']: p for p in (json.loads(line) for line in args.pages.read_text().splitlines())}
    for row in rows:
        labels = [label.strip() for label in row['relevant_page_ids'].split(';') if label.strip()]
        if (row['review_status'].strip().lower() != 'approved' or not row['reviewer'].strip()
                or not labels or len(labels) != len(set(labels))
                or any(label not in pages or pages[label].get('scope') != 'statutory' for label in labels)):
            parser.error(f"Incomplete or invalid statutory page review: {row['case_id']}")
        row['relevant_page_ids'] = labels
    content = ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows).encode()
    with args.output.open('xb') as f:
        f.write(content)
    with checksum.open('x', encoding='ascii') as f:
        f.write(hashlib.sha256(content).hexdigest() + '\n')
    print(f'Frozen {len(rows)} cases; SHA-256 {hashlib.sha256(content).hexdigest()}')


if __name__ == '__main__':
    main()
