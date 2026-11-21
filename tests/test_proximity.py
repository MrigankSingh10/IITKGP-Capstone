from hr_navigator.retrieval.proximity import proximity_scores
from hr_navigator.retrieval.search import terms


def chunk(page, text):
    return {
        "page_id": page,
        "original_title": "Example Act",
        "text": text,
        "char_start": 0,
        "char_end": len(text),
    }


def test_close_query_terms_score_higher_than_distant_terms():
    near = chunk("near", "Employer must pay overtime wages promptly.")
    far = chunk("far", "Employer " + "other " * 20 + "overtime wages.")
    values = proximity_scores(
        "What must an employer pay for overtime wages?", [near, far], [near, far], terms
    )
    assert values["near"] > values["far"]
    assert all(0 <= value <= 1 for value in values.values())


def test_no_content_terms_gives_zero():
    c = chunk("one", "Some example provision.")
    assert proximity_scores("What is the Example Act?", [c], [c], terms) == {"one": 0.0}
