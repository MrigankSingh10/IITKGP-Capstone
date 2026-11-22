"""Typed, review-only document retrieval boundary for orchestration.

All corpus material and model output are untrusted. This adapter does not establish
relevance, entailment, source currency, or legal applicability.
"""
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Protocol, Sequence

from .draft_review import draft_for_review
from .grounded import extractive_evidence
from .search import search, unsupported_query


class ChatClient(Protocol):
    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class ReviewRequest:
    question: str
    source_scope: Literal['statutory'] = 'statutory'
    labour_code: str | None = None
    top_k: int = 3


@dataclass(frozen=True)
class ReviewResult:
    decision: Literal['evidence_only', 'review_required', 'escalate']
    sources: list[dict[str, Any]]
    reason: str | None = None
    draft_not_verified: str | None = None
    uncertainty: str | None = None
    model_check: str | None = None


class ReviewAdapter:
    """Offline BM25 over supplied corpus; optional injected model for review drafts."""
    def __init__(self, chunks: Sequence[dict[str, Any]], pages: Mapping[str, dict[str, Any]]):
        self._chunks = list(chunks)
        self._pages = dict(pages)

    def retrieve(self, request: ReviewRequest, client: ChatClient | None = None) -> ReviewResult:
        if (not isinstance(request.question, str) or not request.question.strip()
                or unsupported_query(request.question) or request.source_scope != 'statutory'
                or isinstance(request.top_k, bool) or not isinstance(request.top_k, int)
                or not 1 <= request.top_k <= 100):
            return ReviewResult('escalate', [], reason='Unsupported or invalid review request.')
        try:
            evidence = search(request.question, self._chunks, source_scope=request.source_scope,
                              labour_code=request.labour_code, top_k=request.top_k, mode='bm25')
            result = (draft_for_review(client, request.question, evidence, self._pages)
                      if client is not None else extractive_evidence(evidence, self._pages))
            return ReviewResult(decision=result['decision'], sources=result['sources'],
                                reason=result.get('reason') or (result.get('answer') if result['decision'] == 'escalate' else None),
                                draft_not_verified=result.get('draft_not_verified'),
                                uncertainty=result.get('uncertainty'), model_check=result.get('model_check'))
        except (KeyError, TypeError, ValueError, IndexError):
            return ReviewResult('escalate', [], reason='Retrieval or evidence validation failed.')
