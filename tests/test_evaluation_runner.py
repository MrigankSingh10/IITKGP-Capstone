import csv
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from hr_navigator.evaluation import runner, taxonomy
from hr_navigator.evaluation.systems import CallableSystem, ClosedBookSystem

ROOT = Path(__file__).resolve().parents[1]


def perfect_agent(question, conversation_context, auth_context, context):
    """Behaves exactly as each case expects (used to check the metrics reach 100%)."""
    return {'decision': context.get('expected_decision', 'answer'), 'answer': 'ok',
            'sources': [{'quote_or_section': 'x'}],
            'tool_actions': [{**(a if isinstance(a, dict) else {'tool': a, 'args': {}}),
                              'auth_context': dict(auth_context)}
                             for a in context.get('required_tool_actions', [])],
            'approval_required': context.get('expected_approval_required', False),
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}}


def reckless_agent(question, conversation_context, auth_context, context):
    """Always answers and always submits: should fail refusals and approvals."""
    return {'decision': 'answer', 'answer': 'done', 'approval_required': False,
            'tool_actions': [{'tool': 'submit_leave_request', 'args': {}}]}


def spoofing_agent(question, conversation_context, auth_context, context):
    """Reads a balance under someone else's identity: must fail the identity check."""
    return {'decision': 'answer', 'answer': '15 days', 'approval_required': False,
            'tool_actions': [{'tool': 'get_leave_balance', 'args': {'leave_type': 'annual'},
                              'auth_context': {'employee_id': 'demo-003'}}]}


class Broken:
    name = 'broken'

    def answer(self, case):
        raise RuntimeError('model timeout')


class FakeClient:
    def __init__(self, content):
        self.content, self.usage, self.messages = content, {}, None

    def chat(self, messages, **parameters):
        self.messages = messages
        self.usage['prompt_tokens'] = self.usage.get('prompt_tokens', 0) + 7
        return {'choices': [{'message': {'content': self.content}}]}


def scenarios():
    return runner.load_test_set('scenarios_v0.1', ROOT, allow_draft=True)


def run_to_records(system, cases, tmp_path, name='runs.jsonl'):
    out = tmp_path / name
    runner.run(system, cases, out, 'scenarios_v0.1', 'sha')
    return runner.load_runs(out)


def test_test_sets_load_and_protect_frozen_and_draft_files():
    gold, gold_sha = runner.load_test_set('gold_v1', ROOT)
    assert len(gold) == 80 and len(gold_sha) == 64
    with pytest.raises(ValueError, match='draft'):
        runner.load_test_set('scenarios_v0.1', ROOT)
    cases, _ = scenarios()
    injected = next(c for c in cases if c['id'] == 'scn-inj-01')
    assert injected['injected_documents'][0]['id'] == 'INJ-01'
    assert injected['reference_date'] == '2027-01-11'


def test_run_records_errors_resumes_and_tracks_usage(tmp_path):
    cases, _ = scenarios()
    out = tmp_path / 'runs.jsonl'
    assert runner.run(Broken(), cases[:3], out, 'scenarios_v0.1', 'sha') == 3
    assert runner.run(Broken(), cases[:3], out, 'scenarios_v0.1', 'sha') == 0
    records = runner.load_runs(out)
    assert all(r['status'] == 'error' and 'model timeout' in r['error'] for r in records)
    with pytest.raises(ValueError, match='different version'):
        runner.run(Broken(), cases[:3], out, 'scenarios_v0.1', 'other-sha')
    agent = CallableSystem('test_evaluation_runner:perfect_agent', 'perfect')
    records = run_to_records(agent, cases[:2], tmp_path, 'agent.jsonl')
    assert records[0]['usage'] == {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}


def test_auto_checks_catch_wrong_decisions_tools_and_approval(tmp_path):
    cases, _ = scenarios()
    by_id = {c['id']: c for c in cases}
    reckless = CallableSystem('test_evaluation_runner:reckless_agent', 'reckless')
    records = {r['case_id']: r for r in run_to_records(reckless, cases, tmp_path)}
    refusal = runner.auto_check(by_id['scn-prv-01'], records['scn-prv-01'])
    assert any('decision' in p for p in refusal) and any('forbidden' in p for p in refusal)
    draft = runner.auto_check(by_id['scn-act-01'], records['scn-act-01'])
    assert any('missing required tool call' in p for p in draft)
    assert any('approval_required' in p for p in draft)
    perfect = CallableSystem('test_evaluation_runner:perfect_agent', 'perfect')
    good = run_to_records(perfect, cases, tmp_path, 'perfect.jsonl')
    assert all(runner.auto_check(by_id[r['case_id']], r) == [] for r in good)


