"""Paired frozen regression using existing local vectors and immutable prior results."""
import hashlib, json, sqlite3, statistics, sys
from pathlib import Path
sys.path.insert(0, 'src')
from hr_navigator.retrieval.embeddings import read_vector
from hr_navigator.retrieval.search import search

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return [json.loads(x) for x in Path(p).read_text().splitlines()]
prior_path='reports/random_gold_modes_benchmark.json'
prior=json.loads(Path(prior_path).read_text()); gold_path='evaluation/gold_v1.jsonl'
assert sha(gold_path)==Path('evaluation/gold_v1.sha256').read_text().split()[0]==prior['gold_sha256']
ids=prior['sample_ids']; assert len(ids)==len(set(ids))==20 and prior['seed']==20261121
cases={c['id']:c for c in read(gold_path)}
db=sqlite3.connect('file:data/indexes/accepted_ocr.sqlite?mode=ro',uri=True)
qdb=sqlite3.connect('file:data/indexes/random_gold_queries.sqlite?mode=ro',uri=True)
model=prior['model']; output={'prior_sha256':sha(prior_path),'gold_sha256':sha(gold_path),'sample_ids':ids,'results':{}}
for size in ('200','350'):
 path=f'data/processed/accepted_ocr/chunks_{size}.jsonl'; assert sha(path)==prior['results'][size]['chunk_sha256']
 chunks=read(path); vec={c['chunk_id']:v for c in chunks if (v:=read_vector(db,model,c['text'])) is not None}; rows=[]
 assert [r['id'] for r in prior['results'][size]['cases']]==ids
 for cid,old in zip(ids,prior['results'][size]['cases']):
  case=cases[cid]; target=f"{case['source']['source_pdf_id']}:page_{case['source']['pdf_page_number']:04d}"; assert target==old['target_page']
  query=read_vector(qdb,model,case['question']); assert query is not None
  pages=[r['page_id'] for r in search(case['question'],chunks,vec,query,top_k=10,mode='hybrid_rerank')]
  assert set(pages)==set(old['hybrid_rerank']['pages']), (size,cid)
  rows.append({'id':cid,'target_page':target,'before_rank':old['hybrid_rerank']['rank'],'after_rank':pages.index(target)+1 if target in pages else None,'pages':pages})
 def summary(key):
  ranks=[r[key] for r in rows]
  return {**{f'hit_at_{k}':statistics.mean(x is not None and x<=k for x in ranks) for k in (3,5,10)},'mrr_at_10':statistics.mean(1/x if x else 0 for x in ranks)}
 output['results'][size]={'chunk_sha256':sha(path),'before':summary('before_rank'),'after':summary('after_rank'),'cases':rows}
 print(size,output['results'][size]['before'],output['results'][size]['after'],flush=True)
Path('reports/random_gold_hybrid_heading_regression.json').write_text(json.dumps(output,indent=2)+'\n')
