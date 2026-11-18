"""Run local OCR on sparse PDF pages; output unreviewed overlay, never replace originals."""
import csv
import json
from pathlib import Path
import tempfile

import fitz
from rapidocr_onnxruntime import RapidOCR

pages = [json.loads(line) for line in Path('data/processed/pages.jsonl').read_text().splitlines()]
sparse = [p for p in pages if p['extraction_status'] == 'sparse']
engine = RapidOCR()
results = []
for page in sparse:
    with fitz.open(Path('data/raw') / (page['source_pdf_id'] + '.pdf')) as pdf:
        original = pdf[page['pdf_page_number'] - 1]
        images = len(original.get_images(full=True))
        with tempfile.TemporaryDirectory(prefix='hr-ocr-') as tmp:
            image = Path(tmp) / 'page.png'
            original.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).save(str(image))
            try:
                rows, _ = engine(str(image))
                rows = rows or []
                text = '\n'.join(row[1] for row in rows)
                confidence = sum(float(row[2]) for row in rows) / len(rows) if rows else None
                error = None
            except Exception as exc:
                text, confidence, error = '', None, type(exc).__name__
    results.append({'page_id': page['page_id'], 'source_pdf_id': page['source_pdf_id'],
                    'pdf_page_number': page['pdf_page_number'], 'title': page['original_title'],
                    'native_characters': page['character_count'], 'embedded_image_count': images,
                    'ocr_text': text, 'ocr_characters': len(text.strip()),
                    'mean_line_confidence': confidence, 'ocr_error': error,
                    'ocr_method': 'RapidOCR 1.4.4 bundled model, unreviewed',
                    'review_status': 'pending', 'indexed': False})
    print(f"{len(results)}/{len(sparse)} OCR pages processed", flush=True)
with Path('data/processed/sparse_ocr_candidates.jsonl').open('w', encoding='utf-8') as f:
    for item in results:
        f.write(json.dumps(item, ensure_ascii=False) + '\n')
with Path('reports/sparse_ocr_review.csv').open('w', newline='', encoding='utf-8') as f:
    fields = ['page_id', 'title', 'pdf_page_number', 'native_characters', 'embedded_image_count',
              'ocr_characters', 'mean_line_confidence', 'ocr_error', 'review_status', 'indexed']
    writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(results)