def test_review_sheet_keeps_human_marks_and_summary_metrics(tmp_path):
    cases, _ = scenarios()
    perfect = run_to_records(CallableSystem('test_evaluation_runner:perfect_agent', 'perfect'),
                             cases, tmp_path, 'p.jsonl')
    reckless = run_to_records(CallableSystem('test_evaluation_runner:reckless_agent', 'reckless'),
                              cases, tmp_path, 'r.jsonl')
    sheet = tmp_path / 'review.csv'
    assert runner.write_review_sheet(cases, perfect + reckless, sheet) == 80
    rows = list(csv.DictReader(sheet.open(encoding='utf-8')))
    for row in rows:
        row['correct'] = '1' if row['system'] == 'perfect' else '0'
        row['failure_category'] = '' if row['system'] == 'perfect' else 'safety failure'  # old name
        row['reviewer'] = 'tester'
    with sheet.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=runner.REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    runner.write_review_sheet(cases, perfect + reckless, sheet)  # refresh must keep marks
    review = runner.load_review(sheet)
    assert review[('scn-prv-01', 'perfect')]['reviewer'] == 'tester'
    pricing = {'currency': 'INR', 'input_per_million_tokens': 100, 'output_per_million_tokens': 200}
    metrics = runner.summarize(cases, perfect + reckless, review, pricing)
    good, bad = metrics['perfect'], metrics['reckless']
    assert good['accuracy'] == good['decision_accuracy'] == good['refusal_correctness'] == 1.0
    assert good['task_completion'] == good['injection_resistance'] == 1.0
    assert good['cost']['per_query'] == pytest.approx((10 * 100 + 5 * 200) / 1e6)
    assert bad['accuracy'] == bad['refusal_correctness'] == bad['task_completion'] == 0.0
    assert bad['failure_categories'] == {'safety_failure': 40}
    assert bad['failure_layers'] == {'safety': 40}
    assert bad['auto_detected_failures']['safety_failure'] >= 8
    assert good['auto_detected_failures'] == {}
    assert bad['tokens_per_query']['total_tokens'] == 0 and bad['cost']['per_query'] == 0
    assert runner.summarize(cases, perfect, review)['perfect']['cost'] == 'unknown; price not provided'
    assert '| perfect | 100.0% (40/40)' in runner.markdown_table(metrics)


def test_review_sheet_rejects_unknown_category(tmp_path):
    sheet = tmp_path / 'review.csv'
    with sheet.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=runner.REVIEW_FIELDS)
        writer.writeheader()
        writer.writerow({'case_id': 'x', 'system': 's', 'correct': '0', 'failure_category': 'oops'})
    with pytest.raises(ValueError, match='(?i)unknown failure category'):
        runner.load_review(sheet)


def test_closed_book_marks_injected_documents_untrusted():
    cases, _ = scenarios()
    case = next(c for c in cases if c['id'] == 'scn-inj-05')
    client = FakeClient('{"answer": "20 days", "uncertainty": "low"}')
    response = ClosedBookSystem(client, 'Answer in JSON.', 'closed_book_test').answer(case)
    assert response['answer'] == '20 days' and response['decision'] == 'answer'
    user = client.messages[-1]['content']
    assert 'untrusted' in user and 'v9.0' in user and user.endswith(case['question'])
    assert ClosedBookSystem(FakeClient('not json'), 's', 'n').answer(case)['answer'] == 'not json'


def test_gold_set_checks_and_week1_prompts_are_reused(tmp_path):
    gold, sha = runner.load_test_set('gold_v1', ROOT)
    system = ClosedBookSystem(FakeClient('{"answer": "x", "uncertainty": "y"}'), 's', 'closed_book_x')
    out = tmp_path / 'gold.jsonl'
    runner.run(system, gold[:2], out, 'gold_v1', sha)
    record = runner.load_runs(out)[0]
    assert record['usage'] == {'prompt_tokens': 7}
    assert runner.auto_check(gold[0], record) == ['statutory answer without sources']
    import importlib.util
    spec = importlib.util.spec_from_file_location('run_evaluation', ROOT / 'scripts/run_evaluation.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert set(module.baseline_strategies()) == {'zero_shot', 'few_shot', 'decomposition'}


def test_command_line_end_to_end(tmp_path):
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join([str(ROOT / 'tests'), str(ROOT / 'src')])}
    script = [sys.executable, str(ROOT / 'scripts/run_evaluation.py')]
    runs = tmp_path / 'runs.jsonl'
    base = ['--test-set', 'scenarios_v0.1', '--allow-draft']
    subprocess.run(script + ['run', *base, '--system', 'callable', '--name', 'perfect',
                             '--entrypoint', 'test_evaluation_runner:perfect_agent',
                             '--output', str(runs)], cwd=ROOT, env=env, check=True)
    sheet = tmp_path / 'review.csv'
    subprocess.run(script + ['review-sheet', *base, '--runs', str(runs), '--output', str(sheet)],
                   cwd=ROOT, env=env, check=True)
    metrics = tmp_path / 'metrics.json'
    subprocess.run(script + ['summarize', *base, '--runs', str(runs), '--review', str(sheet),
                             '--output', str(metrics)], cwd=ROOT, env=env, check=True)
    result = json.loads(metrics.read_text())
    assert result['perfect']['cases'] == 40 and result['perfect']['auto_check_pass_rate'] == 1.0
    assert metrics.with_suffix('.md').exists()
    failed = subprocess.run(script + ['run', '--test-set', 'scenarios_v0.1', '--system', 'callable',
                                      '--entrypoint', 'x:y'], cwd=ROOT, env=env,
                            capture_output=True, text=True)
    assert failed.returncode != 0 and 'draft' in failed.stderr


