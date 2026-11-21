"""Additional hand-designed fictional checks; not an independent benchmark."""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hr_navigator.clients.api import APIConfig, APIError, HostedClient  # noqa: E402
from hr_navigator.retrieval.draft_review import check_question_source_alignment  # noqa: E402

parser=argparse.ArgumentParser()
parser.add_argument('--key-file',required=True,type=Path)
parser.add_argument('--ca-file',required=True,type=Path)
parser.add_argument('--base-url',required=True)
parser.add_argument('--model',required=True)
args=parser.parse_args()
cases=[
 ('new_irrelevant','What is the fictional inspection fee?','The facility opens on Monday.',
  'Fictional inspection handbook','The facility opens on Monday.',False),
 ('new_direct','What is the fictional inspection fee?','The fee is 12 tokens.',
  'Fictional inspection handbook','The inspection fee is 12 tokens.',True),
 ('new_wrong_document','According to the 2024 fictional harbor bulletin, what is the renewal period?','Thirty days.',
  'Fictional harbor bulletin 2026','The renewal period is thirty days.',False),
 ('new_right_document','According to the 2024 fictional harbor bulletin, what is the renewal period?','Thirty days.',
  'Fictional harbor bulletin 2024','The renewal period is thirty days.',True),
 ('new_missing_component','What are the fictional length and weight?','The length is 5 units.',
  'Fictional cargo guide','The length is 5 units and the weight is 7 units.',False),
 ('new_compact_complete','What are the fictional length and weight?','Five units and seven units respectively.',
  'Fictional cargo guide','The length is 5 units and the weight is 7 units.',True),
]
c=HostedClient(APIConfig(args.base_url,args.model,args.key_file.read_text().strip(),str(args.ca_file),60))
results=[]
try:
 for cid,q,a,t,quote,expected in cases:
  start=time.monotonic()
  try:
   o=check_question_source_alignment(c,q,a,[{'title':t,'page_number':1,'quote':quote}])
   accept=o['answers_question'] and o['requested_source_match']
   err=None
  except (APIError,ValueError,TypeError,KeyError,IndexError):
   o=None
   accept=False
   err='model or schema error'
  results.append({'id':cid,'expected_accept':expected,'observed_accept':accept,
                  'observed':o,'error':err,'latency_seconds':round(time.monotonic()-start,3)})
  print(cid,'expected',expected,'actual',accept,flush=True)
finally:
 usage=c.usage
 c.close()
Path('reports/alignment_additional_dev.json').write_text(json.dumps({'scope':'hand-designed additional development examples; not a benchmark',
 'usage':usage,'results':results},indent=2)+'\n')
