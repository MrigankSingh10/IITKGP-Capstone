import re
import time
from collections import defaultdict
from pydantic import BaseModel


class GuardrailResult(BaseModel):
    allowed: bool
    reason: str | None = None
    sanitized_query: str


INJECTION_PATTERNS = [
    r"ignore (all )?(previous|prior) instructions",
    r"reveal (the )?(system|developer) prompt",
    r"you are now (a|an)",
    r"bypass (policy|rules|guardrails|refusal)",
]

OUT_OF_SCOPE_PATTERNS = [
    r"\bstock tip(s)?\b",
    r"\bmedical diagnosis\b",
    r"\blegal advice\b",
]


class RateLimiter:
    def __init__(self, max_requests: int = 20, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, session_id: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        active = [ts for ts in self._requests[session_id] if ts > cutoff]
        if len(active) >= self.max_requests:
            self._requests[session_id] = active
            return False
        active.append(now)
        self._requests[session_id] = active
        return True


def validate_user_input(query: str) -> GuardrailResult:
    cleaned = " ".join(query.strip().split())
    if not cleaned:
        return GuardrailResult(
            allowed=False,
            reason="Please enter a non-empty HR policy or benefit question.",
            sanitized_query="",
        )

    lowered = cleaned.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lowered):
            return GuardrailResult(
                allowed=False,
                reason="Request refused: prompt-injection or instruction-override pattern detected.",
                sanitized_query=cleaned,
            )

    for pattern in OUT_OF_SCOPE_PATTERNS:
        if re.search(pattern, lowered):
            return GuardrailResult(
                allowed=False,
                reason="Request refused: outside supported HR policy scope.",
                sanitized_query=cleaned,
            )

    return GuardrailResult(allowed=True, sanitized_query=cleaned)