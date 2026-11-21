"""Page-local query-term proximity used for experimental retrieval reranking."""

from collections import Counter, defaultdict
import math

# Generic question scaffolding does not identify an answer passage.
_STOP = frozenset(
    "the a an of to by or in and for under does do how who what which when where is are can has have about on as at according this that their with from it be would did was say state states specify specifies section code".split()
)


def proximity_scores(query, candidates, chunks, tokenize, window=16):
    """Return IDF-weighted query coverage in the best page window.

    Only selected eligible passage text is used. Reconstructed gaps are spaces;
    each hit remains attached to its original page and candidate citation.
    """
    grouped = defaultdict(list)
    for chunk in chunks:
        grouped[chunk["page_id"]].append(chunk)
    page_tokens = {}
    for page_id, parts in grouped.items():
        text = ""
        for chunk in sorted(parts, key=lambda c: c.get("char_start", 0)):
            start = chunk.get("char_start", 0)
            end = chunk.get("char_end", start + len(chunk["text"]))
            if start > len(text):
                text += " " * (start - len(text))
            text = text[:start] + chunk["text"] + text[end:]
        page_tokens[page_id] = tokenize(text)
    df = Counter(word for words in page_tokens.values() for word in set(words))
    count = len(page_tokens)
    scores = {}
    for candidate in candidates:
        query_terms = {
            word
            for word in set(tokenize(query)) - set(tokenize(candidate["original_title"])) - _STOP
            if word.isalpha()
        }
        if not query_terms:
            scores[candidate["page_id"]] = 0.0
            continue
        weights = {
            word: math.log(1 + (count - df[word] + 0.5) / (df[word] + 0.5))
            for word in sorted(query_terms)
        }
        total = sum(weights.values())
        hits = [
            (i, word)
            for i, word in enumerate(page_tokens[candidate["page_id"]])
            if word in query_terms
        ]
        best = right = 0
        seen = Counter()
        for i, word in hits:
            while right < len(hits) and hits[right][0] - i < window:
                seen[hits[right][1]] += 1
                right += 1
            best = max(best, sum(weights[w] for w, n in seen.items() if n))
            seen[word] -= 1
        scores[candidate["page_id"]] = min(1.0, best / total)
    return scores
