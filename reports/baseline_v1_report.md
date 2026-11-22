# Phase 1 closed-book baseline — 2026-11-18

**Reconciled official baseline (2026-11-21):** the team members agreed to use the strict rubric (the frozen gold rule "no partial correctness"). The official marks are in `baseline_v1_review_reconciled.csv` and `baseline_v1_metrics_reconciled.json`: **19/240 (7.9%)**; zero-shot 6/80 (7.5%), few-shot 5/80 (6.25%), decomposition 8/80 (10.0%). See "Reconciled baseline" at the end of this report. The two original reviews are kept unchanged for traceability.

The user approved and froze 80 document-only cases (SHA256 `00945556195f2403b17a7a4078b642f4fe1c3eb8b68109ed0a04a92b3a2238bf`). We ran the permitted Qwen/Qwen3-8B model on the supplied VM04 endpoint: one request per case and strategy, 240 requests, all HTTP/API calls succeeded. VM04 was inferred from the supplied CA and still needs group-assignment confirmation. The same 80 questions, temperature 0 and max output 512 were used in each strategy. For six cases an earlier user message was also supplied; this is not a test of durable state. No PDF content, gold answers or retrieval were sent. Strategies: zero-shot structured; few-shot with general uncertainty examples; decomposition with a concise self-check and no request for private reasoning. See `scripts/run_baselines.py` for exact prompts and settings.

| Strategy | Calls succeeded | Valid JSON with string answer and uncertainty | Mean latency (seconds) | Reported prompt / completion tokens |
|---|---:|---:|---:|---:|
| Zero-shot | 80/80 | 66/80 (82.5%) | 1.803 | 5,796 / 6,346 |
| Few-shot | 80/80 | 80/80 (100%) | 1.050 | 9,876 / 3,556 |
| Decomposition | 80/80 | 80/80 (100%) | 0.966 | 6,676 / 3,229 |

Latency is elapsed per call and includes network/service time, not the one-second queue interval. The endpoint reported usage; no price was supplied, so cost is unknown. JSON validity is not factual correctness, source grounding, or evidence of a better system. Correctness is scored in `baseline_v1_review.csv` (see "Answer accuracy after review" below); refusal correctness does not apply because the frozen set has no refusal cases, and `docs/baseline_review_guide.md` explains review. The runs are in `baseline_v1_runs.jsonl`; aggregate data are in `baseline_v1_metrics.json`.

## Illustrative observations, not an aggregate score

- `draft-033`, zero-shot: answered that State does not include a Union territory; the gold case cites Code on Wages PDF page 4, which says it does. It also returned a boolean for `uncertainty`, violating the requested string shape.
- `draft-037`, zero-shot: asserted the Social Security Code did not specifically address a later fall below the First Schedule threshold, whereas the cited PDF page 2 contains section 1(8) on continued application. This is a source-grounding failure in a closed-book setting; no retrieval was available.
- `draft-001`, decomposition: said the date is determined by the appropriate government; the cited text names the Central Government and permits different dates for different provisions. This is an incomplete or imprecise answer even though JSON is valid.
- `draft-001`, few-shot: avoided stating the manner of commencement; the cited page specifies notification by the Central Government. This cautious answer omits a gold condition.
- `draft-060`, zero-shot: claimed the December 2025 FAQ was not a recognized or official document. The supplied corpus has the named FAQ. The prompt had not supplied that document; lack of access does not justify asserting it does not exist.

These examples are preliminary manual comparisons, not a substitute for full human scoring. Retrieved evidence, legal applicability and subsequent amendments must be checked before using any answer.

## Limitations and next gate

The user approved the set as a whole; individual case records retain their original `unreviewed` status and should not be described as independently legally reviewed. The 80 questions cover 10 PDFs and 21 page pairs; six have only a previous user turn. The gold set has no explicit refusal cases after the user restricted it to document questions, so refusal correctness is not meaningfully measurable from this set. Performance of tool use, durable state and task completion requires additional document-only scenarios in later phases. Keep the set frozen; document errors for a future separately versioned set. Full human review and grading remain outstanding before claiming correctness or completing the Phase 1 evaluation gate. Do not start the graph before that gate.

## Answer accuracy after review — 2026-11-19

All 240 responses were scored in `baseline_v1_review.csv`, following `docs/baseline_review_guide.md`: 1 only when every gold condition is met and nothing false is added; declining counts as 0 because every frozen case expects an answer. **Review process:** marks and reasons were first suggested by an AI assistant (Claude), comparing each response with the frozen gold conditions only (the source PDFs were not available to it). A team member then reviewed them; reviewer name: Hrishikesh. The reviewer kept every suggested mark (240/240 agreement). An independent blind second review of a sample is recommended before final submission.

