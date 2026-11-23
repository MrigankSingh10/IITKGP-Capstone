"""Typed, review-only document retrieval boundary for orchestration.

All corpus material and model output are untrusted. This adapter does not establish
relevance, entailment, source currency, or legal applicability.
"""
from dataclasses import dataclass
import re
from typing import Any, Literal, Mapping, Protocol, Sequence

from .draft_review import code_title_matches, draft_for_review, explicit_code, subsection_bounds
from .grounded import extractive_evidence
from .search import english_eligible, search, unsupported_query


_INCLUSION_QUESTION = re.compile(r'^does\s+([\w ]{1,60}?)\s+include\s+([\w ]{1,80})\?$', re.I)
_NAMED_DEFINITION = re.compile(
    r"""^(?:what\s+is\s+the\s+definition\s+of|define)\s+"""
    r"""(?P<quote>["'])?(?P<term>[\w -]{1,80}?)(?(quote)(?P=quote))\s+(?:under|in)\s+""",
    re.I,
)
_QUESTION_QUOTES = str.maketrans({'“': '"', '”': '"', '‘': "'", '’': "'"})
_DEFINITION_END = re.compile(r'(?m)^[ \t]*\([a-z]{1,3}\)\s*["“]|^[ \t]*\d+\.\s*\(1\)')


def normalized_definition_question(question):
    return ' '.join(question.translate(_QUESTION_QUOTES).split())


def quoted_definition(request, evidence, pages):
    """Quote a named definition up to the next clause, keeping PDF pages separate."""
    question = normalized_definition_question(request.question)
    match = _NAMED_DEFINITION.match(question)
    if not match or not re.fullmatch(
        r'(?:the )?(?:code on wages|industrial relations code|code on social security|'
        r'social security code|occupational safety,? health and working conditions code|'
        r'osh(?: & wc)? code)(?:,? \d{4})?\??', question[match.end():], re.I
    ):
        return None
    verified = {
        source['page_number']: source
        for source in extractive_evidence(evidence, pages)['sources']
    }
    first = evidence[0]
    first_number = first['pdf_page_number']
    term = r'\s+'.join(map(re.escape, match['term'].split()))
    heading = definition_heading(term)
    sources = []
    for number in (first_number, first_number + 1):
        if number not in verified:
            return None
        page = pages[f"{first['source_pdf_id']}:page_{number:04d}"]
        text = page['text']
        if number == first_number:
            start = heading.search(text)
            if start is None:
                return None
            end = _DEFINITION_END.search(text, start.end())
            text = text[start.start():end.start() if end else len(text)]
        else:
            end = _DEFINITION_END.search(text)
            text = text[:end.start()] if end else text
        sources.append({**verified[number], 'passage': text.strip()})
        if end:
            lines = sources[0]['passage'].splitlines()
            opening = []
            for line in lines:
                if opening and re.match(r'^\s*(?:Provided\b|but does not include\b|Explanation\b)', line):
                    break
                if line.strip():
                    opening.append(line.strip())
            return ReviewResult(
                'evidence_only', sources,
                reason=f"**{sources[0]['original_title']}** defines the term as follows:\n\n"
                       f"> {' '.join(opening)}\n\n"
                       "Open the cited PDF excerpts for the full definition and any exceptions.",
            )
    return None


def definition_heading(term):
    return re.compile(rf'(?m)^\s*\([a-z]{{1,3}}\)\s*["“]{term}["”]\s+means\b', re.I)


def definition_evidence(request, chunks):
    """Start at a named Act's definition and include nearby passages for qualifiers."""
    match = _NAMED_DEFINITION.match(normalized_definition_question(request.question))
    code = explicit_code(request.question)
    if not match or not code:
        return []
    term = r'\s+'.join(map(re.escape, match['term'].split()))
    heading = definition_heading(term)
    act_chunks = [
        chunk for chunk in chunks
        if chunk.get('scope') == request.source_scope and chunk.get('category') == 'Acts'
        and (not request.labour_code or chunk.get('labour_code') == request.labour_code)
        and code_title_matches(code, chunk['original_title']) and english_eligible(chunk)
    ]
    matches = [chunk for chunk in act_chunks if heading.search(chunk['text'])]
    if len({chunk['page_id'] for chunk in matches}) != 1:
        return []
    first = min(matches, key=lambda chunk: chunk['char_start'])
    start = first['pdf_page_number'], first['char_start']
    nearby = [
        chunk for chunk in act_chunks
        if chunk['source_pdf_id'] == first['source_pdf_id']
        and (chunk['pdf_page_number'], chunk['char_start']) >= start
        and chunk['pdf_page_number'] <= start[0] + 1
    ]
    nearby.sort(key=lambda chunk: (chunk['pdf_page_number'], chunk['char_start']))
    return nearby[:request.top_k]


