"""Member 1 source context, kept separate from applicability determinations."""
import csv
from pathlib import Path
import re

from hr_navigator.retrieval.search import bm25, english_eligible, unsupported_query

ROOT = Path(__file__).resolve().parents[3]


def _rows(name):
    with (ROOT / 'reports' / name).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def load_source_context():
    return ({r['source_pdf_id']: r for r in _rows('member_1_source_triage.csv')},
            _rows('member_1_source_relationships.csv'),
            {r['page_id']: r for r in _rows('member_1_sparse_page_triage.csv')})


def enrich_pages(pages, context):
    tags, relationships, sparse = context
    fields = ('document_type', 'labour_code_manifest', 'authority_tier', 'jurisdiction_tag',
              'document_date', 'document_date_kind', 'review_status', 'observed_language')
    for page_id, page in pages.items():
        tag = tags.get(page['source_pdf_id'], {})
        page['source_tags'] = {k: tag[k] for k in fields if tag.get(k)}
        page['source_relationships'] = [r for r in relationships
                                        if page['source_pdf_id'] in
                                        (r['source_pdf_id'], r['related_source_pdf_id'])]
        disposition = sparse.get(page_id)
        if disposition:
            page['sparse_page_disposition'] = disposition['disposition']
            warning = ('Sparse-page disposition: ' + disposition['disposition'] + '. '
                       + disposition['note'])
            page['source_warnings'] = list(dict.fromkeys(page.get('source_warnings', []) + [warning]))
    return pages


def citation_context(page):
    return {key: page[key] for key in ('source_tags', 'source_relationships',
                                        'sparse_page_disposition') if key in page}


def pair_related(query, results, chunks, context, labour_code=None):
    """Append linked passages only for explicit provision or instrument references.

    Relationships are leads for review, not evidence that a change applies. Existing
    scope/code filters remain in force and missing linked text is never fabricated.
    """
    if unsupported_query(query):
        return []
    results = [c for c in results if english_eligible(c)]
    _, relationships, _ = context
    present = {c['source_pdf_id'] for c in results}
    seen = {c['page_id'] for c in results}
    q = query.casefold()
    for relation in relationships:
        kind = relation['relationship']
        if kind == 'amends':
            targeted = bool(re.search(r'\b(?:section|sec\.?|s\.?)\s*104\b', q))
        elif kind == 'source_conflict':
            targeted = bool(re.search(r'\b(?:155|156)\b', q))
        elif kind in ('corrects', 'corrects_hindi_text'):
            instrument = re.sub(r'[^a-z0-9]', '', relation['related_instrument'].split(',')[0].casefold())
            targeted = bool(instrument and instrument in re.sub(r'[^a-z0-9]', '', q))
        else:
            targeted = False
        a, b = relation['source_pdf_id'], relation['related_source_pdf_id']
        if not targeted or not ({a, b} & present):
            continue
        other = b if a in present else a
        if other in present and (kind != 'amends' or any(
                c['source_pdf_id'] == other and re.search(r'\b104\s*[.(]', c['text'])
                for c in results)):
            continue
        candidates = [c for c in chunks if c['source_pdf_id'] == other
                      and c['scope'] == 'statutory' and english_eligible(c)
                      and (not labour_code or c['labour_code'] == labour_code)]
        if kind == 'amends':
            candidates = [c for c in candidates if re.search(r'\b104\s*[.(]', c['text'])]
        elif kind == 'source_conflict':
            candidates = [c for c in candidates if re.search(r'\b15[56]\b', c['text'])]
        ranking = bm25(query, candidates)
        if ranking:
            by_id = {c['chunk_id']: c for c in candidates}
            chunk = by_id[ranking[0][0]]
            if chunk['page_id'] not in seen:
                results.append({**chunk, 'score': ranking[0][1],
                                'relationship_pairing': kind})
                seen.add(chunk['page_id'])
                present.add(other)
    return results
