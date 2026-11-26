import asyncio
import json
import os
import re
import sqlite3
import time
from functools import lru_cache
from pathlib import Path
from threading import Event

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from hr_navigator.clients.api import APIConfig, HostedClient
from hr_navigator.retrieval.review_adapter import ReviewAdapter, ReviewRequest
from hr_navigator.retrieval.search import unsupported_query
from hr_navigator.retrieval.source_context import enrich_pages, load_source_context
from hr_navigator.security.guardrails import (
    RateLimiter,
    redact_personal_identifiers,
    validate_user_input,
)
from hr_navigator.observability.tracer import (
    TraceEvent,
    estimate_cost,
    log_trace,
    utc_now_iso,
)
from hr_navigator.demo import answer_leave_balance_question, is_leave_balance_question

ROOT = Path(__file__).resolve().parents[2]
app = FastAPI(title="HR Policy Navigator API", version="0.2.0")
rate_limiter = RateLimiter(max_requests=30, window_seconds=60)
_MINIMUM_WAGE = re.compile(r'\bminimum wages?\b', re.I)
_PERSONAL_RATE = re.compile(
    r'\b(?:exact|applicable)\s+minimum wages?\b'
    r'|\b(?:my|our)\s+minimum wages?\b'
    r'|\b(?:am i|are we|should i|must i|can i)\s+(?:be\s+)?(?:paid|pay|earn|get|receive)\b'
    r'|\bminimum wages?\s+(?:applicable\s+)?(?:for me|for my\b|i\b|we\b)', re.I,
)
_RATE_CLARIFICATION = (
    'The indexed documents explain how minimum wages are set, but don’t include verified rate schedules. '
    'To identify the details you’d need for a rate lookup, where do you work '
    '(state or Union territory and city or district), what kind of work do you do, '
    'and what date or pay period are you asking about? Please include your industry and skill category '
    'if you know them. You can reply with all the details in one message.'
)
_RATE_SOURCE_UNAVAILABLE = (
    'I can’t verify your exact minimum wage from the documents indexed here. '
    'I’d need an official rate schedule covering your work location, job classification, '
    'and the month and year the wages are for. Your usual payday does not identify that pay period.'
)


class ChatRequest(BaseModel):
    session_id: str
    employee_id: str | None = None
    query: str
    labour_code: str | None = None
    follow_up_to: str | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[str] = Field(default_factory=list)
    sources: list[dict] = Field(default_factory=list)
    route_taken: str
    latency_ms: float
    simulated: bool = False
    status: str = "ok"


@lru_cache(maxsize=1)
def get_review_adapter() -> ReviewAdapter:
    data_dir = ROOT / 'data/processed/accepted_ocr'
    with (data_dir / 'chunks_200.jsonl').open(encoding='utf-8') as stream:
        chunks = [json.loads(line) for line in stream if line.strip()]
    with (data_dir / 'pages.jsonl').open(encoding='utf-8') as stream:
        pages = {page['page_id']: page for page in (json.loads(line) for line in stream if line.strip())}
    enrich_pages(pages, load_source_context())
    return ReviewAdapter(chunks, pages)


def run_hr_pipeline(query: str, labour_code: str | None = None, *, progress=None):
    if progress is not None:
        progress('retrieval')
    adapter = get_review_adapter()
    review_request = ReviewRequest(query, labour_code=labour_code, top_k=5,
                                   prefer_verbatim=True, interactive=True)
    names = ('CHAT_BASE_URL', 'CHAT_MODEL', 'CHAT_API_KEY', 'CHAT_CA_FILE')
    configured = [bool(os.environ.get(name)) for name in names]
    if any(configured) and not all(configured):
        raise ValueError('Incomplete CHAT configuration: set all four CHAT_* variables or none.')
    local_config = ROOT / 'configs/chat.local.json'
    config = None
    if all(configured):
        config = APIConfig.from_env('CHAT')
    elif local_config.is_file():
        with local_config.open(encoding='utf-8') as stream:
            settings = json.load(stream)
        key_file = ROOT / settings['key_file']
        ca_file = ROOT / settings['ca_file']
        config = APIConfig(settings['base_url'], settings['model'],
                           key_file.read_text(encoding='utf-8').strip(), str(ca_file))
    if config is not None:
        client = HostedClient(config, retries=0)
        try:
            options = {'progress': progress} if progress is not None else {}
            result = adapter.retrieve(review_request, client, **options)
            usage = client.usage
        finally:
            client.close()
    else:
        result = adapter.retrieve(review_request)
        usage = {}
    return result, usage


