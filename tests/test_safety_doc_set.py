import collections
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from hr_navigator.evaluation import runner, safety_set
from hr_navigator.evaluation.scenarios import load_jsonl
from hr_navigator.evaluation.systems import CallableSystem, poisoned_evidence
from hr_navigator.retrieval import draft_review
from hr_navigator.retrieval.grounded import extractive_evidence

ROOT = Path(__file__).resolve().parents[1]


def load():
    cases = load_jsonl(ROOT / 'evaluation/safety_doc_v0.1.jsonl')
    fixtures = json.loads((ROOT / 'evaluation/safety_doc_fixtures_v0.1.json').read_text(encoding='utf-8'))
    gold = {c['id']: c for c in load_jsonl(ROOT / 'evaluation/gold_v1.jsonl')}
    return cases, fixtures, gold


def safe_agent(question, conversation_context, auth_context, context):
    return {'decision': context['expected_decision'], 'answer': 'ok', 'sources': [{'x': 1}],
            'tool_actions': [{'tool': 'search_policy', 'args': {}, 'auth_context': dict(auth_context)}],
            'approval_required': False}


def escalating_agent(question, conversation_context, auth_context, context):
    return {'decision': 'escalate', 'answer': 'Needs review.', 'tool_actions': [], 'approval_required': False}


def test_draft_is_valid_and_document_only():
    cases, fixtures, gold = load()
    assert safety_set.validate(cases, fixtures, gold) == []
    assert collections.Counter(c['category'] for c in cases) == {
        'refusal': 6, 'document_injection': 6, 'out_of_scope': 5, 'clarify': 1}
    assert all(not c['expected_approval_required'] for c in cases)


def test_validator_catches_mistakes():
    cases, fixtures, gold = load()
    injection = next(c for c in cases if c['category'] == 'document_injection')
    bad = [dict(injection, question='edited'), dict(cases[0], acceptable_decisions=['answer']),
           dict(cases[0], id=cases[1]['id'], required_tool_actions=['submit_leave_request'])]
    problems = safety_set.validate([cases[1]] + bad, fixtures, gold)
    assert any('differ from' in p for p in problems)
    assert any('acceptable decisions' in p for p in problems)
    assert any('duplicate id' in p for p in problems)
    assert any('write tool' in p for p in problems)


def test_runner_scores_the_set_with_acceptable_decisions(tmp_path):
    cases, sha = runner.load_test_set('safety_doc_v0.1', ROOT, allow_draft=True)
    assert next(c for c in cases if c['id'] == 'sd-inj-01')['injected_documents'][0]['id'] == 'SD-INJ-01'
    out = tmp_path / 'runs.jsonl'
    runner.run(CallableSystem('test_safety_doc_set:safe_agent', 'safe'), cases, out, 'safety_doc_v0.1', sha)
    runner.run(CallableSystem('test_safety_doc_set:escalating_agent', 'esc'), cases, out, 'safety_doc_v0.1', sha)
    runs = runner.load_runs(out)
    by_id = {c['id']: c for c in cases}
    safe = [r for r in runs if r['system'] == 'safe']
    assert all(runner.auto_check(by_id[r['case_id']], r) == [] for r in safe)
    esc = {r['case_id']: runner.auto_check(by_id[r['case_id']], r) for r in runs if r['system'] == 'esc'}
    assert esc['sd-inj-01'] == []                                  # escalating on tampered evidence is safe
    assert any('decision' in p for p in esc['sd-ref-01'])           # but a refusal case must refuse
    metrics = runner.summarize(cases, runs, {})
    assert metrics['safe']['decision_accuracy'] == 1.0
    assert metrics['safe']['refusal_correctness'] == 1.0


def test_poisoned_pages_pass_validation_so_the_pipeline_really_sees_them():
    _, fixtures, _ = load()
    pages, chunks = poisoned_evidence(fixtures['injected_documents'])
    verified = extractive_evidence(chunks, pages)['sources']
    assert len(verified) == 6
    flagged = {d['id'] for d in fixtures['injected_documents']
               if draft_review._INJECTION.search(d['text'])}
    assert flagged == {'SD-INJ-01', 'SD-INJ-04', 'SD-INJ-06'}       # the rest test the model itself


def test_freeze_script_freezes_once(tmp_path):
    for rel in ('evaluation/safety_doc_v0.1.jsonl', 'evaluation/safety_doc_fixtures_v0.1.json',
                'evaluation/gold_v1.jsonl'):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, tmp_path / rel)
    env = {**os.environ, 'PYTHONPATH': str(ROOT / 'src')}
    script = [sys.executable, str(ROOT / 'scripts/freeze_safety_set.py'), '--approved-by', 'Team members']
    subprocess.run(script, cwd=tmp_path, env=env, check=True, capture_output=True)
    assert (tmp_path / 'evaluation/safety_doc_v1.jsonl').read_bytes() == \
        (ROOT / 'evaluation/safety_doc_v0.1.jsonl').read_bytes()
    assert 'Team members' in (tmp_path / 'evaluation/safety_doc_v1_freeze.md').read_text()
    again = subprocess.run(script, cwd=tmp_path, env=env, capture_output=True, text=True)
    assert again.returncode != 0 and 'never overwritten' in again.stderr


def test_frozen_safety_set_unchanged_if_present():
    checksum = ROOT / 'evaluation/safety_doc_v1.sha256'
    if not checksum.exists():
        pytest.skip('safety set not frozen yet')
    cases, _ = runner.load_test_set('safety_doc_v1', ROOT)
    assert len(cases) == 18
