"""Check the Langfuse settings, optionally send a test trace, and print the trace dashboard link.

    export LANGFUSE_PUBLIC_KEY=pk-lf-...  LANGFUSE_SECRET_KEY=sk-lf-...
    python scripts/trace_dashboard.py --send-test
"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hr_navigator.observability.langfuse_export import LangfuseConfig, dashboard_link, send  # noqa: E402
from hr_navigator.observability.tracer import TraceEvent, utc_now_iso  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--send-test', action='store_true', help='send one test trace (no user data)')
    args = parser.parse_args()
    try:
        config = LangfuseConfig.from_env()
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if config is None:
        raise SystemExit('Langfuse is not configured. Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY '
                         '(and LANGFUSE_HOST if not https://cloud.langfuse.com) in this terminal.')
    try:
        link = dashboard_link(config)
    except Exception as exc:
        raise SystemExit(f'Could not reach Langfuse: {exc}') from exc
    if args.send_test:
        event = TraceEvent(timestamp=utc_now_iso(), session_id='setup-check', query='Trace dashboard setup check',
                           route_taken='setup_check', latency_ms=0.0, status='ok')
        if not send(event, config):
            raise SystemExit('The test trace was not accepted; see the warning above.')
        print('Test trace sent.')
    print(f'Trace dashboard: {link}')


if __name__ == '__main__':
    main()
