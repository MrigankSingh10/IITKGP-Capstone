# Explicit Code section heading ranking

A query naming exactly one corpus Code and one numbered section receives a lexical ranking boost for an eligible passage from that Code's Act containing a matching section opening. The query and passage provide the matching signals; gold labels are never used to route queries. This affects BM25 only. It does not alter source metadata, page boundaries, citation validation, applicability decisions, or hybrid modes. A heading may also appear in a table of contents, and section text can continue onto later pages without a repeated heading; the hint is not proof of relevance or completeness.

Development used the 20 source-linked `review_required` cases in `grounding_fresh_v1.jsonl` (one target page per query; labels are incomplete and not independently adjudicated). The 20 random gold cases were not used for candidate design. Results, before and after:

| Chunks | Ranking | Hit@3 | Hit@5 | Hit@10 | MRR@10 |
| --- | --- | ---: | ---: | ---: | ---: |
| 200 | Baseline | .65 | .70 | .80 | .5097 |
| 200 | Heading | .75 | .80 | .80 | .6767 |
| 350 | Baseline | .75 | .80 | .80 | .5933 |
| 350 | Heading | .75 | .80 | .80 | .7042 |

A separate regression uses the exact random sample fixed in `random_gold_bm25_benchmark.json`, with its original corpus checksums and unchanged baseline artifacts. Its one cited target page is not an exhaustive relevance judgment; the underlying frozen gold set lacks individual expert review. It has not met the requested >.70 thresholds; >.70 hit rate requires at least 15 of 20 cases.

| Chunks | Ranking | Hit@3 | Hit@5 | Hit@10 | MRR@10 |
| --- | --- | ---: | ---: | ---: | ---: |
| 200 | Baseline | .55 | .55 | .55 | .4583 |
| 200 | Heading | .55 | .55 | .55 | .4917 |
| 350 | Baseline | .50 | .55 | .55 | .4625 |
| 350 | Heading | .50 | .55 | .55 | .4875 |

For each chunk size, all 20 regression target pages contain at least one eligible chunk. This is only a page-level coverage floor, not evidence that the relevant text itself is in an eligible passage. Multi-page provisions, OCR, overlapping chunks, contents pages, and missing or incomplete relevance judgments remain limitations. The ranking does not stitch pages; cross-page passage coverage is therefore not established. More representative, independently adjudicated multi-page relevance labels and improved general retrieval are needed to support the requested target. No external calls were made.

Run `.venv/bin/python scripts/experiment_section_heading.py` and `.venv/bin/python scripts/regress_section_heading.py`. The latter writes `random_gold_section_heading_regression.json` and preserves the original benchmark.

A corpus-only continuation diagnostic on 350-token Acts chunks found 287 pages with at least one eligible chunk. Of these, 74 have no detected section opening; 29 immediately follow a page with a detected opening, and 20 of those 29 predecessors have more than one distinct detected section number. A predecessor heading alone therefore cannot identify the continuation safely; even the last detected number can be affected by OCR or contents-page formatting. These counts are not labeled continuation cases or a measurement of relevant-text coverage. A page-order-aware section parser would need verified boundaries and evaluation before using continuation signals to change ranking.
