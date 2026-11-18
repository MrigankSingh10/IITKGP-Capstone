"""Filtered lexical/dense retrieval, reciprocal-rank fusion and local reranking."""
from collections import Counter
import math
import re

import faiss
import numpy as np


def terms(text):
    return re.findall(r'[^\W_]+', text.casefold(), re.UNICODE)


def bm25(query, chunks):
    q = set(terms(query))
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
           labour_code=None, category=None, top_k=5, mode='hybrid_rerank', date_filter=None):
    if date_filter is not None:
        raise ValueError('Date filtering unavailable until source dates are validated')
    if not 1 <= top_k <= 100:
        raise ValueError('top_k out of range')
    if source_scope != 'statutory':
        return []
    selected = [c for c in chunks if c['scope'] == source_scope
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
        if len(results) == top_k:
            break
    return results


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
