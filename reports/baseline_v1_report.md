# Phase 1 closed-book baseline — 2026-11-18

The user approved and froze 80 document-only cases (SHA256 `00945556195f2403b17a7a4078b642f4fe1c3eb8b68109ed0a04a92b3a2238bf`). We ran the permitted Qwen/Qwen3-8B model on the supplied VM04 endpoint: one request per case and strategy, 240 requests, all HTTP/API calls succeeded. VM04 was inferred from the supplied CA and still needs group-assignment confirmation. The same 80 questions, temperature 0 and max output 512 were used in each strategy. For six cases an earlier user message was also supplied; this is not a test of durable state. No PDF content, gold answers or retrieval were sent. Strategies: zero-shot structured; few-shot with general uncertainty examples; decomposition with a concise self-check and no request for private reasoning. See `scripts/run_baselines.py` for exact prompts and settings.

| Strategy | Calls succeeded | Valid JSON with string answer and uncertainty | Mean latency (seconds) | Reported prompt / completion tokens |
|---|---:|---:|---:|---:|
| Zero-shot | 80/80 | 66/80 (82.5%) | 1.803 | 5,796 / 6,346 |
| Few-shot | 80/80 | 80/80 (100%) | 1.050 | 9,876 / 3,556 |
| Decomposition | 80/80 | 80/80 (100%) | 0.966 | 6,676 / 3,229 |

Latency is elapsed per call and includes network/service time, not the one-second queue interval. The endpoint reported usage; no price was supplied, so cost is unknown. JSON validity is not factual correctness, source grounding, or evidence of a better system. Full correctness and refusal correctness require human review; `baseline_v1_review.csv` is an unscored worksheet, and `docs/baseline_review_guide.md` explains review. The runs are in `baseline_v1_runs.jsonl`; aggregate data are in `baseline_v1_metrics.json`.

## Illustrative observations, not an aggregate score

- `draft-033`, zero-shot: answered that State does not include a Union territory; the gold case cites Code on Wages PDF page 4, which says it does. It also returned a boolean for `uncertainty`, violating the requested string shape.
- `draft-037`, zero-shot: asserted the Social Security Code did not specifically address a later fall below the First Schedule threshold, whereas the cited PDF page 2 contains section 1(8) on continued application. This is a source-grounding failure in a closed-book setting; no retrieval was available.
- `draft-001`, decomposition: said the date is determined by the appropriate government; the cited text names the Central Government and permits different dates for different provisions. This is an incomplete or imprecise answer even though JSON is valid.
- `draft-001`, few-shot: avoided stating the manner of commencement; the cited page specifies notification by the Central Government. This cautious answer omits a gold condition.
- `draft-060`, zero-shot: claimed the December 2025 FAQ was not a recognized or official document. The supplied corpus has the named FAQ. The prompt had not supplied that document; lack of access does not justify asserting it does not exist.

These examples are preliminary manual comparisons, not a substitute for full human scoring. Retrieved evidence, legal applicability and subsequent amendments must be checked before using any answer.

## Limitations and next gate

The user approved the set as a whole; individual case records retain their original `unreviewed` status and should not be described as independently legally reviewed. The 80 questions cover 10 PDFs and 21 page pairs; six have only a previous user turn. The gold set has no explicit refusal cases after the user restricted it to document questions, so refusal correctness is not meaningfully measurable from this set. Performance of tool use, durable state and task completion requires additional document-only scenarios in later phases. Keep the set frozen; document errors for a future separately versioned set. Full human review and grading remain outstanding before claiming correctness or completing the Phase 1 evaluation gate. Do not start the graph before that gate.
