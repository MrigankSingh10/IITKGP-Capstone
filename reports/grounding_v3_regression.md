# Grounding regression checks — 21 November 2026

The 20 previously used questions were rerun after definition, modality and authority guards were added. These questions informed the changes and are a development set, not an independent accuracy test. Results are in `grounding_fresh_v3_runs.jsonl`, with the workflow fingerprint captured per row. The subsequent targeted changes described below were made after this run, so the run does not evaluate the final code version end to end.

The v3 run returned 7 review-required drafts and 13 escalations. Cases 009, 011 and 015 escalated respectively for missing discretionary wording, a quotation that did not define the requested term, and an omitted decision-making authority. Escalation blocks the particular draft; it does not prove that the system can produce a complete correct answer. The previous run's case 012 failed quote validation and case 020 failed source/alignment checks.

A separate targeted diagnostic reproduced 012: the model had merged non-contiguous source wording into a supposed verbatim quotation. The citation gate correctly rejected it. The prompt now requests separate exact citations for non-contiguous material; a subsequent targeted call produced a valid contiguous quote and a review-required draft. No quotation validation was weakened.

A targeted diagnostic for 020 showed the accepted OCR table row was quoted correctly, but the alignment model did not see the page heading identifying Annexure B. The checker now receives the first 300 characters of the source page as untrusted context. A subsequent targeted call returned a review-required draft citing the row, preserving OCR warnings. The heading is context for verification, not a replacement for the cited source quote.

These individual calls are diagnostic observations, not independent accuracy estimates. Checkers can still be wrong, and all generated answers remain review-required. A separate, independently reviewed question set and full evaluation of the final workflow remain to be completed.
