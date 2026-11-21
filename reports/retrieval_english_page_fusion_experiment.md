# English page BM25 development experiment

This is a development experiment, not an independent evaluation. The existing seven-question English relevance pilot was not used to select this candidate and was not rerun. Prior metric JSON files are unchanged.

Before scoring, the candidate and selection rule were fixed in `scripts/experiment_page_bm25.py`: combine passage BM25 reciprocal ranks with page BM25 reciprocal ranks at weight 0.5, assigning each page's contribution to its highest-ranked passage. Page text is formed by concatenating eligible chunks; overlapping chunks can repeat text. Retrieval still returns distinct pages. Require no drop in hit@10, page recall@10, or MRR@10 at either chunk size and an improvement in at least one metric. The development set comprises the 20 `review_required` cases with a source and page in `evaluation/grounding_fresh_v1.jsonl`; each has one source-linked target page, so hit and recall are equal. These labels are not exhaustive relevance judgments and the set is not independent human validation.

| Chunk size | Ranking | Hit@10 | Page recall@10 | MRR@10 |
| --- | --- | ---: | ---: | ---: |
| 200 | Current | 0.80 | 0.80 | 0.4098 |
| 200 | Page fusion | 0.75 | 0.75 | 0.3830 |
| 350 | Current | 0.75 | 0.75 | 0.4863 |
| 350 | Page fusion | 0.75 | 0.75 | 0.5085 |

The candidate fails the selection rule and was not incorporated. All 20 development targets have at least one eligible 200-token chunk, so this set does not establish gains from relaxing the English filter. Mixed-script OCR can interleave English with non-English text represented in both Devanagari and legacy Roman glyphs; removing Devanagari alone would not establish English-only content or preserve reliable passage boundaries. Any future extraction strategy needs independently checked passage boundaries, source offsets, and a separate evaluation of its impact on citation validity.

Run locally with `.venv/bin/python scripts/experiment_page_bm25.py` from the project root. It reads local files only.
