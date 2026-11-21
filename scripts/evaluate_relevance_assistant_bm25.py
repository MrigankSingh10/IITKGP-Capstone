import hashlib,json,statistics,sys,time
from pathlib import Path
sys.path.insert(0,'src');sys.path.insert(0,'scripts')
from evaluate_relevance_fresh import metrics
from hr_navigator.retrieval.search import search
f=Path('evaluation/relevance_assistant_v1.jsonl'); d=hashlib.sha256(f.read_bytes()).hexdigest(); assert Path(str(f)+'.sha256').read_text().strip()==d
cases=[json.loads(x) for x in f.read_text().splitlines()]; labels=[set(c['relevant_page_ids']) for c in cases]
out={'frozen_sha256':d,'provenance':'Assistant-reviewed focused judgments; not independent human review; incomplete labels may understate performance','latency_scope':'local search only, includes per-query ranking setup; excludes embeddings and end-to-end costs','results':{},'chunk_sha256':{}}
for size in (200,350):
 p=Path(f'data/processed/accepted_ocr/chunks_{size}.jsonl'); chunks=[json.loads(x) for x in p.read_text().splitlines()]; ranks=[];times=[]
 for c in cases:
  t=time.perf_counter();r=search(c['question'],chunks,top_k=10,mode='bm25');times.append(time.perf_counter()-t);ranks.append([x['page_id'] for x in r])
 score=metrics(ranks,labels);score['mean_local_search_seconds']=statistics.mean(times);score['language_slices']={lang:metrics([r for r,c in zip(ranks,cases) if c['query_language']==lang],[g for g,c in zip(labels,cases) if c['query_language']==lang]) for lang in sorted({c['query_language'] for c in cases})};out['results'][f'{size}_bm25']=score;out['chunk_sha256'][str(size)]=hashlib.sha256(p.read_bytes()).hexdigest()
Path('reports/relevance_assistant_bm25_metrics.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
