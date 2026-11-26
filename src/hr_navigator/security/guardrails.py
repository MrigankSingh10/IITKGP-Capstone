import base64
import binascii
import re
import time
import unicodedata
from collections import defaultdict
from pydantic import BaseModel


class GuardrailResult(BaseModel):
    allowed: bool
    reason: str | None = None
    sanitized_query: str


# Matched against a normalised copy of the question (see _normalise): lower case, spacing and
# punctuation tricks removed, common digit/symbol swaps undone, and any Base64 text decoded.
# Patterns aim at the request ("ignore your instructions"), not at words that also appear in
# ordinary HR questions ("ignore a grievance", "previous instructions for the old portal").
_OVERRIDE_VERBS = (r"ignore|disregard|forget|discard|drop|set aside|pay no attention to|override|bypass|"
                   r"skip|abandon|stop following|throw away|get rid of")
_RULE_WORDS = (r"instructions?|rules|guidelines?|guidance|directions?|directives?|restrictions?|"
               r"constraints|programming|system prompt|prompt|safeguards?|guardrails?|filters?|safety")
_ROLE_TARGETS = (r"unrestricted|unfiltered|jailbroken|uncensored|admin(?:istrator)?|superuser|root|"
                 r"hr director|director|payroll system|database|system administrator|dan\b|god")

INJECTION_PATTERNS = [
    # override requests, also paraphrased: "set aside the guidance you were configured with"
    rf"\b(?:{_OVERRIDE_VERBS})\b(?:\s+\S+){{0,4}}?\s+(?:{_RULE_WORDS})\b",
    r"\b(?:ignore|disregard|forget)\s+(?:everything|anything|all)\s+(?:you\s+)?(?:were|have been|'ve been|was)\s+"
    r"(?:told|given|instructed|taught)",
    r"\b(?:previous|prior|earlier|old|original|existing)\s+(?:instructions|rules|guidelines|restrictions)\s+"
    r"(?:no longer apply|do not apply|don't apply|are (?:void|cancelled|canceled|revoked|lifted))",
    r"\bfrom now on\b.{0,40}\b(?:no|without)\s+(?:restrictions|rules|limits|filters)",
    r"\b(?:answer|respond|reply|talk)\w*\s+without\s+(?:any\s+)?(?:restrictions|rules|limits|filters|censorship)",
    # role tags and fake approvals typed into the question
    r"^(?:system|assistant|developer)\s*:",
    r"\[(?:system|admin|developer)\]|<\|?(?:system|im_start)\|?>",
    r"\bapproval[_ ]token\s*[:=]",
    # prompt and secret extraction
    r"\b(?:reveal|show|print|repeat|output|display|paste|share|leak|dump|give|tell|send|write)\b(?:\s+\S+){0,4}?\s+"
    r"(?:system prompt|developer (?:message|prompt|instructions)|initial (?:prompt|instructions|message)|"
    r"hidden (?:instructions|prompt|configuration|rules)|your (?:instructions|prompt|configuration|rules)|"
    r"(?:api|secret|private) key|access token|token you use|credentials)",
    r"\bwhat (?:is|are|does|did)\s+(?:your|the)\s+(?:system prompt|hidden (?:configuration|instructions|prompt)|"
    r"initial instructions|developer message)",
    r"\binstructions\s+(?:did|do)\s+your\s+(?:developers?|creators?|makers?|programmers?)",
    r"\brepeat\s+(?:everything|all|the text|what is|whatever is)\s+(?:written\s+)?(?:above|before)",
    # role play and privilege escalation
    rf"\b(?:you are now|pretend (?:to be|you are|you're)|act as|roleplay as|role-play as|role play as|"
    rf"play the role of|become)\b(?:\s+\S+){{0,3}}?\s+(?:{_ROLE_TARGETS})",
    r"\b(?:developer|god|jailbreak|dan|unrestricted|admin)\s+mode\b",
    r"\byou are dan\b|\bdo anything now\b",
    r"\b(?:you (?:now )?have|grant(?:ed)? you|give you)\s+(?:full\s+)?(?:admin|administrator|root|superuser|elevated)?\s*"
    r"(?:privileges|access rights|permissions|database access)",
    r"\bfull (?:database|system|admin) access\b",
    # asking the assistant to follow encoded text
    r"\b(?:decode|decrypt|base64)\b.{0,40}\b(?:follow|execute|run|obey|do what)",
]

# Requests for other people's personal data in bulk; the identity layer must also enforce this.
PERSONAL_DATA_PATTERNS = [
    r"\b(?:list|show|give|print|output|dump|export|display|tell)\b(?:\s+me)?\s+(?:all|every|each|everyone'?s?|"
    r"the (?:full|entire|complete|whole))\s+(?:\S+\s+){0,2}?(?:employees?'?\s*)?(?:salary|salaries|salary slips?|pay|"
    r"records|table|data|leave balances?|balances|personal details|phone numbers|addresses)",
    r"\b(?:every|each|all)\s+(?:employee|manager|worker|staff)'?s?\s+(?:salary|salaries|pay|leave balance|"
    r"balances|records|personal details)",
]

