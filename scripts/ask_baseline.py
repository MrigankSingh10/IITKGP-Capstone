"""Interactive closed-book chat baseline; no corpus retrieval or persistent memory."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hr_navigator.clients.api import APIConfig, APIError, HostedClient  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key-file', type=Path, required=True)
    parser.add_argument('--ca-file', type=Path, required=True)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--model', required=True)
    args = parser.parse_args()
    try:
        key = args.key_file.read_text(encoding='utf-8').strip()
        client = HostedClient(APIConfig(args.base_url, args.model, key, str(args.ca_file)))
    except (OSError, ValueError) as exc:
        print(f'Configuration error: {type(exc).__name__}', file=sys.stderr)
        return 1
    print('Closed-book baseline: PDF retrieval is not enabled. Type quit to exit.')
    try:
        while True:
            try:
                question = input('\nYour question: ').strip()
            except EOFError:
                break
            if question.lower() in ('quit', 'exit'):
                break
            if not question:
                continue
            try:
                result = client.chat([
                    {'role': 'system', 'content': 'Answer cautiously. You have no access to the documents. Do not invent source citations or claim to verify current legal applicability.'},
                    {'role': 'user', 'content': question},
                ], temperature=0, max_tokens=512)
                answer = result['choices'][0]['message'].get('content') or '[No answer returned]'
                print('\nAnswer:', answer.replace(key, '[REDACTED]'))
            except (APIError, KeyError, IndexError, TypeError) as exc:
                print('Request failed:', str(exc) if isinstance(exc, APIError) else type(exc).__name__)
    except KeyboardInterrupt:
        print()
    finally:
        client.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
