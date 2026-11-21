"""Create an unfrozen review draft; does not run any hosted model."""
import csv
from difflib import SequenceMatcher
import json
from pathlib import Path
import re

pages = list(map(json.loads, Path('data/processed/accepted_ocr/pages.jsonl').read_text().splitlines()))
gold = list(map(json.loads, Path('evaluation/gold_v1.jsonl').read_text().splitlines()))
# Source-specific questions ask what the document says, not whether it applies today.
# prefix, page, section, question, expected conditions, start marker, end marker
cases = [
('0d17b967a528',9,'16','What wage periods does section 16 of the Code on Wages list, and what is their maximum length?','Daily, weekly, fortnightly or monthly; no wage period may exceed one month.','The employer shall fix the wage period','shall be more than a month'),
('0d17b967a528',9,'17(1)(i)','According to section 17(1)(i) of the Code on Wages, when are daily-basis wages paid?','At the end of the shift.','daily basis, at the end of the shift','daily basis, at the end of the shift'),
('0d17b967a528',9,'17(1)(iv)','Under section 17(1)(iv) of the Code on Wages, what is the stated time limit for monthly wages?','Before expiry of the seventh day of the succeeding month.','monthly basis, before the expiry of the seventh day','month.'),
('0d17b967a528',7,'8(4)','How often does section 8(4) of the Code on Wages say minimum rates should ordinarily be reviewed or revised?','Ordinarily at an interval not exceeding five years.','The appropriate Government shall review or revise minimum rates of wages ordinarily','at an interval not exceeding five years.'),
('0d17b967a528',7,'8(1)(b)','When proposals to fix or revise minimum wages are published under section 8(1)(b) of the Code on Wages, what is the minimum period before they are considered?','The specified date must be not less than two months from notification.','by notification publish its proposals','the proposals shall be taken into consideration.'),
('43cadbd9ed08',8,'4(1)','At what worker count does section 4(1) of the Industrial Relations Code require grievance redressal committees?','Every industrial establishment employing twenty or more workers must have one or more.','Every industrial establishment employing twenty or more workers','individual grievances.'),
('43cadbd9ed08',8,'4(2), 4(4) and proviso','Under section 4 of the Industrial Relations Code, what is the maximum size of a grievance redressal committee and what representation requirements apply?','No more than ten members; equal employer and worker representation, and adequate women-worker representation not less than their proportion in the establishment.','(2) The Grievance Redressal Committee shall consist','exceed ten:'),
('43cadbd9ed08',8,'4(3)','How often does the chairperson of a grievance redressal committee rotate under section 4(3) of the Industrial Relations Code?','The chairperson alternates annually between employer and worker representatives.','The chairperson of the Grievance Redressal Committee shall be selected','every year.'),
('43cadbd9ed08',9,'4(6)','What period does section 4(6) of the Industrial Relations Code give a grievance redressal committee to complete proceedings?','It may complete proceedings within thirty days of receiving the application.','The Grievance Redressal Committee may complete its proceedings within thirty','days of receipt of the application under sub-section (5).'),
('43cadbd9ed08',13,'14(3)','Under section 14(3) of the Industrial Relations Code, what support level is specified for recognition as sole negotiating union when multiple registered unions function?','Fifty-one per cent or more of workers on the establishment muster roll, verified as prescribed.','the Trade Union having fifty-one per cent. or more','as the sole negotiating union of the workers.'),
('975235e57b8b',8,'2(35)','How does section 2(35) of the Code on Social Security describe a gig worker?','A person who performs work or participates in a work arrangement and earns from it outside a traditional employer-employee relationship.','"gig worker" means a person','relationship;'),
('975235e57b8b',41,'52(2)-(3)','Under section 52 of the Code on Social Security, when can an Employees’ Insurance Court order be appealed to the High Court, and within what period?','An appeal lies if there is a substantial question of law and must be filed within sixty days of the order.','An appeal shall lie to the High Court','date of the order made by the Employees\' Insurance Court.'),
('975235e57b8b',41,'53(1) proviso','What does the proviso to section 53(1) of the Code on Social Security say about the five-year gratuity service condition for death, disablement, or expiry of fixed-term employment?','Five years of continuous service is not necessary where termination is due to death, disablement, expiration of fixed-term employment, or another event notified by the Central Government.','Provided further that the completion of continuous service of five years','may be notified by the Central Government:'),
('975235e57b8b',42,'53(2) proviso','What gratuity rate does the Code on Social Security state for a seasonal establishment employee not employed throughout the year?','Seven days’ wages for each season.','employee who is employed in a seasonal','seven days\' wages for each season:'),
('975235e57b8b',45,'56(8) proviso','When sufficient cause prevented a timely gratuity appeal under section 56(8) of the Code on Social Security, what additional period may be allowed?','The appropriate Government or appellate authority may extend the sixty-day appeal period by a further sixty days if satisfied of sufficient cause.','if it is satisfied that the appellant was prevented by sufficient cause','extend the said period by a further period of sixty days:'),
('9ce8f68b88f7',17,'6(1)(c)','What does the OSH Code say about the cost of the prescribed annual health examination or test?','It is provided free of cost to such categories as prescribed by the appropriate Government.','provide such annual health examination or test free of costs','as may be prescribed by the appropriate Government;'),
('9ce8f68b88f7',21,'16(1)','Which government constitutes the National Occupational Safety and Health Advisory Board under section 16 of the OSH Code?','The Central Government constitutes it by notification.','The Central Government shall, by notification, constitute the National','National Board'),
('9ce8f68b88f7',25,'22(1)','According to section 22(1) of the OSH Code, how must worker and employer representation compare on a Safety Committee?','Worker representatives must not be fewer than employer representatives.','the number of representatives of workers on the Committee','shall not be less than the number of representatives of the employer'),
('9ce8f68b88f7',26,'24(1)(v)','What worker threshold does section 24(1)(v) of the OSH Code mention for a canteen facility?','An establishment where one hundred or more workers, including contract labourers, are ordinarily employed.','facilities of canteen in an establishment','ordinarily employed;'),
('d7d9516acb49',5,'Annexure B row 7','In the Social Security key-provisions letter, which section number appears in Annexure B row 7?','Section 3 appears in row 7. This is a reviewed OCR transcription; check the original scan.','7. | 3 | The time and manner of registration','7. | 3 | The time and manner of registration'),
]

