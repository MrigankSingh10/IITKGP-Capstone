# Trace dashboard (Langfuse)

Track B asks for runs to be traced through LangSmith, Langfuse or OpenTelemetry and for a trace dashboard
link in the technical report. The app keeps writing its local trace file (`reports/agent_traces.jsonl`) and
the Streamlit "Metrics & Traces" tab as before. When Langfuse keys are set, each chat request is **also**
sent to Langfuse, which gives an online dashboard with a shareable link. The app does not need to be
deployed: it can run on a laptop.

## What is sent

One trace per chat request (`POST /chat` and `/chat/stream`), from `tracer.log_trace`. Every outcome is
traced, including requests that end early:

| Outcome | Route | Status |
|---|---|---|
| Answer from the documents | `document_review` | the pipeline decision, e.g. `review_required` |
| Leave balance | `leave_balance_tool` | `ok` |
| Refused by the guardrail | `guardrail_refusal` | `refused` |
| Not in English | `unsupported_language` | `refused` |
| Minimum-wage clarification | `minimum_wage_clarification` / `minimum_wage_source_unavailable` | `clarification_required` / `escalate` |
| Rate limited | `rate_limited` | `rate_limited` |
| Question too long (over 2,000 characters) | `input_too_long` | `refused` |
| Retrieval or leave-balance failure | `document_review` / `leave_balance_tool` | `error` |
| Unexpected error | `internal_error` | `error` |

Each trace is made up of:

| Langfuse item | Contents |
|---|---|
| Trace `chat` | Masked question, status, route, citations, session ID; tagged with route and status |
| Span (named after the route, e.g. `document_review`, `guardrail_refusal`, `leave_balance_tool`) | Start and end time (latency), route, status; `ERROR` level for errors, `WARNING` for rate limits |
| Generation `chat-model` (only when the model was called) | Prompt and completion tokens; cost only when a price is configured (an unknown price is left out, never sent as 0) |

Privacy: questions are masked by the guardrail and masked again before sending (PAN, Aadhaar, phone,
email, employee IDs). The employee ID is never sent. Set `LANGFUSE_SEND_QUERY_TEXT=false` to send no question
text at all. Keys are read from the environment, never logged, and must not be committed.

## Set up (once)

1. Create a free project at <https://cloud.langfuse.com> (or use a self-hosted Langfuse) and create an API key
   pair under **Project settings → API keys**.
2. In the terminal that will run the API, set the keys (the app does not read `.env` automatically):

   ```bash
   export LANGFUSE_PUBLIC_KEY='pk-lf-...'
   export LANGFUSE_SECRET_KEY='sk-lf-...'
   # optional: export LANGFUSE_HOST='https://us.cloud.langfuse.com'   (default https://cloud.langfuse.com)
   ```

3. Check the keys, send one test trace and print the dashboard link:

   ```bash
   python scripts/trace_dashboard.py --send-test
   ```

4. Start the API and UI as in the README and ask a few questions. They appear in the dashboard within
   seconds.

## The link for the report

`scripts/trace_dashboard.py` prints the project's trace page, for example
`https://cloud.langfuse.com/project/<project-id>/traces`. Examiners need access to that project: invite them
as viewers in Langfuse, or share individual traces publicly from the trace view.

Sending happens on two background workers fed by a bounded queue (500 traces), with a five-second timeout
per request. If Langfuse is slow and the queue fills, new traces are dropped and counted in a warning rather
than creating more threads; if a worker cannot be started, export is skipped. The chat response is never
affected. Short runs (scripts, evaluation runs) wait up to ten seconds at exit so
their last traces are sent. `LANGFUSE_HOST` must use HTTPS (plain HTTP only for localhost).
`LANGFUSE_ENVIRONMENT` (default `development`) is converted to a valid Langfuse name, e.g. `Demo Day` →
`demo-day`.

To fill the dashboard now, use the app (the Streamlit UI or `POST /chat`); every request is traced.

Evaluation runs through the chat API (`--system api`) are part of the end-to-end evaluation change, which is
not on `main` yet. Once it is merged, add `--keep-traces` so those runs are also traced, for example
`python scripts/run_evaluation.py run --test-set gold_v1 --system api --keep-traces`.
