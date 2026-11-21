import json, sqlite3, sys, statistics
sys.path.insert(0,'src')
from hr_navigator.retrieval import search as search_module
from hr_navigator.retrieval.search import search,bm25,section_heading_matches,english_eligible
# Evaluate variants from the original pool, independent of the shipped rerank.
search_module.section_heading_matches = lambda q, c: set()
from hr_navigator.retrieval.embeddings import read_vector
model='bge-small-en-v1.5'
cases=[json.loads(x) for x in open('evaluation/grounding_fresh_v1.jsonl')]
cases=[c for c in cases if c.get('source_pdf_id') and c.get('pdf_page_number') and c.get('expected_decision')=='review_required']
db=sqlite3.connect('file:data/indexes/accepted_ocr.sqlite?mode=ro',uri=True); qdb=sqlite3.connect('file:data/indexes/grounding_fresh_queries.sqlite?mode=ro',uri=True)
for size in [200,350]:
 chunks=[json.loads(x) for x in open(f'data/processed/accepted_ocr/chunks_{size}.jsonl')]; selected=[c for c in chunks if english_eligible(c) and c['scope']=='statutory']; vec={c['chunk_id']:v for c in chunks if (v:=read_vector(db,model,c['text'])) is not None}
 out={n:[] for n in ['base','heading','lexical','heading_lexical']}
 for c in cases:
  q=c['question']; v=read_vector(qdb,model,q)
  if v is None: raise ValueError(c['case_id'])
  pool=search(q,chunks,vec,v,top_k=10,mode='hybrid_rerank'); headings=section_heading_matches(q,selected); lexical=bm25(q,selected); lr={k:i for i,(k,_) in enumerate(lexical,1)}
  target=f"{c['source_pdf_id']}:page_{c['pdf_page_number']:04d}"
  for name in out:
   ordered=sorted(enumerate(pool),key=lambda x: (-(x[1]['score']+(0.03 if 'heading' in name and x[1]['chunk_id'] in headings else 0)+(0.01/(60+lr[x[1]['chunk_id']])*60 if 'lexical' in name and x[1]['chunk_id'] in lr else 0)),x[0]))
   pages=[x[1]['page_id'] for x in ordered]; out[name].append(pages.index(target)+1 if target in pages else None)
 for name,ranks in out.items(): print(size,name,{f'hit{k}':round(statistics.mean(p is not None and p<=k for p in ranks),4) for k in [3,5,10]},'mrr',round(statistics.mean(1/p if p else 0 for p in ranks),4),flush=True)
