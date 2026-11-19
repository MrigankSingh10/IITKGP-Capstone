"""Load and validate the behaviour (scenario) evaluation set.

The scenario set tests what the frozen statutory gold set cannot: refusals, prompt injection,
Acme company policy, employee tools, approval-gated actions and clarification. Tool names and
decision values follow docs/product_spec.md so that test cases and the agent share one contract.
"""
import datetime as dt
import json
from pathlib import Path

DECISIONS = {'answer', 'refuse', 'clarify', 'escalate'}
CATEGORIES = {'privacy_refusal', 'prompt_injection', 'company_policy', 'employee_tool',
              'action_approval', 'clarify_escalate'}
TOOLS = {'search_policy', 'get_employee_profile', 'get_leave_balance', 'get_holidays',
         'calculate_leave_days', 'draft_leave_request', 'submit_leave_request',
         'create_hr_ticket', 'get_request_status'}
WRITE_TOOLS = {'submit_leave_request', 'create_hr_ticket'}
REQUIRED_FIELDS = {'id', 'category', 'question', 'conversation_context', 'auth_context',
                   'gold_response_or_conditions', 'expected_decision', 'expected_approval_required',
                   'source', 'required_tool_actions', 'forbidden_tool_actions',
                   'injected_document_ids', 'preconditions', 'scoring_method', 'review_status'}
DATE_ARGS = {'start', 'end'}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def tool_name(action) -> str:
    return action if isinstance(action, str) else action.get('tool', '')


def validate(cases: list[dict], fixtures: dict, handbook: dict) -> list[str]:
    """Return a list of problems; an empty list means the set is internally consistent."""
    problems = []
    employees = {e['id'] for e in fixtures['employees']}
    injected = {d['id'] for d in fixtures['injected_documents']}
    sections = {str(v['section']) for v in handbook.values() if isinstance(v, dict) and 'section' in v}
    seen = set()
    for case in cases:
        cid = case.get('id', '?')
        missing = REQUIRED_FIELDS - case.keys()
        if missing:
            problems.append(f'{cid}: missing fields {sorted(missing)}')
            continue
        if cid in seen:
            problems.append(f'{cid}: duplicate id')
        seen.add(cid)
        if case['category'] not in CATEGORIES:
            problems.append(f"{cid}: unknown category {case['category']!r}")
        if case['expected_decision'] not in DECISIONS:
            problems.append(f"{cid}: unknown decision {case['expected_decision']!r}")
        if case['auth_context'].get('employee_id') not in employees:
            problems.append(f'{cid}: auth employee not in fixtures')
        for doc in case['injected_document_ids']:
            if doc not in injected:
                problems.append(f'{cid}: unknown injected document {doc}')
        if case['category'] == 'prompt_injection' and not case['injected_document_ids'] \
                and 'SYSTEM' not in case['question']:
            problems.append(f'{cid}: injection case has no injected content')
        source = case['source']
        if source is not None:
            if source.get('handbook_version') != handbook.get('version'):
                problems.append(f'{cid}: handbook version mismatch')
            if str(source.get('handbook_section')) not in sections:
                problems.append(f"{cid}: handbook section {source.get('handbook_section')} not found")
        required = case['required_tool_actions']
        forbidden = case['forbidden_tool_actions']
        for action in required + forbidden:
            if tool_name(action) not in TOOLS:
                problems.append(f'{cid}: unknown tool {tool_name(action)!r}')
            args = action.get('args', {}) if isinstance(action, dict) else {}
            for key, value in args.items():
                if key in DATE_ARGS:
                    try:
                        dt.date.fromisoformat(value)
                    except (TypeError, ValueError):
                        problems.append(f'{cid}: bad date {key}={value!r}')
                if key == 'employee_id' and value not in employees:
                    problems.append(f'{cid}: tool argument employee {value} not in fixtures')
        required_names = {tool_name(a) for a in required}
        forbidden_names = {a for a in forbidden if isinstance(a, str)}
        if required_names & forbidden_names:
            problems.append(f'{cid}: tool both required and forbidden: {required_names & forbidden_names}')
        if case['expected_decision'] in ('refuse', 'clarify') and required_names & WRITE_TOOLS:
            problems.append(f'{cid}: refuse/clarify case requires a write tool')
        if required_names & WRITE_TOOLS and not case['expected_approval_required']:
            problems.append(f'{cid}: write tool required without approval flag')
        if 'submit_leave_request' in required_names and not (case['preconditions'] or {}).get('existing_drafts'):
            problems.append(f'{cid}: submission case has no existing draft precondition')
    return problems
