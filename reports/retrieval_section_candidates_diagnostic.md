# Section candidate experiment and retrieval failure audit

This is an **opt-in experiment**, not the default retrieval path. It uses existing local embeddings and makes no network calls. No frozen evaluation files were modified. One cited target page per case is an incomplete relevance label, not an independent human review. Scores below are target-page hit rates, not verified answer accuracy. They do not establish a >70% hit@5 result.

The section lookup reconstructs page text from available chunks and requires unique, ordered section n−1, n, and n+1 openings in the same Act source, with every original PDF page present between n and n+1. It rejects pages explicitly marked as contents, duplicate or out-of-order openings, gaps, and unrecognized references. It returns the entire span through the page containing n+1, since n can end on that page. These checks establish extraction structure, not legally verified section boundaries; OCR can mimic headings or hide a contents page, and page candidates may include text outside the target section. In particular the first and last sections and ambiguous gaps are omitted. Candidate passages retain their original source/page metadata and require source review. The conservative English script filter is not language identification.

The independent candidate ranking is combined with keyword and dense rankings before the current rerank when `section_candidates_enabled=True`. Development on the 20 source-linked `review_required` grounding cases yielded hit@3 60%→70%, hit@5 70%→75%, hit@10 80%→85%, top-30 coverage 95%→95%; these cases have incomplete, unadjudicated labels. Their existing cached query vectors were used. Paired regression on the pre-existing random 20 and 200-token chunks gave unchanged hit@3 50%, hit@5 60%, hit@10 75%, top-30 80%, MRR@10 0.5164. This clears 70% at hit@10 only, not at hit@5, and the small, selected, single-target sample cannot support a general performance claim. One top-10 miss appears at rank 11 and four remain absent from the wider 30-page candidate pool. Thus reranking a wider existing pool could potentially help one sampled target; four would need better candidate recall or evidence/label examination first. Candidate top-30 membership is measured after reranking the first ten; its membership equals pre-rerank top-30 membership.

See `section_candidates_dev_diagnostic.json` and `random_gold_section_candidates_diagnostic.json` for per-case ranks, provenance hashes and scope. Rerun with `scripts/evaluate_section_candidates_dev.py` and `scripts/evaluate_section_candidates.py`; the latter asserts the frozen reference hashes and reproduces prior top-10 ranks. The sample was inspected for diagnosis, not used to adjust the heuristic. Section 1 is intentionally not special-cased after seeing the regression.

## Audit: five target misses at ten

| Case | Target rank | Observation and plausible failure type |
|---|---:|---|
| draft-036 | >30 | Social Security section 1(6) is on a continuation page; no section 1 bracket exists under this conservative rule. Section-to-page candidate recall limitation. |
| draft-010 | 11 | Wages Act opening description is available in the wider pool but sits just outside ten; ranking/pool cutoff. |
| draft-070 | >30 | Occupational safety FAQ page contains state rule-making answer; FAQ retrieval/candidate recall, outside Act section lookup. |
| draft-039 | >30 | Social Security definition is in a long definitions section, with question naming no section number; candidate recall/query routing. |
| draft-063 | >30 | Industrial relations FAQ page includes the tribunal answer; FAQ retrieval/candidate recall, outside Act section lookup. |

## Audit: five later top-ten hits

| Case | Rank | Observation and plausible failure type |
|---|---:|---|
| draft-044 | 4 | Social Security chapter applicability on a continuation page; ranking behind earlier pages. |
| draft-021 | 8 | Industrial Relations definition on a dense definitions page; ranking among competing legal terminology. |
| draft-062 | 9 | Industrial relations FAQ conciliation answer appears on a multi-question page; FAQ page ranking. |
| draft-026 | 7 | Wages Advisory Board definition on a dense definitions page; ranking among competing legal terminology. |
| draft-057 | 5 | Wages FAQ overtime answer occurs on a multi-question page; FAQ page ranking. |

These are descriptive hypotheses from the questions, target pages and ranks, not adjudicated root causes. Other pages may also be relevant.

## Independent evaluation plan

Before enabling in production, assemble a fresh English-only query set disjoint from development, the fixed random 20, and existing frozen relevance/grounding sets; sample across Act sections (including continuation and first/last boundaries), FAQ questions, definitions and ambiguous names. Select cases without looking at system rankings, record selection seed and corpus/version hashes, and independently review original PDFs for all relevant original pages, including continuation and plausible competing pages. Freeze queries, full relevance judgments, exclusions and hashes before running; separately assess parser false positives and missed boundaries against reviewed page-level spans. Use cached vectors where already available; do not transmit new questions or create external embeddings without the user's authorization. Report paired hit@3/5/10, pre-rerank top-30 recall, MRR, per-category outcomes, confidence intervals and changed cases. Keep unknown and unreviewed labels separate from negatives. Treat the >70% gate as unmet for hit@5 until the agreed metric is met on the independent reviewed set.
