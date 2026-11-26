# Trace dashboard (Langfuse)

Track B asks for runs to be traced through LangSmith, Langfuse or OpenTelemetry and for a trace dashboard
link in the technical report. The app keeps writing its local trace file (`reports/agent_traces.jsonl`) and
the Streamlit "Metrics & Traces" tab as before. When Langfuse keys are set, each chat request is **also**
sent to Langfuse, which gives an online dashboard with a shareable link. The app does not need to be
deployed: it can run on a laptop.

## What is sent

One trace per chat request (`POST /chat`), from `tracer.log_trace`:

| Langfuse item | Contents |
|---|---|
| Trace `chat` | Masked question, status, route, citations, session ID; tagged with route and status |
| Span (named after the route, e.g. `document_review`, `guardrail_refusal`, `leave_balance_tool`) | Start and end time (latency), route, status; `ERROR` level when the request failed |
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

Sending happens in the background with a five-second timeout; if Langfuse is unreachable, a warning is logged
and the chat response is unaffected. Short runs (scripts, evaluation runs) wait up to ten seconds at exit so
their last traces are sent. `LANGFUSE_HOST` must use HTTPS (plain HTTP only for localhost).
`LANGFUSE_ENVIRONMENT` (default `development`) is converted to a valid Langfuse name, e.g. `Demo Day` →
`demo-day`.

Evaluation runs through the chat API send traces only with `--keep-traces`, for example
`python scripts/run_evaluation.py run --test-set gold_v1 --system api --keep-traces`.
