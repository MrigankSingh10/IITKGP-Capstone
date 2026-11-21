"""Filtered lexical/dense retrieval, reciprocal-rank fusion and local reranking."""
from collections import Counter
import math
import re

import faiss
import numpy as np

from .section_lookup import section_candidates
from .proximity import proximity_scores


def unsupported_query(text):
    """Detect Devanagari input; Romanized language cannot be identified reliably."""
    return any('\u0900' <= char <= '\u097f' for char in text)


def english_eligible(chunk):
    """Conservative script-based passage filter, not language identification."""
    text = chunk.get('text', '')
    return (not unsupported_query(text)
            and sum('a' <= char.lower() <= 'z' for char in text) >= 3)


def terms(text):
    return re.findall(r'[^\W_]+', text.casefold(), re.UNICODE)


# Gazette instrument identifiers are precise references; punctuation and spacing
# vary between the query and official PDF extraction. Keep number and suffix exact.
_INSTRUMENT = re.compile(
    r"(?<![\w])(?:g\s*\.?\s*s\s*\.?\s*r|s\s*\.?\s*o)\s*\.?"
    r"\s*(\d+)\s*\(\s*([a-z])\s*\)", re.IGNORECASE)


def instrument_ids(text):
    return {(re.sub(r'[^a-z]', '', match.group(0).casefold().split(match.group(1))[0]),
             match.group(1), match.group(2).casefold())
            for match in _INSTRUMENT.finditer(text)}


# Interrogative boilerplate carries little legal meaning in ordinary questions.
# Keep negation, identifiers, and all other terms; fall back for short queries.
_QUERY_BOILERPLATE = frozenset({'what', 'when', 'where', 'which', 'who', 'how',
                                'does', 'do', 'did', 'is', 'are', 'was', 'were'})


def bm25(query, chunks):
    all_terms = set(terms(query))
    q = all_terms - _QUERY_BOILERPLATE or all_terms
    if not q or not chunks:
        return []
    docs = [terms(c['text']) for c in chunks]
    avg = sum(map(len, docs)) / len(docs) or 1
    df = Counter(token for doc in docs for token in set(doc))
    result = []
    for chunk, doc in zip(chunks, docs):
        freq = Counter(doc)
        score = 0.0
        for token in q:
            f = freq[token]
            if f:
                idf = math.log(1 + (len(docs) - df[token] + 0.5) / (df[token] + 0.5))
                score += idf * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * len(doc) / avg))
        if score:
            result.append((chunk['chunk_id'], score))
    return sorted(result, key=lambda x: (-x[1], x[0]))


def section_heading_matches(query, chunks):
    """Find explicit section openings in a uniquely named Code's Act passages.

    This is a ranking hint only: a heading can also occur in a contents page,
    and provisions can continue onto subsequent pages.
    """
    sections = re.findall(r'\bsections?\s+(\d+)\b', query, re.IGNORECASE)
    codes = {c['labour_code'] for c in chunks if c.get('category') == 'Acts'
             and c.get('labour_code') and re.search(
                 r'(?<!\w)' + re.escape(c['labour_code']) + r'(?!\w)', query, re.IGNORECASE)}
    if len(sections) != 1 or len(codes) != 1:
        return set()
    code = next(iter(codes))
    marker = re.compile(r'(?m)^\s*' + re.escape(sections[0]) + r'\.\s*(?:\(\d+\)|[A-Z])')
    return {c['chunk_id'] for c in chunks if c.get('category') == 'Acts'
            and c.get('labour_code') == code and marker.search(c['text'])}


def dense(query_vector, chunks, vectors):
    eligible = [c for c in chunks if c['chunk_id'] in vectors]
    if not eligible:
        return []
    mat = np.asarray([vectors[c['chunk_id']] for c in eligible], dtype='float32')
    q = np.asarray(query_vector, dtype='float32').reshape(1, -1).copy()
    if mat.ndim != 2 or mat.shape[1] != q.shape[1] or not np.isfinite(mat).all() or not np.isfinite(q).all():
        raise ValueError('Invalid vector dimensions or values')
    faiss.normalize_L2(mat)
    faiss.normalize_L2(q)
    index = faiss.IndexFlatIP(mat.shape[1])
    index.add(mat)
    scores, indices = index.search(q, len(eligible))
    return [(eligible[int(i)]['chunk_id'], float(score)) for score, i in zip(scores[0], indices[0]) if i >= 0]


