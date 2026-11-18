"""Run three single-prompt baselines; no gold answers or PDF text are sent to the model."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hr_navigator.clients.api import APIConfig, APIError, HostedClient  # noqa: E402

STRATEGIES = {
    'zero_shot': 'Answer the user question. Return one JSON object with keys answer and uncertainty. If you cannot verify a source or a legal fact, say so. Do not invent citations or current applicability.',
    'few_shot': 'Return one JSON object with keys answer and uncertainty. Do not invent citations or current applicability. Example: Q: What does a document I have not supplied say? A: {"answer":"I cannot verify its contents.","uncertainty":"The document was not provided."} Example: Q: Is a quoted provision definitely current? A: {"answer":"The quote alone does not establish current applicability.","uncertainty":"Check current authoritative sources."}',
    'decomposition': 'First identify what the question asks and what evidence is available. Privately check whether the requested source and current applicability are verifiable. Then return only a concise JSON object with keys answer and uncertainty. Do not invent citations or expose internal reasoning.',
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--key-file', type=Path, required=True)
    parser.add_argument('--ca-file', type=Path, required=True)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    gold = Path('evaluation/gold_v1.jsonl')
    expected = Path('evaluation/gold_v1.sha256').read_text().split()[0]
    if hashlib.sha256(gold.read_bytes()).hexdigest() != expected:
        raise SystemExit('Frozen set checksum mismatch')
    cases = [json.loads(line) for line in gold.read_text().splitlines()]
    done = set()
    if args.output.exists():
        for line in args.output.read_text().splitlines():
            row = json.loads(line)
            if row['gold_sha256'] != expected or row['model'] != args.model:
                raise SystemExit('Existing run has different dataset or model')
            done.add((row['case_id'], row['strategy']))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    key = args.key_file.read_text().strip()
    config = APIConfig(args.base_url, args.model, key, str(args.ca_file), timeout=90)
    client = HostedClient(config, retries=3)
    try:
        with args.output.open('a', encoding='utf-8') as out:
            for case in cases:
                for strategy, system in STRATEGIES.items():
                    if (case['id'], strategy) in done:
                        continue
                    messages = [{'role': 'system', 'content': system}]
                    messages += case.get('conversation_context', [])
                    messages.append({'role': 'user', 'content': case['question']})
                    start = time.monotonic()
                    row = {'case_id': case['id'], 'strategy': strategy, 'gold_sha256': expected,
                           'model': args.model, 'temperature': 0, 'max_tokens': 512,
                           'latency_seconds': None, 'usage': None, 'status': 'error',
                           'answer_text': None, 'schema_valid': False, 'error': None}
                    try:
                        result = client.chat(messages, temperature=0, max_tokens=512)
                        choice = result['choices'][0]
                        content = choice['message'].get('content') or ''
                        content = content.replace(key, '[REDACTED]')
                        row.update(status='ok', answer_text=content, usage=result.get('usage'),
                                   finish_reason=choice.get('finish_reason'))
                        try:
                            obj = json.loads(content)
                            row['schema_valid'] = (isinstance(obj, dict)
                                and isinstance(obj.get('answer'), str)
                                and isinstance(obj.get('uncertainty'), str))
                        except (ValueError, TypeError):
                            pass
                    except (APIError, KeyError, IndexError, TypeError) as exc:
                        row['error'] = str(exc) if isinstance(exc, APIError) else type(exc).__name__
                    row['latency_seconds'] = round(time.monotonic() - start, 3)
                    out.write(json.dumps(row, ensure_ascii=False) + '\n')
                    out.flush()
                    print(f"{case['id']} {strategy}: {row['status']}", flush=True)
                    time.sleep(1.05)
    finally:
        client.close()


if __name__ == '__main__':
    main()
