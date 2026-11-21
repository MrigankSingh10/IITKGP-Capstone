# Phase 1 progress — baselines run, human scoring pending

The user approved the 80 document-only cases; `evaluation/gold_v1.jsonl` was frozen on 2026-11-18 with the adjacent SHA256. Approval applies to the set as a whole; existing case-level `unreviewed` values do not establish individual legal review. It covers 10 PDFs and 21 PDF/page pairs, including six explicit prior-user-turn cases. More diverse sources and independent relevance review would improve future evaluation versions.

All 240 live closed-book baseline calls succeeded on the permitted Qwen/Qwen3-8B chat endpoint. Three prompting strategies each used the same 80 questions and settings. Detailed results, usage, latency, examples and limitations are in `baseline_v1_report.md`; the document-only set has no explicit refusal cases. Cost is unknown; no agent graph has been implemented.

Before claiming the Phase 1 evaluation gate, reconcile the differing reviews described below and document observed failures without editing the frozen file. Faculty page-as-document acceptance was reported by the user; its written scope, legal applicability and redistribution rights remain to be documented. Phase 2 retrieval is underway; Phase 3 LangGraph has not started.

## User-approved deferral — 2026-11-18

The user requested that Phase 2 start while human scoring of the saved baseline responses remains outstanding. This defers the Phase 1 evaluation gate; it does not establish baseline accuracy or a measured improvement. Preserve the frozen questions and saved responses. Reviewers should score the baseline independently before viewing Phase 2 answers, and complete scoring before claiming improvements or starting agent development.

## User-provided scoring and adjudication — 2026-11-20

All 240 row-level baseline scores were supplied and imported; the row table totals 32 passes, whereas the supplied narrative stated 24. This is provisional user-provided evaluation, not an independently verified accuracy figure. `reports/baseline_adjudication.csv` contains 16 items needing review for scoring completeness or clause references; original supplied scores remain unchanged. The scenario set in `evaluation/scenarios_v0.1.jsonl` is not frozen. Complete review before claiming improvement or beginning agent development.

## User-provided adjudication update — 2026-11-20

All 16 flagged baseline items received user-provided strict-rubric decisions; 13 scores changed from 1 to 0, and three existing 0 scores were retained. Current sheet totals are 6/80 zero-shot, 5/80 few-shot and 8/80 decomposition (19/240 overall). These are user-provided, not independently verified human accuracy scores. Historical scores remain in row notes. See `baseline_user_review_import.md` and `baseline_adjudication.csv`.

## Team review retained

The team also supplied a separately reviewed baseline sheet, preserved as `baseline_v1_review_team.csv`, and a report describing 33/240 passes. Its scores differ from the later strict adjudication above. Both are retained for rubric and reviewer reconciliation; the summaries are not interchangeable or independently verified by this merge. The 40-case behaviour scenario set remains a draft and must be reconciled with the user's document-focused scope before use.
