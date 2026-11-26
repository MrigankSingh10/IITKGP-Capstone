# Evaluation runner guide

Owner: Member 4 (prompting / evaluation). One tool scores every version of the system — closed-book
baseline, RAG and the agent — on the same test sets, so results are directly comparable.

## Three steps

```bash
# 1. Ask the system every question and save its answers
python scripts/run_evaluation.py run --test-set gold_v1 --system closed_book --strategy decomposition

# 2. Build the review sheet; people fill in `correct` (1/0) and `failure_category`
python scripts/run_evaluation.py review-sheet --test-set gold_v1 \
    --runs reports/evaluation/gold_v1__closed_book_decomposition.jsonl

# 3. Compute the metrics (re-run whenever more rows are marked)
python scripts/run_evaluation.py summarize --test-set gold_v1 \
    --runs reports/evaluation/gold_v1__closed_book_decomposition.jsonl
```

Outputs go to `reports/evaluation/`: `<set>__<system>.jsonl` (answers), `<set>_review.csv` (marks),
`<set>_metrics.json` and `<set>_metrics.md` (comparison table). Pass several `--runs` files to compare
systems side by side.

Safeguards:

- **Retries:** re-running `run` skips cases already answered successfully and retries failed ones
  (for example a temporary API error). The file keeps every attempt; the latest one per case counts.
- **Right test set:** `review-sheet` and `summarize` refuse answer files produced on another test set
  or another version of it, so answers are never scored against the wrong expected results.
- **Marks stay with their answer:** every answer has an `answer_fingerprint`. Refreshing the review
  sheet keeps a mark only if the answer is unchanged; otherwise the mark is cleared and the row is
  noted for re-marking. `summarize` ignores marks whose answer has changed and reports how many.

Use `--limit 3` for a quick check before a full run. A run on a changed test set is refused.

## Test sets

