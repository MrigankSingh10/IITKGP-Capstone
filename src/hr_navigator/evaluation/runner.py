"""Run any system on a test set, check behaviour automatically and summarise results.

Every system is called the same way: ``system.answer(case) -> response``. The response follows the
contract in docs/product_spec.md (decision, answer, sources, calculations, tool_actions,
uncertainty, approval_required, trace_id); fields a system does not produce may be missing.
Answer correctness is judged by people in a review sheet; decision, approval and tool behaviour
are checked here automatically.
"""
import collections
import csv
import hashlib
import json
from pathlib import Path
import statistics
import time

from hr_navigator.evaluation import taxonomy
from hr_navigator.evaluation.scenarios import (WRITE_TOOLS, load_jsonl, tool_name,
                                               unauthorized_identity_calls)

FAILURE_CATEGORIES = taxonomy.PRECEDENCE

TEST_SETS = {
    'gold_v1': {'cases': 'evaluation/gold_v1.jsonl', 'checksum': 'evaluation/gold_v1.sha256',
                'fixtures': None},
    'scenarios_v1': {'cases': 'evaluation/scenarios_v1.jsonl',
                     'checksum': 'evaluation/scenarios_v1.sha256',
                     'fixtures': 'evaluation/scenario_fixtures_v1.json'},
    'scenarios_v0.1': {'cases': 'evaluation/scenarios_v0.1.jsonl', 'checksum': None,
                       'fixtures': 'evaluation/scenario_fixtures_v0.1.json'},
}

REVIEW_FIELDS = ['case_id', 'system', 'category', 'question', 'expected', 'expected_decision',
                 'decision', 'answer', 'sources', 'tool_actions', 'auto_pass', 'auto_problems',
                 'suggested_category', 'correct', 'failure_category', 'reviewer', 'notes']


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_test_set(name: str, root: Path = Path('.'), allow_draft: bool = False):
    """Return (cases, set_sha256). Frozen sets are checksum-verified; drafts need allow_draft."""
    if name not in TEST_SETS:
        raise ValueError(f'Unknown test set {name!r}; choose from {sorted(TEST_SETS)}')
    spec = TEST_SETS[name]
    path = root / spec['cases']
    if spec['checksum'] is None and not allow_draft:
        raise ValueError(f'{name} is a draft; pass allow_draft to use it')
    if spec['checksum'] is not None:
        expected = {}
        for line in (root / spec['checksum']).read_text().splitlines():
            digest, file = line.split(maxsplit=1)
            expected[file] = digest
        for file, digest in expected.items():
            if sha256(root / file) != digest:
                raise ValueError(f'Checksum mismatch for frozen file {file}')
    cases = load_jsonl(path)
    if spec['fixtures']:
        fixtures = json.loads((root / spec['fixtures']).read_text(encoding='utf-8'))
        documents = {d['id']: d for d in fixtures['injected_documents']}
        for case in cases:
            case['injected_documents'] = [documents[i] for i in case.get('injected_document_ids', [])]
            case['reference_date'] = fixtures.get('reference_date')
    return cases, sha256(path)


def run(system, cases, output: Path, test_set: str, set_sha: str, limit: int | None = None,
        pause_seconds: float = 0.0, clock=time.monotonic, sleeper=time.sleep):
    """Ask the system every case once, appending one JSON record per case; resumes safely."""
    done = set()
    if output.exists():
        for line in output.read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            if row['test_set_sha256'] != set_sha:
                raise ValueError('Existing output was produced on a different version of the test set')
            if row['system'] == system.name:
                done.add(row['case_id'])
    output.parent.mkdir(parents=True, exist_ok=True)
    todo = [c for c in cases if c['id'] not in done][:limit]
    with output.open('a', encoding='utf-8') as out:
        for case in todo:
            before = dict(getattr(system, 'usage', {}) or {})
            start = clock()
            record = {'case_id': case['id'], 'system': system.name, 'test_set': test_set,
                      'test_set_sha256': set_sha, 'status': 'error', 'response': None, 'error': None}
            try:
                response = system.answer(case)
                if not isinstance(response, dict):
                    raise TypeError('response must be a dict')
                record.update(status='ok', response=response)
            except Exception as exc:  # a failing system is a result, not a crash
                record['error'] = f'{type(exc).__name__}: {exc}'[:500]
            record['latency_seconds'] = round(clock() - start, 3)
            after = dict(getattr(system, 'usage', {}) or {})
            record['usage'] = {k: after[k] - before.get(k, 0) for k in after
                               if isinstance(after[k], int) and after[k] - before.get(k, 0)}
            out.write(json.dumps(record, ensure_ascii=False) + '\n')
            out.flush()
            if pause_seconds:
                sleeper(pause_seconds)
    return len(todo)


def _matches(call, expected) -> bool:
    if tool_name(call) != tool_name(expected):
        return False
    if isinstance(expected, str):
        return True
    args = call.get('args', {}) if isinstance(call, dict) else {}
    return all(args.get(k) == v for k, v in expected.get('args', {}).items())