| Strategy | Correct | Accuracy | Hallucination | Reasoning error | Evidence unavailable |
|---|---:|---:|---:|---:|---:|
| Zero-shot | 9/80 | 11.3% | 51 | 9 | 11 |
| Few-shot | 10/80 | 12.5% | 40 | 16 | 14 |
| Decomposition | 14/80 | 17.5% | 56 | 9 | 1 |
| **All** | **33/240** | **13.8%** | **147** | **34** | **26** |

In the project error taxonomy (`docs/error_taxonomy.md`) this team review maps to `hallucination` 147, `reasoning_error` 34 and `abstention` 26; the strict adjudication in `baseline_v1_review.csv` maps to `hallucination` 108, `reasoning_error` 56, `abstention` 43 and `format_error` 14. The two reviews agree on 226 of 240 correct/incorrect marks (94.2%). Category definitions: *hallucination* states something false (including claiming a real document does not exist or does not cover the topic); *reasoning error* is partly right or too generic and misses a required condition; *evidence unavailable* declines without asserting a falsehood. Retrieval and tool categories do not apply to a closed-book baseline. Only 16 of 80 questions were answered correctly by at least one strategy; six by all three (draft-002, 004, 024, 025, 045, 074). Accuracy was similar on Code text (17/132) and FAQ questions (16/108). No response with invalid JSON was correct. Refusal correctness is not applicable: the frozen set has no refusal cases. Cost remains unknown.

## How Qwen3-8B fails without documents

1. **Confident fabrication of specific facts.** Wrong law numbers (claims the Codes have none), wrong dates (1935, 1947, 2023), wrong components (house rent allowance instead of retaining allowance), wrong rates (overtime 1.5× instead of not less than twice), and the opposite of the text (closure as *temporary* suspension; "State" excluding Union territories).
2. **Wrong jurisdiction.** 21 responses frame Indian law as US or Australian (Social Security Administration, OSHA, Congress, "federal government", "whole of Australia").
3. **Denying the source exists or covers the topic.** 9 responses say a supplied FAQ "does not exist" or is "not a recognized document"; many more claim a document "does not address" a topic that it does address. Lack of access is turned into a false negative claim.
4. **Generic textbook definitions instead of statutory ones.** Definitions omit the cross-references that make them correct (section 6, section 43, Companies Act section 2(20), Chapter IV).
5. **Uncertainty is not calibrated.** Decomposition marked 42 of its 66 wrong answers with "low" (or "0"/"false") uncertainty. It rarely declined (1 case), so its higher accuracy comes with the most hallucinations.
6. **Format drift in zero-shot.** 14/80 responses returned a boolean `uncertainty`, breaking the requested schema; few-shot and decomposition were always valid.

**Implications for later phases:** most failures need the source text, which RAG supplies; citation checks and a critic must reject "document does not exist / does not mention" claims when retrieval found the page; uncertainty fields from the model cannot be trusted as a confidence signal; structured examples (few-shot) fix the format but not the facts.

## Usage and cost per query

Token usage is taken from the API's reported `usage` for every call; cost needs a price, which has not been provided. `scripts/summarize_baselines.py` computes cost automatically once `configs/pricing.json` has both prices: cost per query = (prompt tokens × input price + completion tokens × output price) ÷ 1,000,000, averaged over queries.

| Strategy | Prompt tokens / query | Completion tokens / query | Total tokens / query | Cost / query |
|---|---:|---:|---:|---|
| Zero-shot | 72.5 | 79.3 | 151.8 | unknown (price pending) |
| Few-shot | 123.5 | 44.5 | 167.9 | unknown (price pending) |
| Decomposition | 83.5 | 40.4 | 123.8 | unknown (price pending) |

Few-shot spends about 70% more prompt tokens than zero-shot (its examples) but produces shorter answers; decomposition is the cheapest overall and the most accurate of the three, though it also hallucinates most.

## Reconciled baseline — 2026-11-21

The two reviews agreed on 226 of 240 correct/incorrect marks (94.2%). All 14 differences were bare yes/no or partly complete answers that the team review accepted and the strict review rejected; the team members agreed to follow the strict review, which applies the frozen gold rule "no partial correctness". Reviewer identity is recorded as team members.

| Strategy | Correct | Accuracy |
|---|---:|---:|
| Zero-shot | 6/80 | 7.5% |
| Few-shot | 5/80 | 6.25% |
| Decomposition | 8/80 | 10.0% |
| **All** | **19/240** | **7.9%** |

Each of the 221 wrong answers has one category from `docs/error_taxonomy.md`: `hallucination` 150, `reasoning_error` 49, `abstention` 22. The two reviews chose the same category for 153 answers; for the other 54 the taxonomy's precedence rule decided (the more serious category is primary, and a format error is primary only when the content is acceptable). The remaining 14 wrong answers were marked wrong only by the strict review and take its category. Every decision is traceable in the sheet's `mark_basis`, `category_basis` and original-review columns, and `scripts/reconcile_baseline_reviews.py` reproduces the sheet exactly.

The earlier sections of this report describe the team review (33/240) and remain as the record of that review; the reconciled figures above are the ones to use for comparisons.
