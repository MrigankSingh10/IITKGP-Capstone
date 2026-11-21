"""Evaluate any version of the system on a test set: run it, build the review sheet, summarise.

  run           ask the system every question and save its answers
  review-sheet  build (or refresh) the sheet where people mark answers 1/0
  summarize     compute accuracy, refusal, injection, task completion, latency, tokens and cost

Credentials come from flags or from CHAT_* / EMBEDDING_* environment variables (see .env.example).
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from hr_navigator.clients.api import APIConfig, HostedClient  # noqa: E402
from hr_navigator.evaluation import runner  # noqa: E402
from hr_navigator.evaluation.systems import CallableSystem, ClosedBookSystem, RagSystem  # noqa: E402


# Search indexes: (folder with pages.jsonl and chunks_<size>.jsonl, embedding cache)
INDEXES = {'accepted_ocr': (Path('data/processed/accepted_ocr'), 'data/indexes/accepted_ocr.sqlite'),
           'original': (Path('data/processed'), 'data/indexes/embeddings.sqlite')}


def baseline_strategies():
    """Reuse the exact Week 1 prompts from scripts/run_baselines.py."""
    spec = importlib.util.spec_from_file_location('run_baselines', ROOT / 'scripts/run_baselines.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.STRATEGIES


def config(args, prefix):
    lower = prefix.lower()
    values = [getattr(args, f'{lower}_{name}') for name in ('base_url', 'model', 'key_file', 'ca_file')]
    if not any(values):
        try:
            return APIConfig.from_env(prefix)
        except ValueError:
            raise SystemExit(f'Missing {prefix} settings: set {prefix}_BASE_URL, {prefix}_MODEL, '
                             f'{prefix}_API_KEY and {prefix}_CA_FILE, or pass the --{lower}-* options') from None
    if not all(values):
        raise SystemExit(f'Give all four --{lower}-* options, or none to use {prefix}_* variables')
    base_url, model, key_file, ca_file = values
    return APIConfig(base_url, model, Path(key_file).read_text().strip(), ca_file, timeout=90)


def build_system(args):
    if args.system == 'closed_book':
        strategies = baseline_strategies()
        if args.strategy not in strategies:
            raise SystemExit(f'--strategy must be one of {sorted(strategies)}')
        client = HostedClient(config(args, 'CHAT'), retries=3)
        return ClosedBookSystem(client, strategies[args.strategy], f'closed_book_{args.strategy}'), [client]
    if args.system == 'rag':
        from hr_navigator.retrieval.embeddings import connect, read_vector
        embed_config = config(args, 'EMBEDDING')
        root, cache = INDEXES[args.index]
        chunks = runner.load_jsonl(root / f'chunks_{args.chunk_size}.jsonl')
        pages = {p['page_id']: p for p in runner.load_jsonl(root / 'pages.jsonl')}
        db = connect(cache)
        try:
            vectors = {c['chunk_id']: v for c in chunks
                       if (v := read_vector(db, embed_config.model, c['text'])) is not None}
        finally:
            db.close()
        chat = HostedClient(config(args, 'CHAT'), retries=3)
        embed = HostedClient(embed_config, retries=3)
        return RagSystem(chat, embed, chunks, vectors, pages, top_k=args.top_k,
                         name=f'rag_{args.index}_{args.chunk_size}_top{args.top_k}'), [chat, embed]
    if not args.entrypoint:
        raise SystemExit('--entrypoint package.module:function is required for --system callable')
    return CallableSystem(args.entrypoint, args.name), []


def load_checked_runs(args, set_sha):
    runs = [r for path in args.runs for r in runner.load_runs(path)]
    try:
        runner.check_runs(runs, args.test_set, set_sha)
    except ValueError as exc:
        raise SystemExit(str(exc))
    return runs


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)

    def common(p):
        p.add_argument('--test-set', required=True, choices=sorted(runner.TEST_SETS))
        p.add_argument('--allow-draft', action='store_true', help='allow the unfrozen scenarios_v0.1 draft')

    p_run = sub.add_parser('run')
    common(p_run)
    p_run.add_argument('--system', required=True, choices=['closed_book', 'rag', 'callable'])
    p_run.add_argument('--strategy', default='few_shot', help='closed_book prompt from run_baselines.py')
    p_run.add_argument('--chunk-size', default='350', choices=['200', '350'])
    p_run.add_argument('--top-k', type=int, default=5)
    p_run.add_argument('--index', default='accepted_ocr', choices=sorted(INDEXES),
                       help='accepted_ocr = corpus with the 11 reviewed OCR pages (as in grounding runs)')
    p_run.add_argument('--entrypoint', help='for callable: package.module:function')
    p_run.add_argument('--name', help='system name shown in results (callable)')
    p_run.add_argument('--output', type=Path)
    p_run.add_argument('--limit', type=int, help='only the first N not-yet-run cases (quick check)')
    p_run.add_argument('--pause', type=float, default=1.05, help='seconds between calls')
    for prefix in ('chat', 'embedding'):
        for name in ('base-url', 'model', 'key-file', 'ca-file'):
            p_run.add_argument(f'--{prefix}-{name}')

    p_sheet = sub.add_parser('review-sheet')
    common(p_sheet)
    p_sheet.add_argument('--runs', type=Path, nargs='+', required=True)
    p_sheet.add_argument('--output', type=Path)

    p_sum = sub.add_parser('summarize')
    common(p_sum)
    p_sum.add_argument('--runs', type=Path, nargs='+', required=True)
    p_sum.add_argument('--review', type=Path)
    p_sum.add_argument('--pricing', type=Path, default=Path('configs/pricing.json'))
    p_sum.add_argument('--output', type=Path)
    args = parser.parse_args()

    try:
        cases, set_sha = runner.load_test_set(args.test_set, allow_draft=args.allow_draft)
    except ValueError as exc:
        raise SystemExit(str(exc))
    out_dir = Path('reports/evaluation')

    if args.command == 'run':
        system, clients = build_system(args)
        output = args.output or out_dir / f'{args.test_set}__{system.name}.jsonl'
        try:
            count = runner.run(system, cases, output, args.test_set, set_sha, limit=args.limit,
                               pause_seconds=args.pause if clients else 0)
        finally:
            for client in clients:
                client.close()
        print(f'{count} new answers saved to {output}')
    elif args.command == 'review-sheet':
        runs = load_checked_runs(args, set_sha)
        output = args.output or out_dir / f'{args.test_set}_review.csv'
        written, cleared = runner.write_review_sheet(cases, runs, output)
        print(f'{written} rows written to {output}')
        if cleared:
            print(f'{cleared} earlier marks were cleared because those answers changed; please re-mark them.')
    else:
        runs = load_checked_runs(args, set_sha)
        review_path = args.review or out_dir / f'{args.test_set}_review.csv'
        try:
            review = runner.load_review(review_path)
        except ValueError as exc:
            raise SystemExit(str(exc))
        pricing = json.loads(args.pricing.read_text()) if args.pricing.exists() else {}
        metrics = runner.summarize(cases, runs, review, pricing)
        output = args.output or out_dir / f'{args.test_set}_metrics.json'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(metrics, indent=2) + '\n')
        output.with_suffix('.md').write_text(runner.markdown_table(metrics))
        print(runner.markdown_table(metrics))
        stale = sum(m['stale_marks_ignored'] for m in metrics.values())
        if stale:
            print(f'{stale} marks were ignored because their answers changed; refresh the review sheet.')
        print(f'Saved {output} and {output.with_suffix(".md")}')


if __name__ == '__main__':
    main()
