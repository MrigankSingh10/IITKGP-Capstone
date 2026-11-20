import collections
import datetime as dt
import hashlib
import json
from pathlib import Path

import pytest

from hr_navigator.evaluation.scenarios import load_jsonl, tool_name, validate, unauthorized_identity_calls

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / 'evaluation/scenarios_v0.1.jsonl'
FIXTURES = ROOT / 'evaluation/scenario_fixtures_v0.1.json'
HANDBOOK = ROOT / 'data/synthetic/acme_handbook_v0.1.json'


def load():
    return (load_jsonl(DRAFT), json.loads(FIXTURES.read_text(encoding='utf-8')),
            json.loads(HANDBOOK.read_text(encoding='utf-8')))


def working_days(start, end, holidays):
    day, count = dt.date.fromisoformat(start), 0
    while day <= dt.date.fromisoformat(end):
        count += day.weekday() < 5 and day.isoformat() not in holidays
        day += dt.timedelta(days=1)
    return count


def test_scenario_draft_is_internally_consistent():
    cases, fixtures, handbook = load()
    assert validate(cases, fixtures, handbook) == []
    assert len(cases) == 40
    assert collections.Counter(c['category'] for c in cases) == {
        'privacy_refusal': 8, 'prompt_injection': 6, 'company_policy': 8,
        'employee_tool': 8, 'action_approval': 6, 'clarify_escalate': 4}


def test_validator_catches_bad_cases():
    cases, fixtures, handbook = load()
    bad = dict(cases[0], id=cases[1]['id'], expected_decision='maybe',
               required_tool_actions=[{'tool': 'delete_everything', 'args': {}}])
    problems = validate([cases[1], bad], fixtures, handbook)
    assert any('duplicate id' in p for p in problems)
    assert any('unknown decision' in p for p in problems)
    assert any('unknown tool' in p for p in problems)


def test_identity_sensitive_trace_requires_trusted_caller():
    case = load()[0][0]
    call = {'tool': 'get_leave_balance', 'args': {'leave_type': 'annual'},
            'auth_context': {'employee_id': 'demo-001'}}
    assert unauthorized_identity_calls(case, [call]) == []
    assert unauthorized_identity_calls(case, [{**call, 'auth_context': {'employee_id': 'demo-002'}}])
    assert unauthorized_identity_calls(case, [{'tool': 'get_leave_balance',
                                                'args': {'employee_id': 'demo-001'}}])
    assert unauthorized_identity_calls(case, [{'tool': 'get_employee_profile'}])


def test_calculation_gold_answers_match_handbook_calendar():
    cases, fixtures, handbook = load()
    holidays = {h['date'] for h in handbook['holidays']['dates']}
    expected = {('2027-01-25', '2027-01-29'): 4, ('2027-08-13', '2027-08-17'): 2,
                ('2027-02-01', '2027-02-12'): 10, ('2027-02-01', '2027-02-05'): 5}
    seen = set()
    for case in cases:
        for action in case['required_tool_actions']:
            if tool_name(action) == 'calculate_leave_days':
                span = (action['args']['start'], action['args']['end'])
                assert working_days(*span, holidays) == expected[span]
                assert str(expected[span]) in case['gold_response_or_conditions']
                seen.add(span)
    assert seen == set(expected)


def test_balance_gold_answers_match_fixtures():
    cases, fixtures, _ = load()
    balances = {(b['employee_id'], b['leave_type']): b['days'] for b in fixtures['leave_balances']}
    checks = {'scn-tool-01': ('demo-001', 'annual'), 'scn-tool-02': ('demo-001', 'sick'),
              'scn-inj-03': ('demo-001', 'annual'), 'scn-tool-08': ('demo-002', 'annual')}
    by_id = {c['id']: c for c in cases}
    for cid, key in checks.items():
        assert by_id[cid]['auth_context']['employee_id'] == key[0]
        assert f'{balances[key]} day' in by_id[cid]['gold_response_or_conditions']


def test_injected_documents_stay_out_of_the_statutory_corpus():
    _, fixtures, _ = load()
    registry = (ROOT / 'reports/source_registry.jsonl').read_text(encoding='utf-8')
    for doc in fixtures['injected_documents']:
        assert doc['scope'] == 'untrusted_test_document'
        assert doc['id'] not in registry and doc['title'] not in registry


def test_frozen_scenarios_unchanged_if_present():
    checksum = ROOT / 'evaluation/scenarios_v1.sha256'
    if not checksum.exists():
        pytest.skip('scenario set not frozen yet')
    for line in checksum.read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
