# Review-only document-grounded evaluation — 2026-11-20

## Scope and method

The actual 350-token hybrid-plus-rerank index and the course Qwen/Qwen3-8B endpoint were used on the same 19 single-turn questions selected in the earlier retrieval experiment. For each question the workflow retrieves up to five pages, constructs a draft using only validated excerpts, checks exact quotation and asks the same model to assess support. Passing drafts are explicitly `review_required`; no generated answer is automatically released. The model does not receive the expected answer or gold source page. Prior research and development used some of these questions, so this is an exploratory repeat, not a clean held-out evaluation. Each question has one user-provided gold page, not an independently exhaustive set of relevant pages.

## Observations

- 19 of 19 requests completed. Four escalated without a review draft; 15 returned model-checked drafts requiring human review.
- The recorded gold page was in the first five retrieved pages for 12/19 questions. This is a single-page hit, not comprehensive recall; other relevant pages can exist.
- An assistant's preliminary comparison suggests 10 drafts meet the listed answer and source conditions, five do not, and four were escalated. These are proposals, not independent human scores. See `grounded_v1_assisted_review.csv` for each question, expected conditions, draft, quotations and reasons. The entries need reviewer adjudication before reporting accuracy.
- Case draft-029 returned a statement about performance incentives in response to a question about the definition of corporation. The citation was a real passage and the model's additional support check returned `supported`. This is a confirmed answer-question relevance failure and shows the model check is unreliable. The workflow labeled the draft for review, not a final approved answer.
- Drafts 057, 061 and 069 cite different documents from those named in the questions; 061 and 073 also omit expected conditions. A correct statement from a different source does not establish what the requested document says.
- End-to-end measured time (local retrieval plus chat; cached query embeddings, excludes queue sleep) had median 6.98 seconds and nearest-rank p95 11.95 seconds. The endpoint reported 52,685 prompt and 5,211 completion tokens; pricing was not provided. VM04 assignment is inferred and still needs confirmation.

## Interpretation and open work

The selected gold subset was already used in development and source review; it is not an untouched held-out benchmark. The assistant's proposed grades are not independent legal or human review. The RAG workflow makes up to two model calls and produces review drafts, whereas the previously evaluated closed-book baseline makes one call and produces a direct response, so their raw numbers are not a fair validated quality comparison. The source date, legal applicability, prompt-injection, semantic support and 155/156 source-conflict issues remain unresolved. Do not release drafts automatically or claim a measured improvement.

User review is needed to adjudicate the 19 proposed verdicts and identify all supporting pages, with a separate unseen reviewed relevance/evaluation set for future claims. Preserve `evaluation/gold_v1.jsonl`; no tuning or modification to the frozen set. The existing user-provided baseline scores still require independent scoring review. The prompt-injection guard is heuristic and an earlier test was bypassed. Source text is untrusted.

## User-provided adjudication — 2026-11-20

The user supplied an audit described as independent of all 19 assistant-suggested verdicts: 10 pass, five fail, four `escalate_valid`. These decisions and the supplied reasons are recorded in `grounded_v1_assisted_review.csv` as user-provided; the reviewer was not identified and the audit saw the suggested verdicts, so independent blinding or human review is not established. Draft-049's answer paragraph is on PDF page 2 while the question begins on page 1. The remaining five failure notes distinguish relevance, incompleteness and source-attribution mismatches.

Under that audit's strict criteria, 10/19 cases had a passing review draft, and 10/15 drafts were marked pass. These are outcomes on a previously used exploratory subset, not validated system accuracy or a statistically representative precision estimate. The workflow issued no final answers automatically. All four escalations had their single recorded gold page absent from the top five; however, **seven** questions had that gold-page miss, so 4/7 gold-page-miss cases escalated and three returned drafts that the audit marked fail. Absence of the one recorded page does not prove that no other relevant evidence was retrieved. These are not measures of legal correctness, overall abstention quality or independent retrieval recall.

User-provided assessment of substantive factual content has not independently established current legal applicability. The draft-029 false-positive support judgment remains a blocking grounding failure. No modifications were made to the frozen gold set or to prompt/guard behavior based on this test run. Future claims require new, separately reviewed unseen relevance and answer evaluations and adjudication of user-provided scores.
