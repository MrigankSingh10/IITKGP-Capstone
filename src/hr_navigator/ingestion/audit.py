"""Bounded ZIP import and per-page PDF audit; no OCR or retrieval chunking."""
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

import fitz

MAX_ARCHIVE_BYTES = 2_000_000_000
MAX_FILE_BYTES = 200_000_000
MAX_ENTRIES = 10000


def safe_members(archive: zipfile.ZipFile):
    infos = archive.infolist()
    if len(infos) > MAX_ENTRIES or sum(i.file_size for i in infos) > MAX_ARCHIVE_BYTES:
        raise ValueError('Archive exceeds size or entry limit')
    seen = set()
    for info in infos:
        name = info.filename
        path = PurePosixPath(name)
        if (not name or '\\' in name or path.is_absolute() or '..' in path.parts
                or re.match(r'^[A-Za-z]:', name) or stat.S_ISLNK(info.external_attr >> 16)):
            raise ValueError('Unsafe archive member')
        if info.file_size > MAX_FILE_BYTES:
            raise ValueError('Archive member exceeds size limit')
        normalized = str(path).casefold()
        if normalized in seen:
            raise ValueError('Duplicate archive path')
        seen.add(normalized)
    return infos


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def language(text: str) -> str:
    latin = sum('a' <= c.lower() <= 'z' for c in text)
    devanagari = sum('\u0900' <= c <= '\u097f' for c in text)
    if latin < 20 and devanagari < 20:
        return 'unknown/sparse'
    if devanagari >= 20 and latin >= 20:
        return 'mixed English/Devanagari (heuristic)'
    return 'Devanagari (heuristic)' if devanagari >= 20 else 'Latin (heuristic)'


def audit(zip_path: Path, raw_dir: Path, report_dir: Path):
    report_dir.mkdir(parents=True, exist_ok=True)
    registry_path = report_dir / 'source_registry.jsonl'
    with zipfile.ZipFile(zip_path) as z:
        infos = safe_members(z)
        manifests = [i for i in infos if PurePosixPath(i.filename).name.lower() == 'manifest.csv']
        if len(manifests) != 1:
            raise ValueError('Expected exactly one manifest.csv')
        manifest = list(csv.DictReader(io.StringIO(z.read(manifests[0]).decode('utf-8-sig'))))
        pdfs = [i for i in infos if not i.is_dir() and i.filename.lower().endswith('.pdf')]
        if not pdfs:
            raise ValueError('No PDFs in archive')
        records, pages, hashes = [], [], {}
        matched = set()
        for info in pdfs:
            data = z.read(info)
            sha = digest(data)
            filename = PurePosixPath(info.filename).name
            # Preserve the entire matching manifest row, without guessing column semantics.
            matches = [(n, row) for n, row in enumerate(manifest)
                       if any(str(v or '').strip().replace('\\', '/').casefold() in
                              (info.filename.casefold(), filename.casefold()) for v in row.values())]
            matched.update(n for n, _ in matches)
            rec = {'source_pdf_id': sha, 'sha256': sha, 'archive_path': info.filename,
                   'original_filename': filename, 'category_from_path': str(PurePosixPath(info.filename).parent),
                   'manifest_matches': [row for _, row in matches],
                   'duplicate_of': hashes.get(sha), 'page_count': None, 'error': None}
            hashes.setdefault(sha, info.filename)
            try:
                with fitz.open(stream=data, filetype='pdf') as doc:
                    if doc.needs_pass:
                        raise ValueError('encrypted PDF')
                    rec['page_count'] = len(doc)
                    for idx in range(len(doc)):
                        try:
                            text = doc[idx].get_text()
                            count = len(text.strip())
                            error = ''
                            lang = language(text)
                        except Exception as exc:
                            count, lang, error = None, 'unknown', type(exc).__name__
                        pages.append({'source_pdf_id': sha, 'archive_path': info.filename,
                                      'pdf_page_number': idx + 1, 'extractable_characters': count,
                                      'sparse_under_100': count is not None and count < 100,
                                      'language_heuristic': lang, 'extraction_error': error})
            except Exception as exc:
                rec['error'] = type(exc).__name__
            records.append((rec, data))
        registry = ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r, _ in records)
        if registry_path.exists() and registry_path.read_text(encoding='utf-8') != registry:
            raise ValueError('Existing immutable registry differs; use a new report directory')
        raw_dir.mkdir(parents=True, exist_ok=True)
        for rec, data in records:
            dest = raw_dir / (rec['sha256'] + '.pdf')
            if dest.exists() and digest(dest.read_bytes()) != rec['sha256']:
                raise ValueError('Existing raw file hash mismatch')
            if not dest.exists():
                dest.write_bytes(data)
        if not registry_path.exists():
            registry_path.write_text(registry, encoding='utf-8')
        with (report_dir / 'corpus_inventory.csv').open('w', newline='', encoding='utf-8') as f:
            fields = ['source_pdf_id', 'archive_path', 'pdf_page_number', 'extractable_characters',
                      'sparse_under_100', 'language_heuristic', 'extraction_error']
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(pages)
        sparse = sum(p['sparse_under_100'] for p in pages)
        failures = sum(bool(p['extraction_error']) for p in pages)
        report = (f'# Corpus audit\n\nSource PDFs: {len(records)}\n\nPage documents: {len(pages)}\n\n'
                  f'Retrieval chunks: not generated (Phase 2)\n\nSparse pages (<100 characters): {sparse}\n\n'
                  f'PDF errors: {sum(bool(r["error"]) for r, _ in records)}; page errors: {failures}\n\n'
                  f'Duplicate content: {sum(bool(r["duplicate_of"]) for r, _ in records)}\n\n'
                  f'Manifest rows: {len(manifest)}; unmatched rows: {len(manifest) - len(matched)}; '
                  f'PDFs without an exact filename/path manifest match: '
                  f'{sum(not r["manifest_matches"] for r, _ in records)}. '
                  'Manifest matches require manual review, including URLs and download status.\n\n'
                  'Page counts may be incomplete when PDF errors occur. Language is a script heuristic, '
                  'not a language classifier; sparse pages are OCR candidates, not proof of scanning.\n')
        (report_dir / 'corpus_audit.md').write_text(report, encoding='utf-8')
        return report
