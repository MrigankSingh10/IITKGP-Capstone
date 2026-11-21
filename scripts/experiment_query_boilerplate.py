import sys,json,collections
sys.path[:0]=['src','scripts']
from hr_navigator.retrieval import search as s
from evaluate_relevance_fresh import metrics
cases=[json.loads(x) for x in open('evaluation/grounding_fresh_v1.jsonl')]
cases=[c for c in cases if c.get('source_pdf_id') and c.get('pdf_page_number') and c.get('expected_decision')=='review_required']
print('cases',len(cases))
production_bm25=s.bm25
def original(q, chunks):
    saved = s._QUERY_BOILERPLATE
    try:
        s._QUERY_BOILERPLATE = frozenset()
        return production_bm25(q, chunks)
    finally:
        s._QUERY_BOILERPLATE = saved
# Predeclared candidate: remove only interrogative boilerplate tokens; protect
# statutory content and negation. Require both sizes to have no metric regression
# and one metric to improve by at least 0.05.
def candidate(q,chunks):
    stop={'what','when','where','which','who','how','does','do','did','is','are','was','were'}
    return original(' '.join(t for t in s.terms(q) if t not in stop),chunks)
for size in (200,350):
 chunks=[json.loads(x) for x in open(f'data/processed/accepted_ocr/chunks_{size}.jsonl')]
 labels=[{f"{c['source_pdf_id']}:page_{c['pdf_page_number']:04d}"} for c in cases]
 for name,fn in [('baseline',original),('candidate',candidate)]:
  s.bm25=fn
  ranks=[[x['page_id'] for x in s.search(c['question'],chunks,top_k=10,mode='bm25')] for c in cases]
  print(size,name,metrics(ranks,labels),flush=True)
