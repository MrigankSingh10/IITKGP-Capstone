"""Run a frozen random-gold regression without overwriting its original benchmark."""
import hashlib, json, statistics, sys
from pathlib import Path
sys.path.insert(0, 'src')
from hr_navigator.retrieval.search import search, english_eligible
old=json.loads(Path('reports/random_gold_bm25_benchmark.json').read_text())
path=Path('evaluation/gold_v1.jsonl')
assert hashlib.sha256(path.read_bytes()).hexdigest()==old['gold_sha256']
gold={c['id']:c for c in map(json.loads,path.read_text().splitlines())}
cases=[gold[i] for i in old['sample_ids']]
out={'gold_sha256':old['gold_sha256'], 'sample_ids':old['sample_ids'], 'scope':'Fixed sample; one cited target page, incomplete labels, not independent human relevance review.', 'results':{}}
for size in (200,350):
 p=Path(f'data/processed/accepted_ocr/chunks_{size}.jsonl');assert hashlib.sha256(p.read_bytes()).hexdigest()==old['results'][str(size)]['chunk_sha256']
 chunks=list(map(json.loads,p.read_text().splitlines())); eligible={c['page_id'] for c in chunks if english_eligible(c) and c['scope']=='statutory'}; ranks=[]; covered=0
 for c in cases:
  target=f"{c['source']['source_pdf_id']}:page_{c['source']['pdf_page_number']:04d}"; covered+=target in eligible
  pages=[x['page_id'] for x in search(c['question'],chunks,top_k=10,mode='bm25')];ranks.append(pages.index(target)+1 if target in pages else None)
 scores={f'hit_at_{k}':sum(r is not None and r<=k for r in ranks)/len(ranks) for k in (3,5,10)};scores['mrr_at_10']=sum(1/r for r in ranks if r)/len(ranks)
 out['results'][str(size)]={'baseline':old['results'][str(size)]['shipped'],'section_heading':scores,'target_pages_with_eligible_chunk':covered,'ranks':ranks};print(size,out['results'][str(size)],flush=True)
Path('reports/random_gold_section_heading_regression.json').write_text(json.dumps(out,indent=2)+'\n')
