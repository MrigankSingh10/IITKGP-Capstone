# Imported baseline review — 2026-11-19

The user supplied a 240-row evaluation. All 240 case/strategy pairs map uniquely to saved baseline runs, and the row-level `json_valid` values match recorded results. Scores and notes were imported into both baseline review sheets as **user-provided evaluation, reviewer not identified**. No independent human scoring is claimed.

The supplied narrative summary says 24 passes and 216 failures, but its row-by-row table contains **32 passes and 208 failures**. Its statement that 12 rows have invalid JSON conflicts with both its own table and the saved runs, which contain **14 invalid JSON responses**. The sheet preserves the individual table scores; no score was changed to force the summary totals.

| Strategy | Supplied passing rows | Total | Provisional rate |
|---|---:|---:|---:|
| zero-shot | 10 | 80 | 12.5% |
| few-shot | 9 | 80 | 11.25% |
| decomposition | 13 | 80 | 16.25% |
| overall | 32 | 240 | 13.33% |

These are provisional scores under the supplied evaluator's judgments; they are not verified accuracy results. Examples requiring adjudication were flagged directly in both sheets: draft-051 scores a simple `No` as correct although the gold condition also asks for facility arrangements and allowance, and draft-024 decomposition scores a bare `No` despite additional stated gold conditions. Some review notes also cite incorrect clause numbers: draft-027 is section 2(e), draft-028 is 2(f), and draft-031 is 2(t), as shown on the supplied PDF pages. Scores remain unchanged pending review.

The baseline was closed-book: documents were not given to the model, and the instructions encouraged uncertainty. An abstention may fail a content-completeness criterion while still being safer than an unsupported assertion; do not call that a refusal-safety failure without a separate appropriate test. Some supplied categories combine JSON-schema errors with factual errors, so they should not be treated as a complete, mutually independent root-cause taxonomy. Human adjudication, including these scoring rules and reviewer identity, remains necessary before claiming measured system accuracy or improvement.

## User-provided adjudication — 2026-11-20

The user supplied decisions for all 16 flagged rows using a strict interpretation of every expected condition. The three previously failing rows (draft-027/zero-shot, draft-028/zero-shot and draft-031/zero-shot) remain 0 with corrected clause notes; the other 13 rows changed from 1 to 0. Previous scores are preserved in each affected row's notes. The review and adjudication sheets label the decisions as user-provided, with the reviewer not identified; independent human scoring has not been established. Draft-058/zero-shot was identified by the supplied review as borderline but scored 0 under the chosen strict rubric.

| Strategy | Pass | Total | Strict user-provided pass rate |
|---|---:|---:|---:|
| Zero-shot | 6 | 80 | 7.5% |
| Few-shot | 5 | 80 | 6.25% |
| Decomposition | 8 | 80 | 10.0% |
| Overall | 19 | 240 | 7.92% |

These scores supersede the earlier row-table total for reporting this supplied adjudication. They are not independently verified accuracy, and the previously noted inconsistency with the original narrative summary remains a historical fact. The closed-book model did not receive the PDFs; an uncertainty or abstention can fail strict answer completeness without being a safety failure.
