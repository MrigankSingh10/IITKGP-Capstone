import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from hr_navigator.observability.tracer import (
    TraceEvent,
    estimate_cost,
    log_trace,
    utc_now_iso,
)
from hr_navigator.security.guardrails import RateLimiter, validate_user_input

app = FastAPI(title="HR Policy Navigator API", version="0.1.0")
rate_limiter = RateLimiter(max_requests=30, window_seconds=60)


class ChatRequest(BaseModel):
    session_id: str
    employee_id: str | None = None
    query: str


class ChatResponse(BaseModel):
    answer: str
    citations: list[str] = Field(default_factory=list)
    route_taken: str
    latency_ms: float


def invoke_agent_or_stub(
    session_id: str,
    employee_id: str | None,
    query: str,
) -> tuple[str, list[str], str, int, int]:
    """
    Replace or connect this function to Member 3's LangGraph workflow once ready.
    Returns: (answer, citations, route_taken, prompt_tokens, completion_tokens)
    """
    _ = (session_id, employee_id)
    answer = (
        f"Received query: '{query}'. Track 3 agent workflow integration is pending; "
        "connect the LangGraph runner in invoke_agent_or_stub()."
    )
    return answer, ["docs/acme_handbook_v0.1.md"], "stub_route", 0, 0


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    if not rate_limiter.is_allowed(payload.session_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again shortly.")

    guard = validate_user_input(payload.query)
    if not guard.allowed:
        refusal_text = guard.reason or "Request refused."
        log_trace(
            TraceEvent(
                timestamp=utc_now_iso(),
                session_id=payload.session_id,
                employee_id=payload.employee_id,
                query=payload.query,
                route_taken="guardrail_refusal",
                latency_ms=0.0,
                citations=[],
                status="refused",
            )
        )
        return ChatResponse(
            answer=refusal_text,
            citations=[],
            route_taken="guardrail_refusal",
            latency_ms=0.0,
        )

    start = time.perf_counter()
    try:
        answer, citations, route_taken, p_tok, c_tok = invoke_agent_or_stub(
            session_id=payload.session_id,
            employee_id=payload.employee_id,
            query=guard.sanitized_query,
        )
        latency_ms = round((time.perf_counter() - start) * 1000.0, 2)
        log_trace(
            TraceEvent(
                timestamp=utc_now_iso(),
                session_id=payload.session_id,
                employee_id=payload.employee_id,
                query=guard.sanitized_query,
                route_taken=route_taken,
                latency_ms=latency_ms,
                prompt_tokens=p_tok,
                completion_tokens=c_tok,
                estimated_cost_usd=estimate_cost("default", p_tok, c_tok),
                citations=citations,
                status="ok",
            )
        )
        return ChatResponse(
            answer=answer,
            citations=citations,
            route_taken=route_taken,
            latency_ms=latency_ms,
        )
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start) * 1000.0, 2)
        log_trace(
            TraceEvent(
                timestamp=utc_now_iso(),
                session_id=payload.session_id,
                employee_id=payload.employee_id,
                query=guard.sanitized_query,
                route_taken="error_recovery",
                latency_ms=latency_ms,
                citations=[],
                status="error",
            )
        )
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {exc}") from exc