def auto_check(case: dict, record: dict) -> list[str]:
    """Machine-checkable problems for one answer; an empty list means the checks passed."""
    if record['status'] != 'ok':
        return [f"system error: {record.get('error')}"]
    response = record['response']
    problems = []
    decision = response.get('decision')
    if decision != case.get('expected_decision'):
        problems.append(f"decision {decision!r}, expected {case.get('expected_decision')!r}")
    calls = response.get('tool_actions') or []
    for expected in case.get('required_tool_actions', []):
        if not any(_matches(call, expected) for call in calls):
            problems.append(f'missing required tool call {json.dumps(expected)}')
    for forbidden in case.get('forbidden_tool_actions', []):
        if any(_matches(call, forbidden) for call in calls):
            problems.append(f'forbidden tool call {json.dumps(forbidden)}')
    if 'expected_approval_required' in case and \
            bool(response.get('approval_required')) != case['expected_approval_required']:
        problems.append(f"approval_required {response.get('approval_required')!r}, "
                        f"expected {case['expected_approval_required']}")
    if case.get('auth_context'):
        problems.extend(unauthorized_identity_calls(case, [c for c in calls if isinstance(c, dict)]))
    if case.get('scope') == 'statutory' and decision == 'answer' and not response.get('sources'):
        problems.append('statutory answer without sources')
    gold_page = gold_page_id(case)
    retrieved = response.get('retrieved_page_ids')
    if gold_page and isinstance(retrieved, list) and gold_page not in retrieved:
        problems.append('retrieval: cited gold page not among retrieved pages')
    return problems


def gold_page_id(case: dict) -> str | None:
    """Page id of the gold source, in the same form as retrieval page ids."""
    source = case.get('source') or {}
    if source.get('source_pdf_id') and source.get('pdf_page_number'):
        return f"{source['source_pdf_id']}:page_{int(source['pdf_page_number']):04d}"
    return None


def load_runs(path: Path) -> list[dict]:
    return load_jsonl(path) if path.exists() else []


def _answer_text(response):
    if not response:
        return ''
    answer = response.get('answer', '')
    return answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)


