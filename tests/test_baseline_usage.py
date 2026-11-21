import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/summarize_baselines.py'


@pytest.mark.parametrize('usage_rows,expected_coverage', [
    ([{'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}] * 2, 2),
    ([{'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}, None], 1),
    ([None, None], 0),
    ([{'prompt_tokens': 10, 'completion_tokens': 5}, None], 0),
])
@pytest.mark.parametrize('priced', [True, False])
def test_usage_coverage_and_cost(tmp_path, usage_rows, expected_coverage, priced):
    runs = tmp_path / 'runs.jsonl'
    runs.write_text(''.join(json.dumps({'case_id': str(i), 'strategy': 'test', 'status': 'ok',
                                       'schema_valid': True, 'latency_seconds': 1, 'usage': usage}) + '\n'
                            for i, usage in enumerate(usage_rows)))
    pricing = tmp_path / 'pricing.json'
    pricing.write_text(json.dumps({'input_per_million_tokens': 2 if priced else None,
                                   'output_per_million_tokens': 4 if priced else None,
                                   'currency': 'USD'}))
    output = tmp_path / 'metrics.json'
    subprocess.run([sys.executable, str(SCRIPT), '--runs', str(runs), '--output', str(output),
                    '--review', str(tmp_path / 'review.csv'), '--pricing', str(pricing)],
                   check=True, capture_output=True, text=True)
    block = json.loads(output.read_text())['test']
    assert block['usage_coverage'] == {'reported_calls': expected_coverage, 'successful_calls': 2}
    if expected_coverage < 2:
        assert block['tokens_per_query'] == 'unknown; incomplete usage'
        assert block['cost'] == 'unknown; incomplete usage'
    else:
        assert block['tokens_per_query']['total_tokens'] == 15
        assert block['cost']['per_query'] == 0.00004 if priced else block['cost'] == 'unknown; price not provided'
