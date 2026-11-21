# Grounding rerun comparison — 21 November 2026

The same 20 frozen questions were rerun after changing the drafting guards. This is a development regression check: because these cases informed the changes, it is not an independent estimate of accuracy. Raw model outputs and configuration fingerprints are in `grounding_fresh_v2_runs.jsonl`; the original runs and their adjudication are retained separately.

| Metric | Original run | Updated run |
| --- | ---: | ---: |
| Review-required drafts | 12 | 10 |
| Escalations | 8 | 10 |
| Primary annotated page in top 5 | 15 | 15 |
| All annotated required pages in top 5 | 14 | 14 |

Retrieval was unchanged; annotation counts are page hits, not comprehensive retrieval recall. Draft counts are not accuracy measures. The initial attempt could not reach the model under the network sandbox and was discarded; the completed run used the authorized endpoint outside that restriction.

Previously failed drafts 005 and 010 escalated at the subsection boundary check, 017 escalated on missing notification wording, and 019 escalated because the requested Code was not retrieved. These are prevented drafts, not newly correct answers. Case 009 moved from escalation to a draft; its omission of the source's permissive 'may' needs scrutiny. Cases 012 and 020 still escalated at citation and alignment checks respectively.

The updated run also produced an incorrect draft for 011: it cites page 85 and describes gig workers as a category, rather than providing the requested definition on annotated page 8. Case 015 again omits the deciding authority in the expected conditions. Case 006 may omit the expected requirement for one or more committees. Case 013 warrants verification of whether its citation fully supports the cross-page passage. These observations are preliminary and do not constitute independently adjudicated scores.

The comparison worksheet `grounding_fresh_v2_review.csv` includes all 20 cases and assistant notes; reviewer verdict fields are intentionally blank. Human verification remains necessary for review-required outputs. A new, separate evaluation set is required to estimate performance after development.
