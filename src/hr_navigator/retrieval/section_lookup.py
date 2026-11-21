"""Conservative, query-independent section-to-original-PDF-page candidates.

Ordinary sections require bracketed consecutive openings in a single source;
section 1 requires an enacting formula and an early section 2 opening.
This is an extraction heuristic, not proof of legal completeness or relevance.
"""

from collections import defaultdict
import re

_OPENING = re.compile(r"(?m)^\s*(\d{1,3})\.\s*(?:\(1\)\s*)?([A-Z][^\n]{39,})$")
_CONTENTS = re.compile(r"\b(?:table of contents|contents|arrangement of sections)\b", re.I)
_SECTION = re.compile(r"\bsections?\s+(\d+)\b", re.I)


def section_pages(chunks):
    """Return {(source id, section): original page IDs} for verified intervals.

    Requires unique ordered n-1, n, n+1 openings (or a section 1 opening
    after the enacting formula and an early section 2 opening), a complete
    extracted page sequence, and no contents marker on heading pages. Unknown
    intervals are omitted. The n+1 page can also contain the end of n.
    """
    sources = defaultdict(lambda: defaultdict(list))
    for c in chunks:
        if c.get("category") == "Acts" and c.get("source_pdf_id") and c.get("pdf_page_number"):
            sources[c["source_pdf_id"]][c["pdf_page_number"]].append(c)
    result = {}
    for source, pages in sources.items():
        headings = defaultdict(list)
        enacted = {}
        for page, parts in pages.items():
            # Restore overlaps by original page offsets; never concatenate chunks
            # into artificial heading lines.
            segments = sorted(parts, key=lambda c: c.get("char_start", 0))
            text = ""
            for c in segments:
                start = c.get("char_start")
                if not isinstance(start, int) or start > len(text):
                    break
                text += c["text"][max(0, len(text) - start) :]
            else:
                enacting = re.search(r"\bBE\s+it\s+enacted\s+by\s+Parliament\b", text, re.I)
                if enacting:
                    enacted[page] = enacting.start()
                if not _CONTENTS.search(text):
                    for m in _OPENING.finditer(text):
                        if not re.search(r"\.{2,}|\s\d+\s*$", m.group(2)):
                            headings[int(m.group(1))].append((page, m.start()))
        for n, positions in headings.items():
            if n == 1:
                first = [pos for pos in positions if pos[0] == 1]
                if len(first) != 1 or 1 not in enacted or enacted[1] >= first[0][1]:
                    continue
                current = first[0]
                # The first subsequent opening is the section boundary; later
                # numbered repeal lists or schedules are not section openings.
                early = [pos for pos in headings.get(2, []) if current < pos and pos[0] <= 3]
                if len(early) != 1:
                    continue
                following = early[0]
            else:
                if any(len(headings.get(x, [])) != 1 for x in (n - 1, n, n + 1)):
                    continue
                previous, current, following = (headings[x][0] for x in (n - 1, n, n + 1))
                if not previous < current < following:
                    continue
            start, end = current[0], following[0]
            if any(p not in pages for p in range(start, end + 1)):
                continue
            result[(source, n)] = {pages[p][0]["page_id"] for p in range(start, end + 1)}
    return result


def section_candidates(query, chunks):
    numbers = _SECTION.findall(query)
    codes = {
        c["labour_code"]
        for c in chunks
        if c.get("category") == "Acts"
        and c.get("labour_code")
        and re.search(r"(?<!\w)" + re.escape(c["labour_code"]) + r"(?!\w)", query, re.I)
    }
    if re.search(r"(?<!\w)OSH(?:\s+Code)?(?!\w)", query, re.I):
        codes.update(
            c["labour_code"]
            for c in chunks
            if c.get("category") == "Acts"
            and c.get("labour_code") == "Occupational Safety Health and Working Conditions Code"
        )
    if len(numbers) != 1 or len(codes) != 1:
        return []
    code, number = next(iter(codes)), int(numbers[0])
    selected = [c for c in chunks if c.get("labour_code") == code and c.get("category") == "Acts"]
    mapping = section_pages(selected)
    candidates = {page for (source, n), pages in mapping.items() if n == number for page in pages}
    # Stable page order; citation metadata and passage text come from actual chunks.
    return [
        c["chunk_id"]
        for c in sorted(
            selected,
            key=lambda x: (x["source_pdf_id"], x["pdf_page_number"], x.get("char_start", 0)),
        )
        if c["page_id"] in candidates
    ]
