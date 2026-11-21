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
# Preregistered candidate: combine passage BM25 ranks and page BM25 ranks with weight 0.5;
# retain the highest-scoring passage for each page; select only on development hit@10,
# MRR@10 and recall@10, requiring no metric drop and at least one improvement.
def candidate(q,chunks):
    passage=original(q,chunks)
    by_id={c['chunk_id']:c for c in chunks}
    groups={}
    for c in chunks:
        if c['page_id'] not in groups: groups[c['page_id']]={**c,'chunk_id':c['page_id'],'text':''}
        groups[c['page_id']]['text']+=' '+c['text']
    pages=original(q,list(groups.values()))
    scores=collections.Counter({key:1/(60+i) for i,(key,_) in enumerate(passage,1)})
    representative={}
    for key,_ in passage: representative.setdefault(by_id[key]['page_id'],key)
    for i,(page,_) in enumerate(pages[:100],1):
        if page in representative: scores[representative[page]]+=0.5/(60+i)
    return sorted(scores.items(),key=lambda x:(-x[1],x[0]))
for size in (200,350):
 chunks=[json.loads(x) for x in open(f'data/processed/accepted_ocr/chunks_{size}.jsonl')]
 labels=[{f"{c['source_pdf_id']}:page_{c['pdf_page_number']:04d}"} for c in cases]
 for name,fn in [('baseline',original),('candidate',candidate)]:
  s.bm25=fn
  ranks=[[x['page_id'] for x in s.search(c['question'],chunks,top_k=10,mode='bm25')] for c in cases]
  print(size,name,metrics(ranks,labels),flush=True)