def search(query, chunks, vectors=None, query_vector=None, source_scope='statutory',
           labour_code=None, category=None, top_k=5, mode='hybrid_rerank', date_filter=None,
           section_candidates_enabled=True, proximity_enabled=True):
    if date_filter is not None:
        raise ValueError('Date filtering unavailable until source dates are validated')
    if not 1 <= top_k <= 100:
        raise ValueError('top_k out of range')
    if unsupported_query(query):
        return []
    if source_scope != 'statutory':
        return []
    selected = [c for c in chunks if english_eligible(c) and c['scope'] == source_scope
                and (not labour_code or c['labour_code'] == labour_code)
                and (not category or c['category'] == category)]
    if mode not in ('bm25', 'dense', 'hybrid', 'hybrid_rerank'):
        raise ValueError('Unknown retrieval mode')
    lexical = bm25(query, selected) if mode != 'dense' else []
    if mode != 'bm25' and (vectors is None or query_vector is None):
        raise ValueError('Dense query requires embeddings')
    semantic = dense(query_vector, selected, vectors) if mode != 'bm25' else []
    scores = Counter()
    for ranking in (lexical, semantic):
        for rank, (key, _) in enumerate(ranking[:100], 1):
            scores[key] += 1 / (60 + rank)
    by_id = {c['chunk_id']: c for c in selected}
    if mode == 'hybrid_rerank' and section_candidates_enabled:
        # Section lookup supplies an independent candidate ranking before reranking.
        for rank, key in enumerate(section_candidates(query, selected), 1):
            scores[key] += 1 / (60 + rank)
    # Reward only a literal identifier found in the passage, not merely its title.
    # The passage and page provenance remain unchanged and require review.
    identifiers = instrument_ids(query)
    if identifiers and mode != 'dense':
        for chunk in selected:
            if identifiers & instrument_ids(chunk['text']):
                scores[chunk['chunk_id']] += 0.02
    if mode == 'bm25':
        for key in section_heading_matches(query, selected):
            scores[key] += 0.03
    qterms = set(terms(query))
    if mode == 'hybrid_rerank' and qterms:
        for key in scores:
            chunk = by_id[key]
            coverage = len(qterms & set(terms(chunk['text']))) / len(qterms)
            title_coverage = len(qterms & set(terms(chunk['original_title']))) / len(qterms)
            scores[key] += 0.015 * coverage + 0.005 * title_coverage
    results, seen = [], set()
    for key in sorted(scores, key=lambda x: (-scores[x], x)):
        chunk = by_id[key]
        if chunk['page_id'] in seen:
            continue
        seen.add(chunk['page_id'])
        results.append({**chunk, 'score': scores[key]})
        limit = max(top_k, 30 if proximity_enabled else 10) if mode == 'hybrid_rerank' else top_k
        if len(results) == limit:
            break
    if mode == 'hybrid_rerank':
        # Reorder the existing ten-page pool only. A heading is a ranking hint,
        # not a relevance judgment, and must not displace a retrieved page.
        headings = section_heading_matches(query, selected)
        first = results[:10]
        for result in first:
            if result['chunk_id'] in headings:
                result['score'] += 0.03
        first.sort(key=lambda result: (-result['score'], result['chunk_id']))
        results = first + results[10:]
        if proximity_enabled:
            pool = results[:30]
            proximity = proximity_scores(query, pool, selected, terms)
            for result in pool:
                result['score'] += .02 * proximity[result['page_id']]
            pool.sort(key=lambda result: -result['score'])
            results = pool + results[30:]
    return results[:top_k]


def validate_citation(citation, pages):
    source_id = citation.get('source_pdf_id')
    page_number = citation.get('pdf_page_number')
    if not isinstance(source_id, str) or not isinstance(page_number, int) or isinstance(page_number, bool) or page_number < 1:
        return False
    page_id = f"{source_id}:page_{page_number:04d}"
    page = pages.get(page_id)
    return bool(page and citation.get('source_url') == page['source_url']
                and citation.get('scope') == page['scope']
                and citation.get('original_title') == page['original_title'])