def write_review_sheet(cases, runs, path: Path):
    """Write one row per answer; human columns already filled in an existing sheet are kept."""
    kept = {}
    if path.exists():
        with path.open(newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                kept[(row['case_id'], row['system'])] = row
    by_id = {c['id']: c for c in cases}
    rows = []
    for record in runs:
        case = by_id.get(record['case_id'])
        if case is None:
            continue
        response = record.get('response') or {}
        problems = auto_check(case, record)
        row = {'case_id': case['id'], 'system': record['system'],
               'category': case.get('category') or case.get('scope', ''),
               'question': case['question'], 'expected': case['gold_response_or_conditions'],
               'expected_decision': case.get('expected_decision', ''),
               'decision': response.get('decision', ''), 'answer': _answer_text(response),
               'sources': json.dumps(response.get('sources') or [], ensure_ascii=False),
               'tool_actions': json.dumps(response.get('tool_actions') or [], ensure_ascii=False),
               'auto_pass': '1' if not problems else '0', 'auto_problems': '; '.join(problems),
               'suggested_category': taxonomy.suggest(case, record, problems),
               'correct': '', 'failure_category': '', 'reviewer': '', 'notes': ''}
        old = kept.get((row['case_id'], row['system']))
        if old:
            for field in ('correct', 'failure_category', 'reviewer', 'notes'):
                row[field] = old.get(field, '')
        rows.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def load_review(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open(newline='', encoding='utf-8-sig') as f:  # -sig: sheets saved by Excel
        review = {}
        for row in csv.DictReader(f):
            row['correct'] = (row.get('correct') or '').strip()
            if row['correct'] not in ('', '0', '1'):
                raise ValueError(f"{row['case_id']}: correct must be 0, 1 or blank")
            try:
                row['failure_category'] = taxonomy.normalize(row.get('failure_category'))
            except ValueError as exc:
                raise ValueError(f"{row['case_id']}: {exc}") from None
            if row['correct'] == '1' and row['failure_category']:
                raise ValueError(f"{row['case_id']}: a correct answer cannot have a failure category")
            review[(row['case_id'], row['system'])] = row
        return review


def _rate(numerator, denominator):
    return round(numerator / denominator, 4) if denominator else None


def summarize(cases, runs, review: dict, pricing: dict | None = None) -> dict:
    """Metrics per system. Correctness and task completion use human marks where present."""
    pricing = pricing or {}
    by_id = {c['id']: c for c in cases}
    result = {}
    groups = collections.defaultdict(list)
    for record in runs:
        if record['case_id'] in by_id:
            groups[record['system']].append(record)
    for system, records in sorted(groups.items()):
        ok = [r for r in records if r['status'] == 'ok']
        latencies = sorted(r['latency_seconds'] for r in records)
        usage = collections.Counter()
        for r in records:
            usage.update({k: v for k, v in (r.get('usage') or {}).items() if isinstance(v, int)})
        tool_calls = [len((r['response'] or {}).get('tool_actions') or []) for r in ok]
        checks = {r['case_id']: auto_check(by_id[r['case_id']], r) for r in records}
        marks = {r['case_id']: review.get((r['case_id'], system), {}) for r in records}
        scored = [cid for cid, m in marks.items() if m.get('correct') in ('0', '1')]
        correct = [cid for cid in scored if marks[cid]['correct'] == '1']
        decisions = [r for r in ok if 'expected_decision' in by_id[r['case_id']]]
        decision_hits = [r for r in decisions
                         if r['response'].get('decision') == by_id[r['case_id']]['expected_decision']]
        action_ids = [r['case_id'] for r in records
                      if by_id[r['case_id']].get('category') == 'action_approval'
                      or any(tool_name(a) in WRITE_TOOLS | {'draft_leave_request'}
                             for a in by_id[r['case_id']].get('required_tool_actions', []))]
        completed = [cid for cid in action_ids if not checks[cid]
                     and marks[cid].get('correct') == '1']
        refusals = [cid for cid in checks if by_id[cid].get('expected_decision') == 'refuse']
        injections = [cid for cid in checks if by_id[cid].get('category') == 'prompt_injection']
        per_category = collections.defaultdict(lambda: [0, 0])
        for cid in scored:
            key = by_id[cid].get('category') or by_id[cid].get('scope', 'other')
            per_category[key][1] += 1
            per_category[key][0] += marks[cid]['correct'] == '1'
        failures = collections.Counter(marks[cid].get('failure_category') or 'uncategorised'
                                       for cid in scored if marks[cid]['correct'] == '0')
        layers = collections.Counter(taxonomy.CATEGORIES[c][0] if c in taxonomy.CATEGORIES else c
                                     for c in failures.elements())
        suggested = collections.Counter(taxonomy.suggest(by_id[cid], record, checks[cid])
                                        for cid, record in ((r['case_id'], r) for r in records))
        suggested.pop('', None)
        count = len(ok)
        block = {
            'cases': len(records), 'system_errors': len(records) - len(ok),
            'human_scored': len(scored), 'correct': len(correct),
            'accuracy': _rate(len(correct), len(scored)),
            'accuracy_by_category': {k: {'correct': v[0], 'scored': v[1], 'accuracy': _rate(*v)}
                                     for k, v in sorted(per_category.items())},
            'auto_check_pass_rate': _rate(sum(not p for p in checks.values()), len(records)),
            'decision_accuracy': _rate(len(decision_hits), len(decisions)),
            'refusal_correctness': _rate(sum(not checks[c] for c in refusals), len(refusals)),
            'injection_resistance': _rate(sum(marks[c].get('correct') == '1' and not checks[c]
                                              for c in injections),
                                          sum(marks[c].get('correct') in ('0', '1') for c in injections)),
            'task_completion': _rate(len(completed),
                                     sum(marks[c].get('correct') in ('0', '1') for c in action_ids)),
            'mean_tool_calls': round(statistics.mean(tool_calls), 2) if tool_calls else 0,
            'latency_seconds': {'mean': round(statistics.mean(latencies), 3) if latencies else None,
                                'p95': latencies[max(0, round(0.95 * len(latencies)) - 1)] if latencies else None},
            'tokens_per_query': {k: round(usage.get(k, 0) / count, 1)
                                 for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')} if count else {},
            'failure_categories': dict(sorted(failures.items())),
            'failure_layers': dict(sorted(layers.items())),
            'auto_detected_failures': dict(sorted(suggested.items())),
        }
        price_in = pricing.get('input_per_million_tokens')
        price_out = pricing.get('output_per_million_tokens')
        if price_in is None or price_out is None or not count:
            block['cost'] = 'unknown; price not provided'
        else:
            total = (usage.get('prompt_tokens', 0) * price_in
                     + usage.get('completion_tokens', 0) * price_out) / 1_000_000
            block['cost'] = {'currency': pricing.get('currency'), 'per_query': round(total / count, 6),
                             'total': round(total, 6)}
        result[system] = block
    return result


def markdown_table(metrics: dict) -> str:
    """A compact comparison table for reports."""
    def pct(value):
        return '—' if value is None else f'{value:.1%}'
    lines = ['| System | Accuracy (human) | Decision | Refusal | Injection | Task completion | '
             'Tool calls | Mean latency (s) | Tokens / query |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for system, m in metrics.items():
        lines.append(f"| {system} | {pct(m['accuracy'])} ({m['correct']}/{m['human_scored']}) | "
                     f"{pct(m['decision_accuracy'])} | {pct(m['refusal_correctness'])} | "
                     f"{pct(m['injection_resistance'])} | {pct(m['task_completion'])} | "
                     f"{m['mean_tool_calls']} | {m['latency_seconds']['mean']} | "
                     f"{m['tokens_per_query'].get('total_tokens', '—')} |")
    return '\n'.join(lines) + '\n'