| Name | Use | Note |
|---|---|---|
| `gold_v1` | 80 frozen Labour Code questions | Checksum verified on every run |
| `scenarios_v1` | 40 behaviour cases (refusal, injection, policy, tools, approvals) | Available after freezing |
| `scenarios_v0.1` | The draft of the above | Needs `--allow-draft`; for trying things out only, not for reported results |
| `safety_doc_v1` | 18 frozen document-only safety cases (refusal, tampered document, out of scope, clarify) | Checksum covers the cases and the tampered pages |
| `grounding_holdout_v1` | The 20-question grounding hold-out, after its freeze | **Run once per system**, for the final measurement only: `run` needs `--final`, and each run is recorded in `evaluation/run_once_log.jsonl` so it cannot be repeated (see [hold-out guide](holdout_review_guide.md#final-run-once)). Never tune on it |

## Systems

| `--system` | What it runs | Best test set |
|---|---|---|
| `closed_book` | The Week 1 prompts from `scripts/run_baselines.py` (`--strategy zero_shot / few_shot / decomposition`), plus one sentence asking the model to state its `decision` (answer, refuse, clarify or escalate). A missing or invalid decision is recorded as missing, never assumed to be an answer. | Both. Running it on the behaviour set gives the "before" number for refusals and injection. Because of the added sentence, its gold-set results are a fresh run, not a copy of the Week 1 numbers. |
| `rag` | Hybrid retrieval plus the current grounded-draft pipeline `retrieval/draft_review.draft_for_review` (`--index accepted_ocr` by default, `--chunk-size 350`, `--top-k 5`, as in the team's grounding runs) | `gold_v1` (statutory only). Needs the local `data/processed` and `data/indexes` files. |
| `callable` | Any function, e.g. the agent: `--entrypoint hr_navigator.agents.graph:answer --name agent` | Both |
| `api` | **End-to-end:** each question goes through `POST /chat`, the same API the Streamlit app uses (guardrail, English check, minimum-wage clarification, RAG drafting and citation checks). Runs the FastAPI app in-process by default, or a running server with `--api-url http://127.0.0.1:8000`. | `safety_doc_v1` (12 cases; the 6 tampered-document cases are skipped because `/chat` cannot receive a fake page, so run those with `rag`) and later the hold-out. Needs the same local corpus and chat configuration as the demo. |

Credentials for `closed_book` and `rag`: pass `--chat-base-url --chat-model --chat-key-file --chat-ca-file`
(and `--embedding-*` for RAG), or set the `CHAT_*` / `EMBEDDING_*` variables from `.env.example` in your
shell first (Mac/Linux: `set -a; source .env; set +a`).

For `api` the chat server uses its own settings, exactly as in the demo: the `CHAT_*` variables, or
`configs/chat.local.json` when they are not set (in-process), or whatever the server behind `--api-url`
was started with. The runner therefore refuses `--chat-*` and `--embedding-*` with `--system api`,
rather than ignoring them and possibly running a different model.

**How RAG results are recorded:** the pipeline either escalates or returns a draft labelled
`review_required` (it never releases an answer automatically). For scoring, a draft counts as the
system's answer (`decision: answer`) and is marked by people like any other answer; the original label
is kept in `pipeline_decision` and `needs_human_review`. Escalations stay `escalate`, so on `gold_v1`
(where an answer is expected) they show as abstentions. The pipeline's own runs currently record no
token usage, so RAG cost per query will show as unknown until usage is captured.

## End-to-end through the chat API

```bash
python scripts/run_evaluation.py run --test-set safety_doc_v1 --system api
python scripts/run_evaluation.py run --test-set safety_doc_v1 --system rag     # all 18, incl. tampered pages
python scripts/run_evaluation.py review-sheet --test-set safety_doc_v1 --runs reports/evaluation/safety_doc_v1__*.jsonl
python scripts/run_evaluation.py summarize --test-set safety_doc_v1 --runs reports/evaluation/safety_doc_v1__*.jsonl
```

The API's `status` becomes the decision: `review_required` and `evidence_only` → answer (still marked
by people), `escalate` → escalate, `refused` (guardrail or non-English) → refuse,
`clarification_required` → clarify. `/chat` returns only the verified sources, so the gold-page check
uses those. The API keeps no conversation history, so follow-up questions lose their context (flagged
as `conversation_context_dropped`). The in-process run does not write the demo trace file unless
`--keep-traces` is given; model tokens are still counted for the cost summary. With `--api-url` the
server's reply carries no token counts, so usage and cost are reported as unavailable, never as zero (the Markdown table shows "unavailable" in the tokens column). Without the chat
configuration the API returns candidate passages only (`evidence_only`), which reviewers will mark as
not answering the question.

## Plugging in the agent (for Member 3)

Expose one function and pass it with `--system callable`:

```python
def answer(question: str, conversation_context: list[dict], auth_context: dict, context: dict) -> dict:
    ...
    return {
        "decision": "answer",            # answer | refuse | clarify | escalate
        "answer": "...",
        "sources": [...],                 # product_spec source objects
        "calculations": [...],
        "tool_actions": [{"tool": "get_leave_balance", "args": {"leave_type": "annual"},
                          "auth_context": {"employee_id": "demo-001"}}],  # recorded by the server
        "uncertainty": "...",
        "approval_required": False,
        "trace_id": "...",               # tracing id, if available
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
```

`auth_context` holds the authenticated employee id; `context` is the whole test case (including
`injected_documents`, `preconditions` and `reference_date`) so the test harness can set up state.
`tool_actions` must list every tool the agent actually called, with its arguments: the runner checks
required and forbidden calls against it. Each entry must also carry the `auth_context` the **server**
used for that call (from the signed-in session, never from the model's arguments or the user's
message). For `get_employee_profile`, `get_leave_balance` and `get_request_status`, a missing or
mismatched identity fails the case through `scenarios.unauthorized_identity_calls`, even if no data
was shown. RAG runs should also return `retrieved_page_ids` so retrieval misses can be detected.

## What is measured

| Metric | How |
|---|---|
| Accuracy (overall and per category) | Human marks in the review sheet |
| Decision accuracy | Automatic: decision equals the expected decision |
| Refusal correctness | Automatic: refuse cases refused, no forbidden tool used |
| Injection resistance | Human-marked correct and automatic checks passed, on injection cases |
| Task completion | Action cases: automatic checks passed and marked correct |
| Auto-check pass rate | All automatic checks passed (decision, required/forbidden tools, approval flag, trusted identity on identity-sensitive tools, sources for statutory answers, gold page retrieved) |
| Tool calls, latency (mean, p95), tokens per query, cost | From each answer's record and `configs/pricing.json` |
| Failure categories | Reviewer's `failure_category`, using `docs/error_taxonomy.md`; the sheet's `suggested_category` gives the automatic suggestion. Also reported by layer and as `auto_detected_failures` before review. |

## English-only scope

Use English questions and English evidence for new product evaluations. The frozen historical files remain unchanged. `scripts/evaluate_relevance_english.py` performs an offline English-labeled subset regression on the existing assistant-reviewed relevance pilot; it is small, incompletely labeled and not independent. Its subset scores must not be compared directly to the full multilingual historical aggregate. The script filter used in retrieval is not reliable language identification.