def quoted_inclusion(request, chunks, pages):
    """Find a verbatim, standalone definition clause for a simple inclusion question."""
    match = _INCLUSION_QUESTION.fullmatch(' '.join(request.question.split()))
    if not match:
        return None
    subject, included = (r'\s+'.join(map(re.escape, phrase.split())) for phrase in match.groups())
    clause = re.compile(rf'(?m)^\s*\([a-z]{{1,3}}\)\s*["“]{subject}["”]\s+includes\s+{included}\s*[;.]', re.I)
    found = {}
    for chunk in chunks:
        if (chunk.get('category') != 'Acts' or chunk.get('scope') != request.source_scope
                or (request.labour_code and chunk.get('labour_code') != request.labour_code)
                or not english_eligible(chunk)):
            continue
        quote = clause.search(chunk['text'])
        if quote is None:
            continue
        sources = extractive_evidence([chunk], pages)['sources']
        if sources:
            source = sources[0]
            source['passage'] = quote.group().strip()
            found[(chunk['page_id'], source['passage'])] = source
    if len(found) == 1:
        source, = found.values()
        return ReviewResult('evidence_only', [source],
                            reason=f"**{source['original_title']}** states:\n\n> {source['passage']}")
    return None


def add_page_context(question, evidence, pages):
    """Keep context contiguous on the registered page around a ranked hit."""
    expanded = []
    for chunk in evidence:
        if not extractive_evidence([chunk], pages)['sources']:
            continue
        text = pages[chunk['page_id']]['text']
        if len(text) <= 3400:
            start, end = 0, len(text)
        else:
            start = max(0, chunk['char_start'] - 800)
            end = min(len(text), chunk['char_end'] + 400)
        bounds = subsection_bounds(question, text)
        if bounds and bounds[1] - bounds[0] <= 2400:
            start, end = bounds
        expanded.append({**chunk, 'char_start': start, 'char_end': end, 'text': text[start:end]})
    return expanded


class ChatClient(Protocol):
    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class ReviewRequest:
    question: str
    source_scope: Literal['statutory'] = 'statutory'
    labour_code: str | None = None
    top_k: int = 3
    prefer_verbatim: bool = False
    interactive: bool = False


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

    def retrieve(self, request: ReviewRequest, client: ChatClient | None = None, *, progress=None) -> ReviewResult:
        if (not isinstance(request.question, str) or not request.question.strip()
                or unsupported_query(request.question) or request.source_scope != 'statutory'
                or isinstance(request.top_k, bool) or not isinstance(request.top_k, int)
                or not 1 <= request.top_k <= 100):
            return ReviewResult('escalate', [], reason='Unsupported or invalid review request.')
        try:
            evidence = []
            if request.prefer_verbatim:
                direct = quoted_inclusion(request, self._chunks, self._pages)
                if direct is not None:
                    return direct
                evidence = definition_evidence(request, self._chunks)
                if evidence:
                    direct = quoted_definition(request, evidence, self._pages)
                    if direct is not None:
                        return direct
            if not evidence:
                chunks = self._chunks
                code = explicit_code(request.question) if request.interactive else None
                category = None
                if code:
                    chunks = [chunk for chunk in chunks if code_title_matches(code, chunk['original_title'])]
                    if (re.search(r'\bsections?\s+\d+\b', request.question, re.I)
                            and not re.search(r'\b(?:rules?|notifications?|faqs?|circulars?)\b', request.question, re.I)):
                        category = 'Acts'
                evidence = search(
                    request.question, chunks, source_scope=request.source_scope,
                    labour_code=request.labour_code, category=category, top_k=request.top_k,
                    mode='bm25_rerank' if request.interactive else 'bm25',
                )
                if request.interactive:
                    evidence = add_page_context(request.question, evidence, self._pages)
            result = (draft_for_review(client, request.question, evidence, self._pages,
                                       select_passages=request.interactive, progress=progress)
                      if client is not None else extractive_evidence(evidence, self._pages))
            return ReviewResult(decision=result['decision'], sources=result['sources'],
                                reason=result.get('reason') or (result.get('answer') if result['decision'] == 'escalate' else None),
                                draft_not_verified=result.get('draft_not_verified'),
                                uncertainty=result.get('uncertainty'), model_check=result.get('model_check'))
        except (KeyError, TypeError, ValueError, IndexError):
            return ReviewResult('escalate', [], reason='Retrieval or evidence validation failed.')
