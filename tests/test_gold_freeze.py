import hashlib
import json
from pathlib import Path


def test_frozen_gold_integrity_and_citations():
    root = Path(__file__).resolve().parents[1]
    path = root / 'evaluation/gold_v1.jsonl'
    expected = (root / 'evaluation/gold_v1.sha256').read_text().split()[0]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    cases = [json.loads(line) for line in path.read_text().splitlines()]
    registry = {x['source_pdf_id']: x for x in (
        json.loads(line) for line in (root / 'reports/source_registry.jsonl').read_text().splitlines()
    )}
    assert len(cases) == 80
    assert len({c['id'] for c in cases}) == 80
    for case in cases:
        source = case['source']
        record = registry[source['source_pdf_id']]
        assert case['scope'] == 'statutory'
        assert 1 <= source['pdf_page_number'] <= record['page_count']
        assert any(m.get('original_source_url') == source['source_url']
                   for m in record['manifest_matches'])
