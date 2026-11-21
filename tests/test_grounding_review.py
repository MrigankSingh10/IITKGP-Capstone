import csv
import json

import pytest

from hr_navigator.evaluation.grounding_review import reviewed_cases


def write_fixture(tmp_path, verdict='approved', reviewer='Reviewer', quote='The period is thirty days.'):
    page = {'page_id': 'source:page_0001', 'source_pdf_id': 'source', 'pdf_page_number': 1,
            'original_title': 'Example', 'source_url': 'https://example.org',
            'text': 'The period is thirty days.'}
    case = {'case_id': 'fresh-1', 'source_pdf_id': 'source', 'pdf_page_number': 1,
            'question': 'What period?', 'expected_conditions': 'Thirty days.'}
    row = {'case_id': 'fresh-1', 'question': 'What period?', 'expected_conditions': 'Thirty days.',
           'original_title': 'Example', 'pdf_page_number': '1', 'section': '1',
           'source_url': 'https://example.org', 'source_quote': quote,
           'review_verdict': verdict, 'reviewer': reviewer, 'review_notes': ''}
    draft, review, pages = (tmp_path / 'draft.jsonl', tmp_path / 'review.csv', tmp_path / 'pages.jsonl')
    draft.write_text(json.dumps(case)+'\n')
    pages.write_text(json.dumps(page)+'\n')
    with review.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    return draft,review,pages


def test_requires_individual_approval_and_identified_reviewer(tmp_path):
    paths=write_fixture(tmp_path, verdict='', reviewer='')
    with pytest.raises(ValueError, match='approved status'):
        reviewed_cases(*paths)


def test_rejects_invented_quote_and_preserves_approved_review(tmp_path):
    paths=write_fixture(tmp_path,quote='The period is sixty days.')
    with pytest.raises(ValueError,match='Quote does not appear'):
        reviewed_cases(*paths)
    paths=write_fixture(tmp_path)
    cases=reviewed_cases(*paths)
    assert cases[0]['review_status']=='approved' and cases[0]['reviewer']=='Reviewer'
    assert cases[0]['source_quote']=='The period is thirty days.'


def test_additional_sources_must_match_registered_page(tmp_path):
    draft, review, pages = write_fixture(tmp_path)
    with review.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = reader.fieldnames + ['additional_sources_json']
    source = {'source_pdf_id': 'source', 'pdf_page_number': 1, 'original_title': 'Example',
              'source_url': 'https://example.org', 'source_quote': 'invented text'}
    rows[0]['additional_sources_json'] = json.dumps([source])
    with review.open('w',encoding='utf-8-sig',newline='') as f:
        writer = csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match='Additional source does not match'):
        reviewed_cases(draft,review,pages)
    source['source_quote'] = 'The period is thirty days.'
    rows[0]['additional_sources_json'] = json.dumps([source])
    with review.open('w',encoding='utf-8-sig',newline='') as f:
        writer = csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    assert reviewed_cases(draft,review,pages)[0]['additional_sources'][0]['pdf_page_number'] == 1
