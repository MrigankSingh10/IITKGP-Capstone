"""Reproducible extraction and page-contained BGE-token chunks."""
import hashlib
import json
from pathlib import Path

import fitz
from tokenizers import Tokenizer

from hr_navigator.ingestion.audit import language


def load_registry(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()]


def extract_pages(registry_path, raw_dir):
    for source in load_registry(registry_path):
        path = Path(raw_dir) / (source['sha256'] + '.pdf')
        if hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256']:
            raise ValueError('Source PDF hash mismatch')
        matches = source.get('manifest_matches', [])
        downloaded = [m for m in matches if m.get('download_status') == 'Downloaded']
        if len(downloaded) != 1:
            raise ValueError('Expected exactly one downloaded manifest record per PDF')
        manifest = downloaded[0]
        with fitz.open(path) as doc:
            if doc.needs_pass or len(doc) != source['page_count']:
                raise ValueError('PDF inaccessible or page count changed')
            for index in range(len(doc)):
                try:
                    text = doc[index].get_text()
                    status = 'sparse' if len(text.strip()) < 100 else 'extracted'
                except Exception:
                    text, status = '', 'extraction_error'
                yield {'page_id': f"{source['sha256']}:page_{index + 1:04d}",
                       'source_pdf_id': source['sha256'], 'original_filename': source['original_filename'],
                       'original_title': manifest.get('document_name', ''),
                       'source_url': manifest.get('original_source_url', ''),
                       'category': manifest.get('category', ''),
                       'labour_code': manifest.get('labour_code', ''),
                       'scope': 'statutory', 'pdf_page_number': index + 1,
                       'printed_page': None, 'manifest_publication_date_unverified': manifest.get('publication_date', ''),
                       'manifest_language_unverified': manifest.get('language', ''),
                       'language_heuristic': language(text), 'extraction_status': status,
                       'character_count': len(text.strip()), 'text': text}


def make_chunks(page, tokenizer, size, overlap):
    if not 0 <= overlap < size <= 510:
        raise ValueError('Require 0 <= overlap < size <= 510')
    text = page['text']
    encoded = tokenizer.encode(text, add_special_tokens=False)
    offsets = encoded.offsets
    start = 0
    while start < len(offsets):
        end = min(start + size, len(offsets))
        first, last = offsets[start][0], offsets[end - 1][1]
        chunk_text = text[first:last]
        actual = len(tokenizer.encode(chunk_text, add_special_tokens=True).ids)
        if actual > 512:
            raise ValueError('Chunk exceeds embedding token limit')
        if chunk_text.strip():
            chunk_id = hashlib.sha256(f"{page['page_id']}:{size}:{overlap}:{first}:{last}".encode()).hexdigest()
            yield {'chunk_id': chunk_id, 'page_id': page['page_id'],
                   'source_pdf_id': page['source_pdf_id'], 'pdf_page_number': page['pdf_page_number'],
                   'scope': page['scope'], 'labour_code': page['labour_code'],
                   'category': page['category'], 'original_title': page['original_title'],
                   'source_url': page['source_url'], 'language_heuristic': page['language_heuristic'],
                   'extraction_status': page['extraction_status'], 'token_count': actual,
                   'char_start': first, 'char_end': last, 'text': chunk_text}
        if end == len(offsets):
            break
        start = end - overlap


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')


def build(registry, raw, output, tokenizer_path):
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    pages = list(extract_pages(registry, raw))
    write_jsonl(Path(output) / 'pages.jsonl', pages)
    counts = {}
    for size, overlap in [(200, 40), (350, 60)]:
        chunks = [chunk for page in pages for chunk in make_chunks(page, tokenizer, size, overlap)]
        write_jsonl(Path(output) / f'chunks_{size}.jsonl', chunks)
        counts[str(size)] = len(chunks)
    return {'source_pdf_count': len({p['source_pdf_id'] for p in pages}),
            'page_document_count': len(pages), 'chunk_counts': counts}
