"""Find each hold-out quote in the local OCR pages and fill the exact page and OCR wording.

The freeze (scripts/freeze_holdout.py) needs each quote to appear character for character in the
OCR text of the cited page. Quotes copied from another copy of a Code often differ only in line
breaks, hyphenation or quote marks. This helper matches while ignoring those differences, then
writes the exact OCR wording and the PDF page number into a copy of the review sheet.

It never sets review_verdict or reviewer: a person still checks every row and decides.

    python scripts/locate_holdout_quotes.py --review my_filled_sheet.csv
"""
import argparse
import csv
import json
from pathlib import Path
import re

QUOTES = str.maketrans({'‘': "'", '’': "'", '“': '"', '”': '"', '–': '-', '—': '-', ' ': ' '})


def normalise(text: str) -> tuple[str, list[int]]:
    """Return a loose form of text plus, for each loose character, its index in the original."""
    out, index, i = [], [], 0
    while i < len(text):
        ch = text[i].translate(QUOTES)
        if ch == '-' and re.match(r'-\s*\n\s*', text[i:]):        # word split across a line break
            i += len(re.match(r'-\s*\n\s*', text[i:]).group(0))
            continue
        if ch.isspace():
            if out and out[-1] != ' ':
                out.append(' ')
                index.append(i)
            i += 1
            continue
        out.append(ch.lower())
        index.append(i)
        i += 1
    return ''.join(out), index


def locate(quote: str, pages: list[dict]) -> list[tuple[dict, str]]:
    """Return (page, exact OCR substring) for every page whose text contains the quote loosely."""
    wanted = normalise(quote)[0].strip()
    hits = []
    for page in pages:
        loose, index = normalise(page['text'])
        start = loose.find(wanted)
        if wanted and start >= 0:
            end = start + len(wanted) - 1
            hits.append((page, page['text'][index[start]:index[end] + 1]))
    return hits


def page_number(page: dict) -> int:
    return int(page.get('pdf_page_number') or page['page_id'].rsplit('_', 1)[1])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--review', type=Path, required=True, help='Filled or pre-filled review sheet (CSV)')
    parser.add_argument('--pages', type=Path, default=Path('data/processed/accepted_ocr/pages.jsonl'))
    parser.add_argument('--output', type=Path, help='Default: <review>_located.csv')
    args = parser.parse_args()
    if not args.pages.is_file():
        raise SystemExit(f'OCR pages not found at {args.pages}; the corpus folder is needed for this step.')
    by_pdf: dict[str, list[dict]] = {}
    for line in args.pages.read_text(encoding='utf-8').splitlines():
        if line.strip():
            page = json.loads(line)
            by_pdf.setdefault(page['page_id'].split(':')[0], []).append(page)
    with args.review.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    found = 0
    for row in rows:
        quote = row['source_quote'].strip()
        if not quote:
            print(f"{row['case_id']}: no quote yet")
            continue
        hits = locate(quote, by_pdf.get(row['source_pdf_id'], []))
        if len(hits) == 1:
            page, exact = hits[0]
            number = page_number(page)
            if row['pdf_page_number'].strip() and int(row['pdf_page_number']) != number:
                note = f'Located on PDF page {number}, not {row["pdf_page_number"]} as entered; please check.'
            else:
                note = f'Located automatically on PDF page {number}; quote set to the exact OCR wording.'
            row['pdf_page_number'], row['source_quote'] = str(number), exact
            row['review_notes'] = f"{note} {row['review_notes']}".strip()
            found += 1
            print(f"{row['case_id']}: page {number}")
        elif hits:
            numbers = sorted(page_number(p) for p, _ in hits)
            print(f"{row['case_id']}: quote appears on several pages {numbers}; use a longer quote")
        else:
            print(f"{row['case_id']}: NOT FOUND in the OCR text; shorten the quote or copy it from the OCR page")
    output = args.output or args.review.with_name(args.review.stem + '_located.csv')
    with output.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f'\nLocated {found} of {len(rows)} quotes. Wrote {output}. '
          'Now check each row, then set review_verdict and reviewer yourself.')


if __name__ == '__main__':
    main()
