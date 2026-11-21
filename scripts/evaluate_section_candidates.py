"""Paired diagnostic of the fixed random sample, using local cached vectors only."""
import hashlib, json, sqlite3, sys
from pathlib import Path
sys.path.insert(0, 'src')
from hr_navigator.retrieval.embeddings import read_vector
import hr_navigator.retrieval.search as retrieval

def read(p): return [json.loads(line) for line in Path(p).read_text().splitlines()]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
prior=json.loads(Path('reports/random_gold_hybrid_heading_regression.json').read_text())
path='data/processed/accepted_ocr/chunks_200.jsonl'
assert sha(path)==prior['results']['200']['chunk_sha256']
assert sha('evaluation/gold_v1.jsonl')==prior['gold_sha256']
chunks=read(path); gold={x['id']:x for x in read('evaluation/gold_v1.jsonl')}
original=retrieval.section_candidates
model=json.loads(Path('reports/random_gold_modes_benchmark.json').read_text())['model']
db=sqlite3.connect('file:data/indexes/accepted_ocr.sqlite?mode=ro',uri=True)
qdb=sqlite3.connect('file:data/indexes/random_gold_queries.sqlite?mode=ro',uri=True)
vectors={c['chunk_id']:v for c in chunks if (v:=read_vector(db,model,c['text'])) is not None}
rows=[]
for old in prior['results']['200']['cases']:
 c=gold[old['id']]; q=read_vector(qdb,model,c['question']); assert q is not None
 ranks={}
 for name,func in [('before',lambda *a: []),('after',original)]:
  retrieval.section_candidates=func
  pages=[x['page_id'] for x in retrieval.search(c['question'],chunks,vectors,q,top_k=30,mode='hybrid_rerank',section_candidates_enabled=True)]
  ranks[name]=pages.index(old['target_page'])+1 if old['target_page'] in pages else None
 assert (ranks['before'] if ranks['before'] and ranks['before']<=10 else None)==old['after_rank'], (old['id'],ranks,old['after_rank'])
 rows.append({'id':old['id'],'target_page':old['target_page'],'question':c['question'],**ranks})
 print(rows[-1],flush=True)
def stats(key):
 return {f'hit_at_{k}':sum(r[key] is not None and r[key]<=k for r in rows)/len(rows) for k in (3,5,10,30)} | {'mrr_at_10':sum(1/r[key] if r[key] and r[key]<=10 else 0 for r in rows)/len(rows)}
result={'prior_sha256':sha('reports/random_gold_hybrid_heading_regression.json'),'gold_sha256':prior['gold_sha256'],'chunk_sha256':sha(path),'sample_ids':prior['sample_ids'],'scope':'One cited target page per case; incomplete labels, no independent relevance adjudication; 30 means final page order after reranking first ten, hence identical membership to pre-rerank 30.', 'before':stats('before'),'after':stats('after'),'cases':rows}
Path('reports/random_gold_section_candidates_diagnostic.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['before'], result['after'])
