"""Development-set diagnostic using locally cached query and passage vectors."""
import json, sqlite3, sys
from pathlib import Path
sys.path.insert(0, 'src')
import hr_navigator.retrieval.search as retrieval
from hr_navigator.retrieval.embeddings import read_vector
cases=[json.loads(x) for x in Path('evaluation/grounding_fresh_v1.jsonl').read_text().splitlines()]
cases=[c for c in cases if c.get('source_pdf_id') and c.get('pdf_page_number') and c.get('expected_decision')=='review_required']
chunks=[json.loads(x) for x in Path('data/processed/accepted_ocr/chunks_200.jsonl').read_text().splitlines()]
db=sqlite3.connect('file:data/indexes/accepted_ocr.sqlite?mode=ro',uri=True)
qdb=sqlite3.connect('file:data/indexes/grounding_fresh_queries.sqlite?mode=ro',uri=True)
model='bge-small-en-v1.5'; vectors={c['chunk_id']:v for c in chunks if (v:=read_vector(db,model,c['text'])) is not None}
original=retrieval.section_candidates; rows=[]
for c in cases:
 target=f"{c['source_pdf_id']}:page_{c['pdf_page_number']:04d}"; q=read_vector(qdb,model,c['question']); assert q is not None
 row={'id':c['case_id']}
 for name,func in [('before',lambda *a: []),('after',original)]:
  retrieval.section_candidates=func
  pages=[x['page_id'] for x in retrieval.search(c['question'],chunks,vectors,q,top_k=30,mode='hybrid_rerank',section_candidates_enabled=True)]
  row[name]=pages.index(target)+1 if target in pages else None
 rows.append(row); print(row,flush=True)
def stats(k):
 return {f'hit_at_{n}':sum(r[k] is not None and r[k]<=n for r in rows)/len(rows) for n in (3,5,10,30)}
out={'scope':'Development only: source-linked review_required cases, single cited page; labels incomplete and not independently adjudicated.','before':stats('before'),'after':stats('after'),'cases':rows}
Path('reports/section_candidates_dev_diagnostic.json').write_text(json.dumps(out,indent=2)+'\n');print(out['before'],out['after'])