def locate(text, phrase, start=0):
    pieces=phrase.split()
    match=re.search(r'\s+'.join(re.escape(p) for p in pieces),text[start:],re.I)
    if not match:
        raise ValueError(f'Marker missing: {phrase!r}')
    return start+match.start(),start+match.end()

records=[]
for i,(prefix,pno,section,q,expected,begin,end) in enumerate(cases,1):
    page=next(p for p in pages if p['source_pdf_id'].startswith(prefix) and p['pdf_page_number']==pno)
    a,_=locate(page['text'],begin)
    _,b=locate(page['text'],end,a)
    quote=page['text'][a:b]
    if not quote.strip():
        raise ValueError('Empty evidence')
    similarity=max(SequenceMatcher(None,q.casefold(),g['question'].casefold()).ratio() for g in gold)
    records.append({'case_id':f'fresh-draft-{i:03}','question':q,'expected_conditions':expected,
                    'source_pdf_id':page['source_pdf_id'],'original_title':page['original_title'],
                    'pdf_page_number':pno,'section':section,'source_url':page['source_url'],
                    'source_quote':quote,'extraction_status':page['extraction_status'],
                    'source_warnings':page.get('source_warnings',[]),'expected_decision':'review_required',
                    'review_status':'unreviewed','closest_gold_similarity':round(similarity,3)})
case = next(r for r in records if r['case_id'] == 'fresh-draft-007')
extra_page = next(p for p in pages if p['source_pdf_id'] == case['source_pdf_id'] and p['pdf_page_number'] == 9)
a, _ = locate(extra_page['text'], 'Provided that there shall be adequate representation of women workers')
_, b = locate(extra_page['text'], 'industrial establishment.', a)
case['additional_sources'] = [{'source_pdf_id': extra_page['source_pdf_id'],
                               'original_title': extra_page['original_title'],
                               'pdf_page_number': 9, 'source_url': extra_page['source_url'],
                               'source_quote': extra_page['text'][a:b],
                               'extraction_status': extra_page['extraction_status']}]
if len({r['question'] for r in records}) != len(records):
    raise ValueError('Duplicate question')
if any(r['question'].casefold()==g['question'].casefold() for r in records for g in gold):
    raise ValueError('Exact overlap with frozen gold')
out=Path('evaluation/grounding_fresh_draft_v0.1.jsonl')
review_file=Path('evaluation/grounding_fresh_review.csv')
if out.exists() or review_file.exists():
    raise FileExistsError('Review draft already exists; do not overwrite team edits')
out.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in records),encoding='utf-8')
fields=['case_id','question','expected_conditions','original_title','pdf_page_number','section','source_url','source_quote','additional_sources_json','extraction_status','source_warnings','review_verdict','reviewer','review_notes']
with review_file.open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
    w.writeheader()
    for r in records:
        row=dict(r)
        row['source_warnings']=json.dumps(row['source_warnings'],ensure_ascii=False)
        row['additional_sources_json']=json.dumps(row.get('additional_sources',[]),ensure_ascii=False)
        w.writerow(row)
print('Created',len(records),'unreviewed cases, distinct source pages:',len({(x['source_pdf_id'],x['pdf_page_number']) for x in records}))
