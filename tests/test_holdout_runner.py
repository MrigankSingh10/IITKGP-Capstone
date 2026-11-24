"""The runner can load the frozen grounding hold-out (once it exists) and guards its one-time use."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from hr_navigator.evaluation import runner

ROOT = Path(__file__).resolve().parents[1]


def frozen_copy(tmp_path, count=3):
    """Write a frozen hold-out in the format scripts/freeze_holdout.py produces."""
    draft = [json.loads(line) for line in
             (ROOT / 'evaluation/grounding_holdout_candidates_v0.2.jsonl').read_text(encoding='utf-8').splitlines()]
    cases = []
    for n, record in enumerate(draft[:count], 1):
        record = {k: v for k, v in record.items() if k != 'origin'}
        record.update(pdf_page_number=record['pdf_page_number'] or 100 + n,
                      source_quote=record['source_quote'] or f'quote {n}', review_status='approved',
                      reviewer='Team members', additional_sources=[])
        cases.append(record)
    data = ''.join(json.dumps(c, ensure_ascii=False, sort_keys=True) + '\n' for c in cases).encode('utf-8')
    (tmp_path / 'evaluation').mkdir(exist_ok=True)
    (tmp_path / 'evaluation/grounding_holdout_v1.jsonl').write_bytes(data)
    (tmp_path / 'evaluation/grounding_holdout_v1.sha256').write_text(
        f'{hashlib.sha256(data).hexdigest()}  grounding_holdout_v1.jsonl\n', encoding='utf-8')
    return cases


def test_not_frozen_yet_gives_a_clear_message(tmp_path):
    with pytest.raises(ValueError, match='not frozen yet'):
        runner.load_test_set('grounding_holdout_v1', tmp_path)


def test_loads_the_frozen_holdout_in_the_runner_format(tmp_path):
    records = frozen_copy(tmp_path)
    cases, identity = runner.load_test_set('grounding_holdout_v1', tmp_path)
    first, record = cases[0], records[0]
    assert first['id'] == record['case_id'] and first['expected_decision'] == 'answer'
    assert first['gold_response_or_conditions'].startswith(record['expected_conditions'])
    assert record['source_quote'] in first['gold_response_or_conditions']
    assert runner.gold_page_id(first) == f"{record['source_pdf_id']}:page_{record['pdf_page_number']:04d}"

    response = {'decision': 'answer', 'answer': 'x', 'sources': [{}], 'tool_actions': [],
                'approval_required': False, 'retrieved_page_ids': ['other:page_0001']}
    problems = runner.auto_check(first, {'case_id': first['id'], 'status': 'ok', 'response': response})
    assert any('gold page' in p for p in problems)            # wrong page retrieved is flagged
    response['retrieved_page_ids'] = [runner.gold_page_id(first)]
    assert runner.auto_check(first, {'case_id': first['id'], 'status': 'ok', 'response': response}) == []


def test_an_edited_holdout_is_refused(tmp_path):
    frozen_copy(tmp_path)
    path = tmp_path / 'evaluation/grounding_holdout_v1.jsonl'
    path.write_text(path.read_text(encoding='utf-8').replace('section', 'Section', 1), encoding='utf-8')
    with pytest.raises(ValueError, match='Checksum mismatch'):
        runner.load_test_set('grounding_holdout_v1', tmp_path)


def test_cli_requires_final_to_run_the_holdout(tmp_path):
    frozen_copy(tmp_path)
    env = {**os.environ, 'PYTHONPATH': str(ROOT / 'src')}
    command = [sys.executable, str(ROOT / 'scripts/run_evaluation.py'), 'run',
               '--test-set', 'grounding_holdout_v1', '--system', 'callable', '--entrypoint', 'x:y']
    result = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode != 0 and 'Add --final' in result.stderr
