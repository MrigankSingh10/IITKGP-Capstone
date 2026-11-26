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
    estimated_cost_usd: float = 0.0
    citations: list[str] = Field(default_factory=list)
    status: str = "ok"


def estimate_cost(
    model_key: str,
    prompt_tokens: int,
    completion_tokens: int,
    pricing_path: Path = PRICING_PATH,
) -> float:
    if not pricing_path.exists():
        return 0.0
    try:
        data = json.loads(pricing_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0.0

    rates = data.get(model_key) or data.get("default") or {}
    in_rate = float(rates.get("input_per_1k", rates.get("input", 0.0)) or 0.0)
    out_rate = float(rates.get("output_per_1k", rates.get("output", 0.0)) or 0.0)
    total = (prompt_tokens / 1000.0) * in_rate + (completion_tokens / 1000.0) * out_rate
    return round(total, 6)


def log_trace(event: TraceEvent, trace_path: Path = TRACE_LOG_PATH) -> None:
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8") as handle:
        handle.write(event.model_dump_json() + "\n")
    export_trace(event)  # also sends to the Langfuse dashboard when LANGFUSE_* keys are set


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()