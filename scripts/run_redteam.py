"""Run the red-team attack catalogue and API checks; no model calls or API keys needed.

  python scripts/run_redteam.py                       # guardrail, source filter and API checks
  python scripts/run_redteam.py --agent-entrypoint hr_navigator.agents.graph:answer
                                                      # also attack the agent (when it exists)
"""
import argparse
import importlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from hr_navigator.evaluation import redteam  # noqa: E402


def pct(part, total):
    return f'{part}/{total} ({part / total:.0%})' if total else '—'


def markdown(summary, results, findings):
    s = summary
    lines = ['# Red-team results (generated)', '',
             '| Defence | Result |', '|---|---|',
             f"| Input guardrail: attacks blocked | {pct(s['guardrail_attacks_blocked']['pass'], s['guardrail_attacks_blocked']['total'])} |",
             f"| Input guardrail: harmless questions wrongly blocked | {pct(s['guardrail_false_positives']['blocked'], s['guardrail_false_positives']['total'])} |",
             f"| RAG source filter: poisoned passages flagged | {pct(s['source_injections_flagged']['pass'], s['source_injections_flagged']['total'])} |",
             f"| RAG source filter: genuine passages wrongly flagged | {pct(s['source_false_positives']['flagged'], s['source_false_positives']['total'])} |",
             f"| API checks passed | {s['server_checks']['pass']} of {s['server_checks']['pass'] + s['server_checks']['fail']} (not run: {s['server_checks']['not_run']}) |",
             f"| Agent attacks | {s['agent_attacks']['deferred']} deferred until the agent exists |"]
    corpus = s.get('corpus_source_filter')
    lines.append(f"| RAG source filter on the real corpus: genuine pages flagged | "
                 f"{pct(corpus['pages_flagged'], corpus['pages_checked'])} |" if corpus else
                 '| RAG source filter on the real corpus | not run (corpus pages not available) |')
    lines += ['',
             '## By attack type', '', '| Category | Stopped |', '|---|---|']
    for category, b in s['attacks_by_category'].items():
        lines.append(f"| {category} | {pct(b['pass'], b['total'])} |")
    lines += ['', '## Attacks that got through or harmless items that were stopped', '',
              '| ID | Category | Expected | Observed |', '|---|---|---|---|']
    lines += [f"| {r['id']} | {r['category']} | {r['expected']} | {r['observed']} |"
              for r in results if r['status'] == 'fail']
    lines += ['', '## API checks', '', '| ID | Check | Severity | Result | Evidence |', '|---|---|---|---|---|']
    lines += [f"| {f['id']} | {f['check']} | {f['severity']} | {f['status'].upper()} | "
              f"{f['evidence'].replace('|', '/')} |" for f in findings]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--catalogue', type=Path, default=ROOT / 'evaluation/redteam_attacks_v0.1.jsonl')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'reports/redteam')
    parser.add_argument('--agent-entrypoint', help='package.module:function, once the agent exists')
    parser.add_argument('--skip-server', action='store_true')
    parser.add_argument('--pages', type=Path, default=ROOT / 'data/processed/accepted_ocr/pages.jsonl',
                        help='corpus pages for the real false-alarm count (skipped if missing)')
    args = parser.parse_args()
    agent = None
    if args.agent_entrypoint:
        module, _, function = args.agent_entrypoint.partition(':')
        agent = getattr(importlib.import_module(module), function)
    items = redteam.load_catalogue(args.catalogue)
    results = [redteam.check_item(item, agent) for item in items]
    findings = [] if args.skip_server else redteam.server_checks()
    summary = redteam.summarize(results, findings)
    if args.pages.exists():
        pages = [json.loads(line) for line in args.pages.read_text(encoding='utf-8').splitlines()]
        summary['corpus_source_filter'] = redteam.corpus_false_flags(pages)
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / 'redteam_v1_results.jsonl').write_text(
        ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in results), encoding='utf-8')
    (out / 'redteam_v1_server.json').write_text(json.dumps(findings, indent=2) + '\n', encoding='utf-8')
    (out / 'redteam_v1_summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    (out / 'redteam_v1_summary.md').write_text(markdown(summary, results, findings), encoding='utf-8')
    print(markdown(summary, results, findings))


if __name__ == '__main__':
    main()
