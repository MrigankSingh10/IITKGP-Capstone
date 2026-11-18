"""Produce review queues for unverified dates and possible duplicate-title versions."""
from collections import defaultdict
import csv
from datetime import date
import json
from pathlib import Path
import re

records = [json.loads(line) for line in Path('reports/source_registry.jsonl').read_text().splitlines()]
pages = defaultdict(list)
for line in Path('data/processed/pages.jsonl').read_text().splitlines():
    p = json.loads(line)
    if p['pdf_page_number'] <= 3:
        pages[p['source_pdf_id']].append(p['text'])
months = {name.lower(): i for i, name in enumerate(
    ['', 'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
     'september', 'october', 'november', 'december']) if name}
pattern = re.compile(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s*,?\s*(\d{4})\b', re.I)
rows, groups = [], defaultdict(list)
for rec in records:
    m = next(m for m in rec['manifest_matches'] if m.get('download_status') == 'Downloaded')
    stated = m.get('publication_date', '')
    found = set()
    for day, month, year in pattern.findall(' '.join(pages[rec['source_pdf_id']])):
        try:
            found.add(date(int(year), months[month.lower()], int(day)).isoformat())
        except ValueError:
            pass
    status = ('manifest_date_absent' if not stated else 'text_contains_manifest_date_unverified'
              if stated in found else 'manual_review_date_not_found')
    rows.append({'source_pdf_id': rec['source_pdf_id'], 'title': m.get('document_name', ''),
                 'manifest_date_unverified': stated, 'dates_detected_first_three_pages': ';'.join(sorted(found)),
                 'review_status': status, 'current_legal_status': 'unverified',
                 'source_url': m.get('original_source_url', '')})
    key = re.sub(r'\s+', ' ', m.get('document_name', '').strip().casefold())
    if key:
        groups[key].append(rec['source_pdf_id'])
with Path('reports/source_date_review.csv').open('w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
with Path('reports/possible_source_versions.json').open('w', encoding='utf-8') as f:
    json.dump([{'normalized_title': k, 'source_pdf_ids': v, 'relationship': 'unverified'}
               for k, v in groups.items() if len(v) > 1], f, indent=2)
print('Sources:', len(rows))
for status in sorted({r['review_status'] for r in rows}):
    print(status, sum(r['review_status'] == status for r in rows))
print('Exact normalized title groups for manual review:', sum(len(v) > 1 for v in groups.values()))
