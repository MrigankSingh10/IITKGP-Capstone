"""Validate the document-only safety set (refusals, document injection, out-of-scope, clarify).

This set fits the current document Q&A system. Cases that need employee data, tools or approvals
stay in the agent draft (evaluation/scenarios_v0.1.jsonl) until the agent exists.
"""
from hr_navigator.evaluation.scenarios import DECISIONS, TOOLS, WRITE_TOOLS

CATEGORIES = {'refusal', 'document_injection', 'out_of_scope', 'clarify'}
FIELDS = {'id', 'category', 'scope', 'question', 'conversation_context', 'auth_context',
          'gold_response_or_conditions', 'expected_decision', 'acceptable_decisions',
          'expected_approval_required', 'source', 'based_on_gold', 'required_tool_actions',
          'forbidden_tool_actions', 'injected_document_ids', 'preconditions', 'scoring_method',
          'review_status'}


def validate(cases: list[dict], fixtures: dict, gold: dict) -> list[str]:
    """Return problems; an empty list means the set is consistent with the gold set and fixtures."""
    problems, seen = [], set()
    documents = {d['id'] for d in fixtures['injected_documents']}
    for case in cases:
        cid = case.get('id', '?')
        if set(case) != FIELDS:
            problems.append(f'{cid}: fields differ from the schema: {sorted(set(case) ^ FIELDS)}')
            continue
        if cid in seen:
            problems.append(f'{cid}: duplicate id')
        seen.add(cid)
        if case['category'] not in CATEGORIES:
            problems.append(f"{cid}: unknown category {case['category']!r}")
        acceptable = case['acceptable_decisions']
        if case['expected_decision'] not in acceptable or not set(acceptable) <= DECISIONS:
            problems.append(f'{cid}: acceptable decisions must be valid and include the expected one')
        if case['category'] == 'refusal' and acceptable != ['refuse']:
            problems.append(f'{cid}: refusal cases accept only refuse')
        for doc in case['injected_document_ids']:
            if doc not in documents:
                problems.append(f'{cid}: unknown injected document {doc}')
        if case['category'] == 'document_injection' and not (case['injected_document_ids'] and case['based_on_gold']):
            problems.append(f'{cid}: injection cases need a tampered document and a gold question')
        if case['based_on_gold']:
            g = gold.get(case['based_on_gold'])
            if g is None:
                problems.append(f"{cid}: gold case {case['based_on_gold']} not found")
            elif (case['question'] != g['question'] or case['source'] != g['source']
                  or not case['gold_response_or_conditions'].startswith(g['gold_response_or_conditions'])):
                problems.append(f"{cid}: question, source or conditions differ from {case['based_on_gold']}")
        for action in case['required_tool_actions'] + case['forbidden_tool_actions']:
            name = action if isinstance(action, str) else action.get('tool')
            if name not in TOOLS:
                problems.append(f'{cid}: unknown tool {name!r}')
        required = {a if isinstance(a, str) else a.get('tool') for a in case['required_tool_actions']}
        if required & WRITE_TOOLS:
            problems.append(f'{cid}: a document-only case cannot require a write tool')
        if case['expected_approval_required']:
            problems.append(f'{cid}: a document-only case cannot require approval')
    return problems
