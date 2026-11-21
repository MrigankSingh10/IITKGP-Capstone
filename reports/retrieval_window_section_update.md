# Retrieval section and proximity update

This update supersedes the opt-in-only status described in the earlier `retrieval_section_candidates_diagnostic.md`. Hybrid reranking now defaults to using section candidates and a page-local term proximity signal. BM25, dense-only and ordinary hybrid modes are unchanged. The changes use existing local vectors and preserve the original page and passage citation metadata.

Section candidates require a single recognized Code and section number. The section parser brackets most sections using ordered n−1, n and n+1 openings in the same Act with a continuous sequence of extracted pages. Section 1 requires an enacting formula preceding its opening on original PDF page 1 and an unambiguous early section 2 opening; this prevents later numbered repeal lists or schedules from invalidating the first boundary. The `OSH Code` alias is recognized. The section 2 page is included because the end of section 1 may occur on it. These are conservative extraction checks, not human-verified legal boundaries: OCR, unusual layouts, contents pages or numbered lists may defeat them, and candidates may contain text outside the target section. Unknown boundaries and terminal sections remain unsupported. Actual page text and source should be checked before relying on a citation.

For the proximity signal, the retriever reconstructs eligible text at original page offsets, subtracts question scaffolding and source-title words from query terms, and measures IDF-weighted term coverage in the best 16-token page window. It adds 0.02 times that coverage to the score of each page in the existing 30-page pool, then orders that pool. This is a ranking feature, not a relevance or entailment judgment. Section candidates can add pages to the pool; proximity alone cannot recover a page absent from it. Ranking remains English-script-filtered, which is not full language identification.

Selection was performed using 20 separate source-linked development cases (`grounding_fresh_v1`), using only existing cached vectors and without using the random sample labels as features. One cited target per case is an incomplete relevance label and is not independent human review. On 200-token chunks, combined section and proximity improved hit@3/5/10 from .60/.70/.80 to .80/.85/.85 and MRR@10 from .5568 to .6958. On 350 tokens, it improved hit@3/5/10 from .70/.80/.85 to .80/.85/.90 and MRR@10 from .7046 to .7675. Window-only had equal hit rates but lower MRR at both sizes. See `retrieval_window_dev.json` and `scripts/evaluate_retrieval_window_dev.py`.

The configuration was selected before running the paired random-sample regression. The earlier sample had already been examined for failure analysis, so it is a regression set, not a fresh blind evaluation. The new paired results are:

| Chunks | Ranking | Hit@3 | Hit@5 | Hit@10 | Top-30 target coverage | MRR@10 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 200 | Before | .50 | .60 | .75 | .80 | .5164 |
| 200 | After | .55 | .65 | .80 | .85 | .5692 |
| 350 | Before | .50 | .55 | .65 | .85 | .4963 |
| 350 | After | .55 | .60 | .70 | .90 | .5234 |

The strict greater-than-.70 target remains unmet at hit@3 and hit@5 and MRR@10 at both sizes; hit@10 exceeds .70 only at 200 tokens. These 20-case results cannot establish general answer accuracy, since they use one cited target page rather than exhaustive adjudicated relevance labels. The first-section lookup recovers one previously absent target at rank 6. Results are in `random_gold_window_candidate_regression.json` and `random_gold_window_candidate_regression_350.json`; their scripts assert the prior corpus and gold hashes and the previous top-ten ranks. Prior artifacts and frozen datasets are unchanged.

A small local timing check on three development queries, with existing cached vectors and passage data loaded in memory, measured mean retrieval time .572s→.707s for 200 tokens and .493s→.628s for 350 tokens. These are illustrative single-run local timings, excluding embedding, and are not a production latency benchmark. Full pytest: 92 passed, 2 skipped. Ruff checks on the changed retrieval modules, tests and new experiment scripts pass.
