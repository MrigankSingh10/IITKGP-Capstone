from hr_navigator.retrieval.section_lookup import section_pages, section_candidates


def page(number, text, source="s"):
    return {
        "chunk_id": f"{source}-{number}",
        "page_id": f"{source}:page_{number:04d}",
        "source_pdf_id": source,
        "pdf_page_number": number,
        "char_start": 0,
        "text": text,
        "category": "Acts",
        "labour_code": "Code on Wages",
    }


def test_continuation_requires_ordered_consecutive_headings_and_pages():
    chunks = [
        page(
            1,
            "4. Where a dispute arises, the appropriate authority shall decide the matter.\n"
            "5. No employer shall pay any employee less than the minimum wage prescribed.",
        ),
        page(2, "The preceding provision continues on this original PDF page."),
        page(3, "6. The appropriate Government shall fix the applicable minimum wage rate."),
    ]
    expected = {"s:page_0001", "s:page_0002", "s:page_0003"}
    assert section_pages(chunks)[("s", 5)] == expected
    assert set(section_candidates("Code on Wages section 5", chunks)) == {"s-1", "s-2", "s-3"}
    assert section_pages([chunks[0], chunks[2]]) == {}
    assert section_candidates("section 5", chunks) == []


def test_contents_duplicate_and_out_of_order_are_not_accepted():
    def opening(n):
        return f"{n}. The appropriate Government shall determine the applicable wage rate.\n"

    assert not section_pages([page(1, "CONTENTS\n" + "".join(opening(n) for n in (4, 5, 6)))])
    assert not section_pages([page(1, "".join(opening(n) for n in (4, 5, 5, 6)))])
    assert not section_pages([page(1, "".join(opening(n) for n in (5, 4, 6)))])


def test_first_section_requires_enacting_formula_and_early_next_heading():
    first = page(
        1,
        "BE it enacted by Parliament as follows:\n"
        "1. (1) This Act may be called the Code on Wages, 2019.\n",
    )
    second = page(
        2,
        "This subsection continues the first section on the next page.\n"
        "2. In this Code, unless the context otherwise requires, these terms apply.",
    )
    assert section_pages([first, second])[("s", 1)] == {"s:page_0001", "s:page_0002"}
    assert not section_pages(
        [page(1, first["text"].replace("BE it enacted by Parliament", "Contents")), second]
    )
    assert not section_pages([first, page(4, second["text"])])


def test_osh_alias_does_not_select_multiple_named_codes():
    from hr_navigator.retrieval.section_lookup import section_candidates

    def opening(n):
        return f"{n}. The appropriate Government shall determine the applicable wage rate.\n"

    c = page(1, "".join(opening(n) for n in (4, 5, 6)))
    c["labour_code"] = "Occupational Safety Health and Working Conditions Code"
    assert section_candidates("OSH Code section 5", [c]) == [c["chunk_id"]]
    other = dict(
        c,
        chunk_id="wages",
        page_id="wages:page_0001",
        source_pdf_id="wages",
        labour_code="Code on Wages",
    )
    assert section_candidates("OSH Code and Code on Wages section 5", [c, other]) == []