def test_identity_check_runs_on_every_agent_answer(tmp_path):
    cases, _ = scenarios()
    by_id = {c['id']: c for c in cases}
    spoof = CallableSystem('test_evaluation_runner:spoofing_agent', 'spoof')
    record = run_to_records(spoof, [by_id['scn-tool-01']], tmp_path)[0]
    problems = runner.auto_check(by_id['scn-tool-01'], record)
    assert problems == ['get_leave_balance: missing or mismatched trusted identity']
    assert taxonomy.suggest(by_id['scn-tool-01'], record, problems) == 'safety_failure'
    missing = dict(record, response=dict(record['response'], tool_actions=[
        {'tool': 'get_leave_balance', 'args': {'leave_type': 'annual'}}]))
    assert runner.auto_check(by_id['scn-tool-01'], missing) == problems


def test_taxonomy_normalises_old_names_and_applies_precedence():
    assert taxonomy.normalize('evidence unavailable') == 'abstention'
    assert taxonomy.normalize('wrong_jurisdiction_or_entity') == 'hallucination'
    assert taxonomy.normalize(' Reasoning Error ') == 'reasoning_error'
    assert taxonomy.normalize('') == ''
    with pytest.raises(ValueError):
        taxonomy.normalize('bad luck')
    assert taxonomy.primary(['hallucination', 'retrieval miss']) == 'retrieval_miss'
    assert taxonomy.primary(['reasoning_error', 'safety_failure', 'tool_call_error']) == 'safety_failure'
    assert set(taxonomy.CATEGORIES) == set(taxonomy.PRECEDENCE)
    week1 = ('hallucination', 'reasoning error', 'evidence unavailable', 'format error',
             'hallucinated_or_incorrect', 'incomplete_or_vague', 'cutoff_abstention',
             'wrong_jurisdiction_or_entity', 'json_schema_error')
    assert all(taxonomy.normalize(name) in taxonomy.CATEGORIES for name in week1)


def test_suggestions_from_automatic_checks():
    case = {'expected_decision': 'answer'}
    ok = {'status': 'ok', 'response': {'decision': 'escalate'}}
    assert taxonomy.suggest(case, {'status': 'error'}, ['system error: x']) == 'system_error'
    assert taxonomy.suggest(case, ok, ["decision 'escalate', expected 'answer'"]) == 'abstention'
    assert taxonomy.suggest({'expected_decision': 'refuse'}, ok,
                            ["decision 'escalate', expected 'refuse'"]) == 'safety_failure'
    assert taxonomy.suggest(case, ok, ['missing required tool call {"tool": "get_holidays"}',
                                       'retrieval: cited gold page not among retrieved pages']) \
        == 'tool_call_error'
    assert taxonomy.suggest(case, ok, ['statutory answer without sources']) == ''


def test_retrieval_miss_detected_against_gold_page():
    gold, sha = runner.load_test_set('gold_v1', ROOT)
    case = gold[0]
    page = runner.gold_page_id(case)
    assert page.startswith(case['source']['source_pdf_id']) and page.endswith(':page_0001')
    base = {'status': 'ok', 'response': {'decision': 'answer', 'sources': [{'x': 1}],
                                         'retrieved_page_ids': ['other:page_0009']}}
    problems = runner.auto_check(case, base)
    assert problems == ['retrieval: cited gold page not among retrieved pages']
    assert taxonomy.suggest(case, base, problems) == 'retrieval_miss'
    hit = {**base, 'response': {**base['response'], 'retrieved_page_ids': [page]}}
    assert runner.auto_check(case, hit) == []
