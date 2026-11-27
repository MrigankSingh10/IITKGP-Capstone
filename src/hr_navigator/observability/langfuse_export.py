"""Send chat traces to a Langfuse trace dashboard (Track B: trace runs through Langfuse).

Optional and off by default. When LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set, every
TraceEvent written by tracer.log_trace is also sent to Langfuse as OpenTelemetry spans (OTLP over
HTTP/JSON to /api/public/otel/v1/traces, the only trace ingestion Langfuse accepts since 16 November
2026), so the runs appear in the Langfuse web dashboard. Nothing else in the app changes.

Privacy: questions are already masked by the guardrail; they are masked again here before leaving
the machine, the employee ID is never sent, and LANGFUSE_SEND_QUERY_TEXT=false sends no question
text at all. Keys are read from the environment and never logged.

Sending happens on a small fixed pool of background workers fed by a bounded queue, with a short
timeout per request. If Langfuse is slow and the queue fills, new traces are dropped (and counted)
rather than creating more threads; if a worker cannot be started, export is skipped. Neither ever
affects the chat response.
"""
import atexit
from dataclasses import dataclass
from datetime import UTC, datetime
import ipaddress
import json
import logging
import os
import queue
import re
import shlex
import threading
import time
from pathlib import Path
from urllib.parse import urlparse
import uuid

import httpx

from hr_navigator.security.guardrails import redact_personal_identifiers

log = logging.getLogger(__name__)
DEFAULT_HOST = 'https://cloud.langfuse.com'
LOCAL_CONFIG = Path(__file__).resolve().parents[3] / '.env.langfuse'
LOCAL_KEYS = frozenset({'LANGFUSE_PUBLIC_KEY', 'LANGFUSE_SECRET_KEY', 'LANGFUSE_HOST',
                        'LANGFUSE_SEND_QUERY_TEXT', 'LANGFUSE_ENVIRONMENT'})
TIMEOUT_SECONDS = 5.0
FLUSH_SECONDS = 10.0
_VALID_ENVIRONMENT = re.compile(r'^(?!langfuse)[a-z0-9_-]{1,40}$')
WORKERS = 2
QUEUE_SIZE = 500
_queue: 'queue.Queue[tuple]' = queue.Queue(maxsize=QUEUE_SIZE)
_workers: list[threading.Thread] = []
_workers_lock = threading.Lock()
_dropped = 0


def local_settings(path: Path = LOCAL_CONFIG) -> dict[str, str]:
    """Read literal Langfuse assignments without executing shell code."""
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except FileNotFoundError:
        return {}
    except OSError:
        log.warning('Could not read local Langfuse configuration')
        return {}
    settings = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].lstrip()
        key, separator, raw = line.partition('=')
        if not separator or key not in LOCAL_KEYS:
            continue
        try:
            parts = shlex.split(raw, comments=True)
        except ValueError:
            log.warning('Ignoring invalid local Langfuse configuration line')
            continue
        if len(parts) <= 1:
            settings[key] = parts[0] if parts else ''
    return settings


def environment_name(value: str | None) -> str:
    """Langfuse accepts lowercase letters, digits, '-' and '_' (not starting with 'langfuse')."""
    name = re.sub(r'[^a-z0-9_-]+', '-', (value or '').strip().lower()).strip('-')
    if _VALID_ENVIRONMENT.match(name):
        return name
    if value:
        log.warning('LANGFUSE_ENVIRONMENT %r is not a valid Langfuse environment; using "development"', value)
    return 'development'


@dataclass(frozen=True)
class LangfuseConfig:
    public_key: str
    secret_key: str
    host: str = DEFAULT_HOST
    send_query_text: bool = True
    environment: str = 'development'

    @classmethod
    def from_env(cls, env=None) -> 'LangfuseConfig | None':
        """Return a config when both keys are set, otherwise None (export disabled)."""
        if env is None:
            env = {**local_settings(), **os.environ}
        public, secret = env.get('LANGFUSE_PUBLIC_KEY', '').strip(), env.get('LANGFUSE_SECRET_KEY', '').strip()
        if not public or not secret:
            return None
        host = (env.get('LANGFUSE_HOST') or DEFAULT_HOST).strip().rstrip('/')
        check_host(host)
        send_text = env.get('LANGFUSE_SEND_QUERY_TEXT', 'true').strip().lower() not in ('0', 'false', 'no')
        return cls(public, secret, host, send_text, environment_name(env.get('LANGFUSE_ENVIRONMENT')))


