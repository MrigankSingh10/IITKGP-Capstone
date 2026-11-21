"""Validate human-reviewed document grounding cases before freezing them."""
import csv
import json
from pathlib import Path


def reviewed_cases(draft_path, review_path, page_path):
    draft = [json.loads(line) for line in Path(draft_path).read_text(encoding='utf-8').splitlines()]
    with Path(review_path).open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    pages = {p['page_id']: p for p in (json.loads(line) for line in Path(page_path).read_text().splitlines())}
    originals = {r['case_id']: r for r in draft}
    if len(originals) != len(draft) or len(rows) != len(draft):
        raise ValueError('Review cases do not match draft case count')
    if len({r['case_id'] for r in rows}) != len(rows) or set(originals) != {r['case_id'] for r in rows}:
        raise ValueError('Review case IDs differ or are duplicated')
    result = []
    for row in rows:
        original = originals[row['case_id']]
        if row['review_verdict'].strip().lower() != 'approved' or not row['reviewer'].strip():
            raise ValueError('Every case needs approved status and an identified reviewer')
        number = original['pdf_page_number']
        page_id = f"{original['source_pdf_id']}:page_{number:04d}"
        page = pages.get(page_id)
        if page is None:
            raise ValueError('Unknown source PDF page')
        if (row['original_title'] != page['original_title'] or row['source_url'] != page['source_url']
                or row['pdf_page_number'] != str(number)):
            raise ValueError('Source metadata changed; revise the draft before freezing')
        if not row['source_quote'].strip() or row['source_quote'] not in page['text']:
            raise ValueError('Quote does not appear on cited page')
        if not row['question'].strip() or not row['expected_conditions'].strip():
            raise ValueError('Question or expected conditions missing')
        try:
            extra_sources = json.loads(row.get('additional_sources_json') or '[]')
        except (TypeError, ValueError) as exc:
            raise ValueError('Invalid additional sources JSON') from exc
        if not isinstance(extra_sources, list):
            raise ValueError('Additional sources must be a list')
        for source in extra_sources:
            if (not isinstance(source, dict) or not isinstance(source.get('pdf_page_number'), int)
                    or isinstance(source.get('pdf_page_number'), bool) or source['pdf_page_number'] < 1):
                raise ValueError('Invalid additional source')
            extra_id = f"{source.get('source_pdf_id', '')}:page_{source['pdf_page_number']:04d}"
            extra_page = pages.get(extra_id)
            if (extra_page is None or source.get('original_title') != extra_page['original_title']
                    or source.get('source_url') != extra_page['source_url']
                    or not isinstance(source.get('source_quote'), str)
                    or not source['source_quote'].strip() or source['source_quote'] not in extra_page['text']):
                raise ValueError('Additional source does not match the page registry')
        updated = {**original, 'question': row['question'].strip(),
                   'expected_conditions': row['expected_conditions'].strip(),
                   'section': row['section'].strip(), 'source_quote': row['source_quote'],
                   'additional_sources': extra_sources,
                   'review_status': 'approved', 'reviewer': row['reviewer'].strip(),
                   'review_notes': row['review_notes'].strip()}
        result.append(updated)
    if len({r['question'].casefold() for r in result}) != len(result):
        raise ValueError('Duplicate questions after review')
    return result
