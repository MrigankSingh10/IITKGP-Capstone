# Phase 1 progress — baselines run, baselines scored

The user approved the 80 document-only cases; `evaluation/gold_v1.jsonl` was frozen on 2026-11-18 with the adjacent SHA256. Approval applies to the set as a whole; existing case-level `unreviewed` values do not establish individual legal review. It covers 10 PDFs and 21 PDF/page pairs, including six explicit prior-user-turn cases. More diverse sources and independent relevance review would improve future evaluation versions.

All 240 live closed-book baseline calls succeeded on the permitted Qwen/Qwen3-8B chat endpoint. Three prompting strategies each used the same 80 questions and settings. Detailed results, usage, latency, examples and limitations are in `baseline_v1_report.md`; machine-readable runs and a human-review worksheet are alongside it. Correctness and refusal accuracy remain unscored. The document-only set has no explicit refusal cases. Cost is unknown; VM04 assignment still needs confirmation. No agent graph has been implemented.

Remaining before claiming the Phase 1 evaluation gate: human case-level answer and citation review, grading the baseline against frozen conditions, and documenting observed failures without editing the frozen file. Faculty page-as-document clarification, legal applicability and redistribution rights remain pending. The team should confirm how document-only tests demonstrate Track B tool and completion requirements. Phase 2 retrieval and Phase 3 LangGraph have not started.

## User-approved deferral — 2026-11-18

The user requested that Phase 2 start while human scoring of the saved baseline responses remains outstanding. This defers the Phase 1 evaluation gate; it does not establish baseline accuracy or a measured improvement. Preserve the frozen questions and saved responses. Reviewers should score the baseline independently before viewing Phase 2 answers, and complete scoring before claiming improvements or starting agent development.

## Scoring completed and behaviour set drafted — 2026-11-19

All 240 baseline responses are scored in `baseline_v1_review.csv` (AI-suggested marks reviewed by Hrishikesh; see the review-process note in `baseline_v1_report.md`). Closed-book accuracy: zero-shot 11.3%, few-shot 12.5%, decomposition 17.5% (33/240 overall). Failure patterns, tokens per query and the cost method are documented in `baseline_v1_report.md`; money cost stays unknown until a price is entered in `configs/pricing.json`.

Because `gold_v1` covers only statutory questions, a separate 40-case behaviour set was drafted: `evaluation/scenarios_v0.1.jsonl` with fixtures, validator, tests and a freeze script (see `docs/scenario_set_guide.md`). It covers refusals, prompt injection, Acme policy, employee tools, approval-gated actions and clarification.

**Phase 1 gate status:** baseline numbers are now recorded for the statutory set. Before agent (Phase 3) code starts, the team should (1) sign off and freeze the behaviour set as `scenarios_v1`, and (2) ideally run a blind second review of about 40 baseline rows to report reviewer agreement.
