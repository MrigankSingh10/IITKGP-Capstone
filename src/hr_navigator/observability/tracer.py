import json
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel, Field

from hr_navigator.observability.langfuse_export import export_trace

TRACE_LOG_PATH = Path("reports/agent_traces.jsonl")
PRICING_PATH = Path("configs/pricing.json")


class TraceEvent(BaseModel):
    timestamp: str
    session_id: str
    employee_id: str | None = None
    query: str
    route_taken: str
    latency_ms: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float | None = None  # None when no price is configured
    citations: list[str] = Field(default_factory=list)
    status: str = "ok"


def estimate_cost(
    model_key: str,
    prompt_tokens: int,
    completion_tokens: int,
    pricing_path: Path = PRICING_PATH,
) -> float | None:
    """Estimated cost from configs/pricing.json, or None when no price is configured.

    Reads the project format (input_per_million_tokens / output_per_million_tokens, at the top level
    or under a model key) and the older per-1k layout. A missing price is unknown, not zero.
    """
    if not pricing_path.exists():
        return None
    try:
        data = json.loads(pricing_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    rates = data.get(model_key) if isinstance(data.get(model_key), dict) else None
    rates = rates or (data.get("default") if isinstance(data.get("default"), dict) else None) or data
    try:
        if rates.get("input_per_million_tokens") is not None and rates.get("output_per_million_tokens") is not None:
            per_token_in = float(rates["input_per_million_tokens"]) / 1_000_000
            per_token_out = float(rates["output_per_million_tokens"]) / 1_000_000
        elif rates.get("input_per_1k", rates.get("input")) is not None and \
                rates.get("output_per_1k", rates.get("output")) is not None:
            per_token_in = float(rates.get("input_per_1k", rates.get("input"))) / 1000
            per_token_out = float(rates.get("output_per_1k", rates.get("output"))) / 1000
        else:
            return None
    except (TypeError, ValueError):
        return None
    return round(prompt_tokens * per_token_in + completion_tokens * per_token_out, 6)


def log_trace(event: TraceEvent, trace_path: Path = TRACE_LOG_PATH) -> None:
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8") as handle:
        handle.write(event.model_dump_json() + "\n")
    export_trace(event)  # also sends to the Langfuse dashboard when LANGFUSE_* keys are set


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()