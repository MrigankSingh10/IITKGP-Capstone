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
systems side by side. Re-running `review-sheet` after adding a system keeps every mark already entered.

Use `--limit 3` for a quick check before a full run. Runs resume automatically: an interrupted run
continues where it stopped, and a run on a changed test set is refused.

## Test sets

| Name | Use | Note |
|---|---|---|
| `gold_v1` | 80 frozen Labour Code questions | Checksum verified on every run |
| `scenarios_v1` | 40 behaviour cases (refusal, injection, policy, tools, approvals) | Available after freezing |
| `scenarios_v0.1` | The draft of the above | Needs `--allow-draft`; for trying things out only, not for reported results |

## Systems

| `--system` | What it runs | Best test set |
|---|---|---|
| `closed_book` | The exact Week 1 prompts from `scripts/run_baselines.py` (`--strategy zero_shot / few_shot / decomposition`) | Both. Running it on the behaviour set gives the "before" number for refusals and injection. |
| `rag` | Phase 2 retrieval (`--chunk-size`, `--top-k`) plus `retrieval/grounded.py` | `gold_v1` (statutory only). Needs the local `data/processed` and `data/indexes` files. |
| `callable` | Any function, e.g. the agent: `--entrypoint hr_navigator.agents.graph:answer --name agent` | Both |

Credentials: pass `--chat-base-url --chat-model --chat-key-file --chat-ca-file` (and `--embedding-*`
for RAG), or set the `CHAT_*` / `EMBEDDING_*` variables from `.env.example` in your shell first
(Mac/Linux: `set -a; source .env; set +a`).

**Current limitation:** `grounded.py` deliberately escalates every answer until its accuracy issue is
fixed, so RAG runs will show decision "escalate" and no correct answers until Member 2 enables answers.

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