def check_host(host: str) -> None:
    """Require HTTPS, except plain HTTP to a self-hosted Langfuse on this machine."""
    url = urlparse(host)
    loopback = False
    if url.hostname:
        try:
            loopback = url.hostname == 'localhost' or ipaddress.ip_address(url.hostname).is_loopback
        except ValueError:
            loopback = False
    if not url.hostname or url.username or url.password or not (
            url.scheme == 'https' or (url.scheme == 'http' and loopback)):
        raise ValueError('LANGFUSE_HOST must be an https:// URL without credentials '
                         '(http:// is allowed only for localhost)')


OTEL_PATH = '/api/public/otel/v1/traces'
SERVICE_NAME = 'hr-policy-navigator'


def _value(value) -> dict:
    """One OTLP/JSON attribute value."""
    if isinstance(value, bool):
        return {'boolValue': value}
    if isinstance(value, int):
        return {'intValue': str(value)}
    if isinstance(value, float):
        return {'doubleValue': value}
    if isinstance(value, (list, tuple)):
        return {'arrayValue': {'values': [_value(v) for v in value]}}
    return {'stringValue': str(value)}


def _attributes(values: dict) -> list:
    return [{'key': key, 'value': _value(value)} for key, value in values.items() if value is not None]


def _unix_nano(iso: str) -> int:
    moment = datetime.fromisoformat(iso)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return int(moment.timestamp() * 1_000_000) * 1000


def build_spans(event, config: LangfuseConfig) -> dict:
    """Turn one TraceEvent into an OTLP/JSON export request for Langfuse: a root span 'chat' (the
    trace), a child span named after the route and, if the model was called, a child generation
    carrying the token usage and cost."""
    trace_id = uuid.uuid4().hex                     # 32 hex characters
    root_id, route_id, model_id = (uuid.uuid4().hex[:16] for _ in range(3))
    try:
        end = _unix_nano(event.timestamp)          # the tracer stamps the event when the request finishes
    except ValueError:
        end = time.time_ns()
    start = end - int((event.latency_ms or 0) * 1_000_000)
    question = redact_personal_identifiers(event.query) if config.send_query_text else '[not sent]'
    level = {'error': 'ERROR', 'rate_limited': 'WARNING'}.get(event.status, 'DEFAULT')
    shared = {                                      # on every span so the dashboard can filter by them
        'langfuse.trace.name': 'chat', 'langfuse.session.id': event.session_id,
        'langfuse.trace.tags': [event.route_taken, event.status], 'langfuse.environment': config.environment,
        'langfuse.trace.metadata.route_taken': event.route_taken, 'langfuse.trace.metadata.status': event.status,
    }
    output = json.dumps({'status': event.status, 'route_taken': event.route_taken,
                         'citations': list(event.citations)}, ensure_ascii=False)
    root = {'name': 'chat', 'attrs': {
        **shared, 'langfuse.observation.type': 'span', 'langfuse.observation.level': level,
        'langfuse.observation.input': json.dumps({'question': question}, ensure_ascii=False),
        'langfuse.observation.output': output,
        'langfuse.trace.input': json.dumps({'question': question}, ensure_ascii=False),
        'langfuse.trace.output': output,
        'langfuse.trace.metadata.latency_ms': event.latency_ms,
        'langfuse.trace.metadata.citation_count': len(event.citations)}}
    route = {'name': event.route_taken, 'parent': root_id, 'attrs': {
        **shared, 'langfuse.observation.type': 'span', 'langfuse.observation.level': level,
        'langfuse.observation.metadata.latency_ms': event.latency_ms}}
    spans = [(root_id, root), (route_id, route)]
    if event.prompt_tokens or event.completion_tokens:
        attrs = {**shared, 'langfuse.observation.type': 'generation',
                 'langfuse.observation.usage_details': json.dumps(
                     {'input': event.prompt_tokens, 'output': event.completion_tokens})}
        if event.estimated_cost_usd and event.estimated_cost_usd > 0:   # unknown price: no cost, not zero
            attrs['langfuse.observation.cost_details'] = json.dumps({'total': event.estimated_cost_usd})
        spans.append((model_id, {'name': 'chat-model', 'parent': root_id, 'attrs': attrs}))
    otlp = []
    for span_id, span in spans:
        item = {'traceId': trace_id, 'spanId': span_id, 'name': span['name'], 'kind': 1,
                'startTimeUnixNano': str(start), 'endTimeUnixNano': str(end),
                'attributes': _attributes(span['attrs']),
                'status': {'code': 2 if level == 'ERROR' else 0}}
        if span.get('parent'):
            item['parentSpanId'] = span['parent']
        otlp.append(item)
    return {'resourceSpans': [{
        'resource': {'attributes': _attributes({'service.name': SERVICE_NAME,
                                                'deployment.environment': config.environment})},
        'scopeSpans': [{'scope': {'name': 'hr_navigator.observability'}, 'spans': otlp}]}]}