def citation_label(source: dict) -> str:
    return f"{source.get('original_title', source.get('source_pdf_id', 'Source'))}, PDF page {source.get('page_number', '?')}"


def trace_outcome(payload: ChatRequest, route: str, status: str, latency_ms: float = 0.0,
                  query: str | None = None) -> None:
    """Record a request that ends before the normal trace (refusals, limits, errors).

    The question is masked and shortened; tracing problems never affect the response.
    """
    try:
        text = query if query is not None else redact_personal_identifiers(' '.join(payload.query.split()))
        log_trace(TraceEvent(timestamp=utc_now_iso(), session_id=redact_personal_identifiers(payload.session_id),
                             employee_id=None, query=text[:500], route_taken=route,
                             latency_ms=latency_ms, citations=[], status=status))
    except Exception:  # noqa: BLE001 - tracing must never break the request
        pass


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.post('/chat', response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    try:
        return answer_chat(payload)
    except HTTPException:
        raise                                   # already traced where it was raised
    except Exception:
        trace_outcome(payload, 'internal_error', 'error')
        raise


def asks_for_personal_minimum_wage(question: str) -> bool:
    return bool(_MINIMUM_WAGE.search(question) and _PERSONAL_RATE.search(question))


def answer_chat(payload: ChatRequest, progress=None) -> ChatResponse:
    if not rate_limiter.is_allowed(payload.session_id):
        trace_outcome(payload, 'rate_limited', 'rate_limited')
        raise HTTPException(status_code=429, detail='Rate limit exceeded. Try again shortly.')
    guard = validate_user_input(payload.query)
    trace_session_id = redact_personal_identifiers(payload.session_id)
    is_follow_up = bool(payload.follow_up_to and asks_for_personal_minimum_wage(payload.follow_up_to))
    if guard.allowed and is_follow_up:
        guard = validate_user_input(
            f'{payload.follow_up_to} Additional details: {guard.sanitized_query}'
        )
    if not guard.allowed:
        log_trace(TraceEvent(timestamp=utc_now_iso(), session_id=trace_session_id,
                             employee_id=None, query=guard.sanitized_query,
                             route_taken='guardrail_refusal', latency_ms=0.0,
                             citations=[], status='refused'))
        return ChatResponse(answer=guard.reason or 'Request refused.', route_taken='guardrail_refusal',
                            latency_ms=0.0, status='refused')
    if unsupported_query(guard.sanitized_query):
        trace_outcome(payload, 'unsupported_language', 'refused', query=guard.sanitized_query)
        return ChatResponse(answer='Please ask your question in English.', route_taken='unsupported_language',
                            latency_ms=0.0, status='refused')
    if is_follow_up or asks_for_personal_minimum_wage(guard.sanitized_query):
        # The current corpus contains the statutory framework but no validated
        # rate schedules for determining an individual worker's exact rate.
        route = 'minimum_wage_source_unavailable' if is_follow_up else 'minimum_wage_clarification'
        status = 'escalate' if is_follow_up else 'clarification_required'
        log_trace(TraceEvent(timestamp=utc_now_iso(), session_id=trace_session_id,
                             employee_id=None, query=guard.sanitized_query,
                             route_taken=route, latency_ms=0.0, citations=[], status=status))
        return ChatResponse(answer=_RATE_SOURCE_UNAVAILABLE if is_follow_up else _RATE_CLARIFICATION,
                            route_taken=route, latency_ms=0.0, status=status)

    # Handle read-only leave-balance questions with the synthetic employee tools.
    # This branch must run before document retrieval so balance questions are not
    # incorrectly routed to PDF search.
    if is_leave_balance_question(guard.sanitized_query):
        start = time.perf_counter()
        try:
            answer = answer_leave_balance_question(
                query=guard.sanitized_query,
                employee_id=payload.employee_id,
            )
        except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
            trace_outcome(payload, 'leave_balance_tool', 'error',
                          round((time.perf_counter() - start) * 1000.0, 2), guard.sanitized_query)
            raise HTTPException(
                status_code=503,
                detail='Synthetic leave-balance demo is unavailable. Check the local fixtures and database.',
            ) from exc

        latency_ms = round((time.perf_counter() - start) * 1000.0, 2)
        log_trace(
            TraceEvent(
                timestamp=utc_now_iso(),
                session_id=trace_session_id,
                employee_id=None,
                query=guard.sanitized_query,
                route_taken='leave_balance_tool',
                latency_ms=latency_ms,
                citations=[],
                status='ok',
            )
        )
        return ChatResponse(
            answer=answer,
            citations=[],
            route_taken='leave_balance_tool',
            latency_ms=latency_ms,
            simulated=True,
            status='ok',
        )

    start = time.perf_counter()
    try:
        options = {'progress': progress} if progress is not None else {}
        result, usage = run_hr_pipeline(guard.sanitized_query, payload.labour_code, **options)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        citations = [citation_label(source) for source in result.sources]
        if result.decision == 'review_required':
            answer = result.draft_not_verified or 'No draft was returned.'
        elif result.decision == 'evidence_only':
            answer = result.reason or ('Candidate source passages are shown below for review. '
                                       'Configure the chat model to generate a draft answer.')
        else:
            answer = result.reason or 'No verifiable source passages were found.'
            if result.sources:
                answer += ' The passages below are available for review.'
        prompt_tokens = usage.get('prompt_tokens', 0)
        completion_tokens = usage.get('completion_tokens', 0)
        log_trace(TraceEvent(timestamp=utc_now_iso(), session_id=trace_session_id,
                             employee_id=None, query=guard.sanitized_query,
                             route_taken='document_review', latency_ms=latency_ms,
                             prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                             estimated_cost_usd=estimate_cost('default', prompt_tokens, completion_tokens),
                             citations=citations, status=result.decision))
        return ChatResponse(answer=answer, citations=citations, sources=result.sources,
                            route_taken='document_review', latency_ms=latency_ms, status=result.decision)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        trace_outcome(payload, 'document_review', 'error',
                      round((time.perf_counter() - start) * 1000, 2), guard.sanitized_query)
        raise HTTPException(status_code=503, detail='Document retrieval is unavailable. Check the corpus and chat configuration.') from exc



@app.post('/chat/stream')
async def chat_stream(payload: ChatRequest) -> StreamingResponse:
    async def events():
        loop = asyncio.get_running_loop()
        queue = asyncio.Queue()
        disconnected = Event()

        def publish(event):
            if not disconnected.is_set():
                loop.call_soon_threadsafe(queue.put_nowait, event)

        def progress(stage):
            publish({'type': 'progress', 'stage': stage})

        def run():
            try:
                result = answer_chat(payload, progress)
                publish({'type': 'result', 'response': result.model_dump()})
            except HTTPException as exc:
                publish({'type': 'error', 'message': exc.detail})
            except Exception:
                trace_outcome(payload, 'internal_error', 'error')
                publish({'type': 'error', 'message': 'Unable to complete the chat request.'})

        worker = asyncio.create_task(asyncio.to_thread(run))
        try:
            while True:
                event = await queue.get()
                yield json.dumps(event) + '\n'
                if event['type'] != 'progress':
                    break
        finally:
            disconnected.set()
            worker.cancel()

    return StreamingResponse(
        events(),
        media_type='application/x-ndjson',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no-cache'}
    )
