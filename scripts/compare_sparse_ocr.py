"""Produce a second local OCR reading for the scanned Social Security pages."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

import fitz

pages = [json.loads(line) for line in Path('data/processed/sparse_ocr_candidates.jsonl').read_text().splitlines()]
pages = [p for p in pages if p['source_pdf_id'].startswith('d7d9516a') and p['pdf_page_number'] <= 11]
results = []
for page in pages:
    with fitz.open(Path('data/raw') / (page['source_pdf_id'] + '.pdf')) as doc:
        with tempfile.TemporaryDirectory(prefix='ocr-second-') as tmp:
            image = Path(tmp) / 'page.png'
            doc[page['pdf_page_number'] - 1].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).save(str(image))
            env = {**os.environ, 'OMP_THREAD_LIMIT': '2'}
            run = subprocess.run(['tesseract', str(image), 'stdout', '-l', 'eng', '--psm', '3'],
                                 capture_output=True, text=True, env=env, timeout=120, check=False)
    results.append({'page_id': page['page_id'], 'pdf_page_number': page['pdf_page_number'],
                    'method': 'Tesseract English 5.5.4 psm 3, unreviewed',
                    'text': run.stdout, 'returncode': run.returncode})
    print(f"{len(results)}/{len(pages)} second OCR readings complete", flush=True)
with Path('data/processed/sparse_ocr_tesseract.jsonl').open('w', encoding='utf-8') as f:
    for item in results:
        f.write(json.dumps(item, ensure_ascii=False) + '\n')
