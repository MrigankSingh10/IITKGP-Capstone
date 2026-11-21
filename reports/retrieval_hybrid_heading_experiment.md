# Hybrid section-heading reranking

The hybrid reranker now promotes an explicit section opening in the named Code's Act, using the same conservative matching rule and 0.03 increment previously developed for BM25. It first forms the original unique-page ranking, then reorders only the first ten pages; smaller requested result counts are prefixes of that order. This preserves the top-ten membership. A heading can appear in a contents page, and provisions can continue onto another page; the signal is not a relevance or completeness judgment. Citation metadata and validation are unchanged.

Development used the 20 source-linked review-required cases in `grounding_fresh_v1.jsonl` and their cached query embeddings. Labels identify one page, are incomplete, and lack independent adjudication. Comparison of baseline, heading only, lexical rank only, and both was fixed before the random-gold regression. Heading alone produced the strongest development MRR: for 200 tokens baseline .55/.65/.80 and .4260 MRR versus .60/.70/.80 and .5568; for 350 baseline .70/.75/.85 and .5826 versus .70/.80/.85 and .7046 (Hit@3/5/10). Lexical-only MRR was .4125 and .5801, and combined MRR .5433 and .7021, respectively. Run `.venv/bin/python scripts/experiment_hybrid_rerank.py` to reproduce development comparisons.

One paired regression used the exact 20 random gold cases and existing cached vectors, verifying corpus and gold hashes and the original ten-page pool for every query. The original benchmark remains unchanged. Results (Hit@3/5/10; MRR@10):

| Chunk size | Before | After |
| --- | --- | --- |
| 200 | .50 / .60 / .75; .4914 | .50 / .60 / .75; .5164 |
| 350 | .50 / .55 / .65; .4629 | .50 / .55 / .65; .4963 |

The requested >.70 Hit@3 and Hit@5 targets remain unmet. For 200 tokens, 10 target pages appear in the first three, five more appear at ranks 4–10, and five are absent from the pool. Improving ordering alone cannot recover absent targets, while broadening or changing the candidate pool could affect the existing Hit@10 and needs separate development and evaluation. Gold gives one cited target rather than exhaustive relevance labels and is not individually expert reviewed; these small-sample results do not establish general effectiveness. No network calls or new text transfers were made. The reproducible paired script is `scripts/regress_hybrid_rerank.py` and the separate results are `reports/random_gold_hybrid_heading_regression.json`.
