# Preliminary retrieval comparison — 2026-11-18

A fixed subset of 19 single-turn questions was selected deterministically as every fourth case from the frozen gold set after excluding six multi-turn cases. Each has one annotated source PDF/page from the gold set. For each system we check whether that one page appears among the first k distinct retrieved pages; this is a cited-page hit rate, a single-relevant-page form of recall, not exhaustively annotated retrieval recall. Other relevant pages may exist. The case-level source annotations have not received independent legal/relevance review, the subset is small, and gold cases concentrate on a few PDFs. Do not treat the numbers as final performance or tune against these held-out cases. MRR is truncated at 10. The local search time excludes query embedding, loading data and network latency; evaluation used warm local files. Dense indexing covers Latin-script heuristic pages only, while BM25 searches extracted chunks across scripts.

| Chunk tokens / method | Hit@3 | Hit@5 | Hit@10 | MRR@10 | Mean local search s |
|---|---:|---:|---:|---:|---:|
| 200 / BM25 | 0.421 | 0.421 | 0.474 | 0.272 | 0.408 |
| 200 / dense | 0.263 | 0.526 | 0.632 | 0.232 | 0.005 |
| 200 / hybrid | 0.421 | 0.526 | 0.789 | 0.381 | 0.404 |
| 200 / hybrid + lexical rerank | 0.526 | 0.526 | 0.789 | 0.417 | 0.411 |
| 350 / BM25 | 0.316 | 0.368 | 0.579 | 0.239 | 0.356 |
| 350 / dense | 0.368 | 0.526 | 0.579 | 0.285 | 0.003 |
| 350 / hybrid | 0.526 | 0.526 | 0.789 | 0.450 | 0.358 |
| 350 / hybrid + lexical rerank | 0.579 | 0.632 | 0.842 | 0.530 | 0.366 |

The reranker is an explicitly measured deterministic token-coverage and title-coverage score added to reciprocal-rank fusion; it is not another generative model. Full results and case IDs are in `retrieval_v1_metrics.json`; `scripts/evaluate_retrieval.py` reproduces the calculation after index and API setup. Comparison alone does not validate answer quality, current law, multilingual coverage or causal improvement. An independently reviewed and more diverse query-to-page relevance set is required for final recall claims.
