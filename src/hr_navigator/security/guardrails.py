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

_PERSONAL_IDENTIFIERS = (
    (re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', re.I), '[PAN removed]'),
    (re.compile(r'(?<!\d)[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}(?!\d)'), '[Aadhaar removed]'),
    (re.compile(r'(?<!\d)(?:\+91[ -]?)?[6-9]\d{4}[ -]?\d{5}(?!\d)'), '[phone removed]'),
    (re.compile(r'\b[\w.+-]+@[\w.-]+\.[A-Z]{2,}\b', re.I), '[email removed]'),
    (re.compile(r'\b(?:employee\s+(?:id|number)\s*[:=#-]?\s*)?(?:EMP[- ]\d+)\b', re.I),
     '[employee ID removed]'),
    (re.compile(r'\bemployee\s+(?:id|number)\s*[:=#]\s*[\w-]+\b', re.I),
     '[employee ID removed]'),
)


def redact_personal_identifiers(text: str) -> str:
    for pattern, replacement in _PERSONAL_IDENTIFIERS:
        text = pattern.sub(replacement, text)
    return text


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
    sanitized = redact_personal_identifiers(cleaned)
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
                sanitized_query=sanitized,
            )

    for pattern in OUT_OF_SCOPE_PATTERNS:
        if re.search(pattern, lowered):
            return GuardrailResult(
                allowed=False,
                reason="Request refused: outside supported HR policy scope.",
                sanitized_query=sanitized,
            )

    return GuardrailResult(allowed=True, sanitized_query=sanitized)