def send(event, config: LangfuseConfig, client: httpx.Client | None = None) -> bool:
    """Send one event now. Returns True when Langfuse accepted it; never raises."""
    try:
        payload = build_spans(event, config)
        owned = client is None
        client = client or httpx.Client(timeout=TIMEOUT_SECONDS)
        try:
            response = client.post(f'{config.host}{OTEL_PATH}', json=payload,
                                   auth=(config.public_key, config.secret_key),
                                   headers={'x-langfuse-ingestion-version': '4'})
        finally:
            if owned:
                client.close()
        if response.status_code >= 300:
            log.warning('Langfuse rejected a trace: HTTP %s', response.status_code)
            return False
        try:
            partial = (response.json() or {}).get('partialSuccess') or {}
        except ValueError:
            partial = {}
        if int(partial.get('rejectedSpans') or 0):
            log.warning('Langfuse rejected %s span(s): %s', partial.get('rejectedSpans'),
                        str(partial.get('errorMessage', ''))[:200])
            return False
        return True
    except Exception as exc:  # tracing must never break the app
        log.warning('Could not send trace to Langfuse: %s', type(exc).__name__)
        return False


def export_trace(event, env=None) -> bool:
    """Queue the event for Langfuse if configured. Returns True when queued; never raises."""
    global _dropped
    try:
        config = LangfuseConfig.from_env(env)
    except ValueError as exc:
        log.warning('Langfuse export disabled: %s', exc)
        return False
    if config is None or not _ensure_workers():
        return False
    try:
        _queue.put_nowait((event, config))
        return True
    except queue.Full:
        _dropped += 1
        if _dropped == 1 or _dropped % 100 == 0:
            log.warning('Langfuse queue full; %d trace(s) dropped so far', _dropped)
        return False


def _ensure_workers() -> bool:
    """Start the fixed worker pool once; False if no worker could be started."""
    with _workers_lock:
        _workers[:] = [w for w in _workers if w.is_alive()]
        while len(_workers) < WORKERS:
            worker = threading.Thread(target=_work, daemon=True, name='langfuse-export')
            try:
                worker.start()
            except RuntimeError as exc:          # e.g. the process cannot create more threads
                log.warning('Could not start a Langfuse export worker: %s', exc)
                break
            _workers.append(worker)
        return bool(_workers)


def _work() -> None:
    while True:
        event, config = _queue.get()
        try:
            send(event, config)
        except Exception:   # send() already never raises; this keeps the worker alive regardless
            log.warning('Langfuse worker error')
        finally:
            _queue.task_done()


def flush(timeout: float = FLUSH_SECONDS) -> int:
    """Wait up to timeout seconds for queued traces to be sent; return how many are left."""
    deadline = time.monotonic() + timeout
    with _queue.all_tasks_done:
        while _queue.unfinished_tasks:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                log.warning('%d trace(s) not sent to Langfuse before exit', _queue.unfinished_tasks)
                break
            _queue.all_tasks_done.wait(remaining)
        return _queue.unfinished_tasks


atexit.register(flush)   # short runs (scripts, evaluation) send their last traces before exiting


def dashboard_link(config: LangfuseConfig, client: httpx.Client | None = None) -> str:
    """Return the project's trace dashboard URL, looked up with the configured keys."""
    owned = client is None
    client = client or httpx.Client(timeout=TIMEOUT_SECONDS)
    try:
        response = client.get(f'{config.host}/api/public/projects', auth=(config.public_key, config.secret_key))
    finally:
        if owned:
            client.close()
    if response.status_code == 401:
        raise ValueError('Langfuse rejected the keys (HTTP 401); check LANGFUSE_PUBLIC_KEY, '
                         'LANGFUSE_SECRET_KEY and LANGFUSE_HOST')
    response.raise_for_status()
    projects = response.json().get('data') or []
    if not projects:
        raise ValueError('No Langfuse project found for these keys')
    return f"{config.host}/project/{projects[0]['id']}/traces"
