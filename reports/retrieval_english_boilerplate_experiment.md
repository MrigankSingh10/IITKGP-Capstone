# English query boilerplate development experiment

A fixed list of interrogative and auxiliary words is removed from BM25 query terms, with the original query used when nothing remains. Negations, legal terminology and instrument numbers remain; the identifier boost still uses the original query. This affects the lexical channel, including hybrid modes, but leaves passage text, source offsets, citation validation and the English filter unchanged.

Before testing, selection required no decline in hit@10, page recall@10 or MRR@10 at either chunk size, and an increase of at least 0.05 in one metric. The 20 source-linked `review_required` grounding cases used in the page-fusion experiment are development data, with one target page each; these labels are incomplete and do not represent independent relevance adjudication.

| Chunk size | Ranking | Hit@10 | Page recall@10 | MRR@10 |
| --- | --- | ---: | ---: | ---: |
| 200 | Previous | 0.80 | 0.80 | 0.4098 |
| 200 | Boilerplate removed | 0.80 | 0.80 | 0.5097 |
| 350 | Previous | 0.75 | 0.75 | 0.4863 |
| 350 | Boilerplate removed | 0.80 | 0.80 | 0.5933 |

The seven-question English slice of the frozen assistant-reviewed pilot was then run once as a regression, not independent proof. For 200-token chunks, hit, recall and MRR remained 4/7. For 350-token chunks, hit and MRR remained 4/7 and page recall rose from 0.50 to 4/7. Existing pilot JSON was preserved; new results are in `reports/relevance_english_boilerplate_regression.json`. Development script: `.venv/bin/python scripts/experiment_query_boilerplate.py`. No external calls were made. This small, non-independent test does not establish broad production improvement or fix pages excluded by the English filter.