OUT_OF_SCOPE_PATTERNS = [
    r"\bstock tips?\b",
    r"\bmedical diagnosis\b",
    # personal legal action (general legal questions about the Codes stay allowed)
    r"\b(?:sue|suing|lawsuit)\b",
    r"\b(?:file|filing|start)\s+(?:a\s+)?(?:court case|case|lawsuit|suit)\s+against\b",
    r"\blegal (?:notice|action)\b.{0,30}\b(?:against|to|for)\b|\b(?:draft|write)\b.{0,20}\blegal notice\b",
    r"\blegal advice (?:on|about|for)\s+(?:suing|my|a case|filing)",
    # health
    r"\bwhat (?:illness|disease|condition|infection) (?:do|might|could) i have\b",
    r"\b(?:which|what) (?:medicines?|medications?|tablets?|drugs?|treatment) (?:should|can|do|must) i\b",
    r"\bdiagnose (?:me|my)\b",
    # investment
    r"\b(?:which|what) (?:shares|stocks|mutual funds?|crypto(?:currency|currencies)?)\b",
    r"\bshould i (?:buy|sell|invest)\b|\bgood time to (?:buy|sell|invest)\b",
]

_LEET = str.maketrans({'0': 'o', '1': 'i', '3': 'e', '4': 'a', '5': 's', '7': 't', '@': 'a', '$': 's', '!': 'i'})
_ZERO_WIDTH = dict.fromkeys(map(ord, '\u200b\u200c\u200d\u2060\ufeff'))
_SPACED = re.compile(r"\b(?:[a-z][\s.\-_*]){2,}[a-z]\b")
_BASE64 = re.compile(r"[A-Za-z0-9+/]{16,}={0,2}")


def _normalise(text: str) -> list[str]:
    """Return the variants of the question that the patterns are checked against."""
    plain = unicodedata.normalize('NFKC', text).translate(_ZERO_WIDTH).lower()
    plain = " ".join(plain.split())
    joined = _SPACED.sub(lambda m: re.sub(r"[\s.\-_*]", "", m.group(0)), plain)
    unleet = joined.translate(_LEET)
    variants = [plain, joined, unleet]
    for token in _BASE64.findall(text):
        try:
            decoded = base64.b64decode(token + '=' * (-len(token) % 4), validate=True).decode('utf-8')
        except (binascii.Error, UnicodeDecodeError, ValueError):
            continue
        if decoded and sum(ch.isprintable() for ch in decoded) / len(decoded) > 0.9:
            variants.append(" ".join(decoded.lower().split()))
    return list(dict.fromkeys(variants))


def _matches(patterns: list[str], variants: list[str]) -> bool:
    return any(re.search(pattern, variant) for pattern in patterns for variant in variants)


_PERSONAL_IDENTIFIERS = (
    (re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', re.I), '[PAN removed]'),
    (re.compile(r'(?<!\d)[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}(?!\d)'), '[Aadhaar removed]'),
    (re.compile(r'(?<!\d)(?:\+91[ -]?)?[6-9](?:\d{4}[ -]?\d{5}|\d{2}[ -]\d{3}[ -]\d{4})(?!\d)'),
     '[phone removed]'),
    (re.compile(r'\b[\w.+-]+@[\w.-]+\.[A-Z]{2,}\b', re.I), '[email removed]'),
    (re.compile(r'(\bemployee\s+(?:id|number)\s*[:=#]\s*["\']?)(?:EMP[ -]\d+|[\w-]+)\b', re.I),
     r'\1[employee ID removed]'),
    # In prose, "employee ID is" can be followed by an adjective rather than an ID.
    (re.compile(r'(\bemployee\s+(?:id|number)\s+is\s+["\']?)(?=[\w-]*\d)[\w-]+\b', re.I),
     r'\1[employee ID removed]'),
    (re.compile(r'\bEMP[- ]\d+\b', re.I), '[employee ID removed]'),
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

    variants = _normalise(cleaned)
    if _matches(INJECTION_PATTERNS, variants):
        return GuardrailResult(
            allowed=False,
            reason="Request refused: prompt-injection or instruction-override pattern detected.",
            sanitized_query=sanitized,
        )

    if _matches(PERSONAL_DATA_PATTERNS, variants):
        return GuardrailResult(
            allowed=False,
            reason="Request refused: other people's personal data cannot be shared.",
            sanitized_query=sanitized,
        )

    if _matches(OUT_OF_SCOPE_PATTERNS, variants):
        return GuardrailResult(
            allowed=False,
            reason="Request refused: outside supported HR policy scope.",
            sanitized_query=sanitized,
        )

    return GuardrailResult(allowed=True, sanitized_query=sanitized)
