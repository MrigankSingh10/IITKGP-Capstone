# Fresh grounding evaluation — 20 November 2026

The approved 20-question document-grounded set was evaluated using the hosted model and retrieval pipeline. The set is limited and was not independently blinded; these results are diagnostic, not a production accuracy estimate.

- 12 responses were returned as drafts requiring human review; 8 were escalated.
- The recorded primary source page appeared in the top five results for 15 of 20 questions. All recorded required pages appeared for 14 of 20, including the multi-page case. These are annotated page-hit counts, not exhaustive recall.
- Initial assistant review suggests seven passes, four failures, and one case requiring adjudication among the 12 drafts. These suggestions are not human-verified results.
- Observed potential failures include an incorrect waiting period (fresh-draft-005), the wrong provision for a union threshold (fresh-draft-010), and citing a different source from the one requested (fresh-draft-019). These require review and corrective work.
- Drafts remain subject to human review; escalation is used when the workflow cannot support an answer. Automated support checks are not sufficient to establish correctness.

The [review worksheet](grounding_fresh_v1_review.csv) contains proposed findings and blank reviewer verdict fields. Raw runs are in `grounding_fresh_v1_runs.jsonl`; the frozen questions are in `evaluation/grounding_fresh_v1.jsonl`.
