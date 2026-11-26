"""Send chat traces to a Langfuse trace dashboard (Track B: trace runs through Langfuse).

Optional and off by default. When LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set, every
TraceEvent written by tracer.log_trace is also sent to Langfuse through its public ingestion API,
so the runs appear in the Langfuse web dashboard. Nothing else in the app changes.

Privacy: questions are already masked by the guardrail; they are masked again here before leaving
the machine, the employee ID is never sent, and LANGFUSE_SEND_QUERY_TEXT=false sends no question
text at all. Keys are read from the environment and never logged.

Sending happens in a background thread with a short timeout. A failure is logged as a warning and
never affects the chat response.
"""
import atexit
from dataclasses import dataclass
from datetime import datetime, timedelta
import ipaddress
import logging
import os
import re
import threading
import time
from urllib.parse import urlparse
import uuid

import httpx

from hr_navigator.security.guardrails import redact_personal_identifiers

log = logging.getLogger(__name__)
DEFAULT_HOST = 'https://cloud.langfuse.com'
TIMEOUT_SECONDS = 5.0
FLUSH_SECONDS = 10.0
_VALID_ENVIRONMENT = re.compile(r'^(?!langfuse)[a-z0-9_-]{1,40}$')
_pending: set[threading.Thread] = set()
_pending_lock = threading.Lock()


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
        env = os.environ if env is None else env
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


def build_batch(event, config: LangfuseConfig) -> dict:
    """Turn one TraceEvent into a Langfuse ingestion batch: a trace, a route span and, if the model
    was called, a generation carrying the token usage and cost."""
    trace_id = uuid.uuid4().hex
    end = event.timestamp                     # the tracer stamps the event when the request finishes
    try:
        start = (datetime.fromisoformat(end) - timedelta(milliseconds=event.latency_ms or 0)).isoformat()
    except ValueError:
        start = end
    question = redact_personal_identifiers(event.query) if config.send_query_text else '[not sent]'
    metadata = {'route_taken': event.route_taken, 'status': event.status, 'latency_ms': event.latency_ms,
                'citation_count': len(event.citations)}
    trace = {'id': trace_id, 'timestamp': event.timestamp, 'name': 'chat',
             'sessionId': event.session_id, 'environment': config.environment,
             'input': {'question': question},
             'output': {'status': event.status, 'route_taken': event.route_taken,
                        'citations': list(event.citations)},
             'metadata': metadata, 'tags': [event.route_taken, event.status]}
    span = {'id': uuid.uuid4().hex, 'traceId': trace_id, 'name': event.route_taken,
            'startTime': start, 'endTime': end, 'environment': config.environment,
            'metadata': metadata, 'level': 'DEFAULT' if event.status != 'error' else 'ERROR'}
    batch = [{'id': uuid.uuid4().hex, 'timestamp': event.timestamp, 'type': 'trace-create', 'body': trace},
             {'id': uuid.uuid4().hex, 'timestamp': event.timestamp, 'type': 'span-create', 'body': span}]
    if event.prompt_tokens or event.completion_tokens:
        generation = {'id': uuid.uuid4().hex, 'traceId': trace_id, 'name': 'chat-model',
                      'startTime': start, 'endTime': end, 'environment': config.environment,
                      'usageDetails': {'input': event.prompt_tokens, 'output': event.completion_tokens}}
        if event.estimated_cost_usd and event.estimated_cost_usd > 0:   # unknown price: no cost, not zero
            generation['costDetails'] = {'total': event.estimated_cost_usd}
        batch.append({'id': uuid.uuid4().hex, 'timestamp': event.timestamp,
                      'type': 'generation-create', 'body': generation})
    return {'batch': batch}


def send(event, config: LangfuseConfig, client: httpx.Client | None = None) -> bool:
    """Send one event now. Returns True when Langfuse accepted it; never raises."""
    try:
        payload = build_batch(event, config)
        owned = client is None
        client = client or httpx.Client(timeout=TIMEOUT_SECONDS)
        try:
            response = client.post(f'{config.host}/api/public/ingestion', json=payload,
                                   auth=(config.public_key, config.secret_key))
        finally:
            if owned:
                client.close()
        if response.status_code >= 300 and response.status_code != 207:
            log.warning('Langfuse rejected a trace: HTTP %s', response.status_code)
            return False
        errors = (response.json() or {}).get('errors') if response.content else None
        if errors:
            log.warning('Langfuse reported %d trace error(s)', len(errors))
            return False
        return True
    except Exception as exc:  # tracing must never break the app
        log.warning('Could not send trace to Langfuse: %s', type(exc).__name__)
        return False


def export_trace(event, env=None) -> threading.Thread | None:
    """Send the event in the background if Langfuse is configured; otherwise do nothing."""
    try:
        config = LangfuseConfig.from_env(env)
    except ValueError as exc:
        log.warning('Langfuse export disabled: %s', exc)
        return None
    if config is None:
        return None
    thread = threading.Thread(target=_send_and_forget, args=(event, config), daemon=True, name='langfuse-export')
    with _pending_lock:
        _pending.add(thread)
    thread.start()
    return thread


def _send_and_forget(event, config: LangfuseConfig) -> None:
    try:
        send(event, config)
    finally:
        with _pending_lock:
            _pending.discard(threading.current_thread())


def flush(timeout: float = FLUSH_SECONDS) -> int:
    """Wait up to timeout seconds for traces still being sent; return how many are left."""
    deadline = time.monotonic() + timeout
    while True:
        with _pending_lock:
            waiting = list(_pending)
        if not waiting:
            return 0
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            log.warning('%d trace(s) not sent to Langfuse before exit', len(waiting))
            return len(waiting)
        waiting[0].join(remaining)


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
