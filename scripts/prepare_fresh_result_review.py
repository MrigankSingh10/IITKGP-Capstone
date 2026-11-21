"""Create an unscored human-review sheet from a completed frozen grounding run."""
import csv
import hashlib
import json
from pathlib import Path

frozen=Path('evaluation/grounding_fresh_v1.jsonl')
checksum=Path('evaluation/grounding_fresh_v1.sha256')
runs=Path('reports/grounding_fresh_v1_runs.jsonl')
output=Path('reports/grounding_fresh_v1_review.csv')
if output.exists():
    raise SystemExit('Review sheet exists; preserve any reviewer edits')
if not all(p.is_file() for p in (frozen,checksum,runs)):
    raise SystemExit('Frozen set or completed run is missing')
set_sha=hashlib.sha256(frozen.read_bytes()).hexdigest()
if set_sha!=checksum.read_text().split()[0]:
    raise SystemExit('Frozen set checksum mismatch')
cases={c['case_id']:c for c in map(json.loads,frozen.read_text().splitlines())}
rows=[json.loads(line) for line in runs.read_text().splitlines()]
if len(rows)!=len(cases) or {r['case_id'] for r in rows}!=set(cases) or any(r['set_sha256']!=set_sha for r in rows):
    raise SystemExit('Run is incomplete, duplicated or for a different set')
fields=['case_id','question','expected_conditions','expected_title','expected_pdf_page','expected_source_url',
        'expected_source_quote','additional_expected_sources','expected_page_rank','expected_page_ranks','workflow_decision','draft_not_verified',
        'cited_sources','review_verdict','reviewer','review_notes']
with output.open('x',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields)
    w.writeheader()
    for row in rows:
        case=cases[row['case_id']]
        result=row['result']
        w.writerow({'case_id':row['case_id'],'question':case['question'],
                    'expected_conditions':case['expected_conditions'], 'expected_title':case['original_title'],
                    'expected_pdf_page':case['pdf_page_number'],'expected_source_url':case['source_url'],
                    'expected_source_quote':case['source_quote'],
                    'additional_expected_sources':json.dumps(case.get('additional_sources',[]),ensure_ascii=False),
                    'expected_page_rank':row['expected_page_rank'],
                    'expected_page_ranks':json.dumps(row['expected_page_ranks']),
                    'workflow_decision':result['decision'],'draft_not_verified':result.get('draft_not_verified',''),
                    'cited_sources':json.dumps(result.get('sources',[]),ensure_ascii=False)})
print('Created',len(rows),'unscored review rows.')
