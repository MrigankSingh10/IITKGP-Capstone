import json
from pathlib import Path

import pytest

from hr_navigator.retrieval.grounded import extractive_evidence
from hr_navigator.retrieval.search import search
from hr_navigator.retrieval.source_context import enrich_pages, load_source_context, pair_related


def test_real_amendment_pair_is_provision_specific():
    root = Path('data/processed/accepted_ocr')
    if not (root / 'chunks_350.jsonl').exists():
        pytest.skip('Accepted OCR corpus is not available locally')
    chunks = [json.loads(line) for line in (root / 'chunks_350.jsonl').read_text().splitlines()]
    context = load_source_context()
    question = 'What does section 104 of the Industrial Relations Code say?'
    initial = search(question, chunks, mode='bm25', top_k=3, labour_code='Industrial Relations Code')
    paired = pair_related(question, initial, chunks, context, 'Industrial Relations Code')
    act = [c for c in paired if c['source_pdf_id'].startswith('43cadbd9')]
    assert any(c['pdf_page_number'] == 51 and '104.' in c['text'] for c in act)
    unrelated = pair_related('What does section 10 say?', initial.copy(), chunks, context,
                             'Industrial Relations Code')
    assert not any(c.get('relationship_pairing') == 'amends' for c in unrelated)


def test_source_metadata_and_sparse_warnings_reach_evidence():
    root = Path('data/processed/accepted_ocr')
    if not (root / 'pages.jsonl').exists():
        pytest.skip('Accepted OCR corpus is not available locally')
    pages = {p['page_id']: p for p in map(json.loads, (root / 'pages.jsonl').read_text().splitlines())}
    enrich_pages(pages, load_source_context())
    chunks = map(json.loads, (root / 'chunks_350.jsonl').read_text().splitlines())
    chunk = next(c for c in chunks if c['page_id'].startswith('d7d9516a')
                 and c['pdf_page_number'] == 10)
    source = extractive_evidence([chunk], pages)['sources'][0]
    assert source['sparse_page_disposition'] == 'retain_accepted_ocr_with_warning'
    assert source['source_warnings']
    assert source['source_tags']['document_type']
    assert any(r['relationship'] == 'source_conflict' for r in source['source_relationships'])
