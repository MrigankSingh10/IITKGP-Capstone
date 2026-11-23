# Shared team work log and handoff

As of 2026-11-22. This is the shared living coordination record for all members and AI agents. Read it and the linked evidence at the start of each session; update the status table and append a dated session entry before finishing. Commit it with the relevant work so Git carries the record between collaborators. Reports and code remain authoritative for detailed evidence; link them here instead of copying their contents. Do not record credentials, employee details or private traces.

## Current work and ownership

| Owner | Status and next action |
| --- | --- |
| Member 1 — domain/data | Priority source dates and version conflicts checked. Eleven OCR page spot-checks are ready for a human reviewer. Written faculty wording remains open and the release uses official links. See [source verification](../reports/member_1_source_verification_2026-11-22.md). |
| Member 2 — retrieval | Review-only retrieval adapter and citation contract ready for Member 3. The new 12-question English packet awaits independent labels. See [Phase 2 status](../reports/phase_2_summary.md) and the [review guide](relevance_english_independent_review_guide.md). |
| Member 3 — orchestration | Phase 3 graph, typed state, routing, budgets and tests remain open. Before graph development, satisfy the evaluation gate below and agree interfaces with Members 2 and 4. |
| Member 4 — HR tools/security | Own the existing synthetic tools and their integration. Drafts, persistent requests, overlap handling, action-bound confirmation, replay protection, idempotent submissions and tickets remain open; see [Phase 3 status](../reports/phase_3_summary.md). |
| Member 5 — integration/evaluation | Coordinate API/UI, evaluation and deployment. The current API hook is a stub; align the interface and trace handling with document-only scope before integration. |
| All members | Review evidence and record ownership, decisions, validation and blockers here each session. |

Ownership is distinct from project phase: the user accepted the Phase 2 baseline for handoff, not the outstanding quality gates. Phase 3 has begun with deterministic tools, but its exit criteria are not met.

## Member 1/2 handoff to Members 3/4

- The working corpus has 126 source PDFs, 1,767 page documents and 9,615 accepted-OCR 200-token chunks (5,605 at 350). Eleven transcriptions were accepted by the user; retain OCR warnings and original scans. Source dates, applicability, independent OCR review, redistribution and written faculty clarification remain incomplete. See [closeout](../reports/member_1_completion_checklist.md) and [document status](../reports/evaluation_document_status_2026-11-20.md).
- The accepted 200-token `hybrid_rerank` configuration achieved Hit@3/5/10 of 0.55/0.65/0.80 and MRR@10 0.5692 on the fixed 20-question English regression. This measures one expected page per question, has incomplete non-independent labels, and is not general retrieval recall or answer accuracy. Details and caveats: [retrieval update](../reports/retrieval_window_section_update.md) and [case results](../reports/random_gold_window_candidate_regression.json).
- Support English questions and English evidence. Script filtering is heuristic and can miss mixed-script English or admit other Latin-script languages. Source relationships are review leads, not applicability decisions. Escalate missing or conflicting evidence.
- Search outputs include `source_pdf_id`, `original_title`, `pdf_page_number` (1-based PDF page), `source_url`, `scope`, `text`, `extraction_status`, `source_warnings`, score and available source tags, relationships and sparse-page disposition. Review-draft citations use `page_number` and `quote_or_section` alongside the source identity, URL, scope, extraction status and warnings. Preserve these fields and verify exact contiguous quotations against the registered page; page identity or a valid quote alone does not prove relevance, support or legal applicability.
- The launch-safe behavior is review-only: `--draft-for-review` returns an unverified `review_required` draft or escalation, never an approved final answer. Model checks can fail; independent grounding and adversarial assessment remain outstanding. The latest full grounding development run predates two targeted fixes; see [regression report](../reports/grounding_v3_regression.md). The normal generated-answer path also fails closed.
- Member 4 already has read-only synthetic profile, leave balance, Karnataka 2027 holiday and leave calculation adapters in [synthetic_hr.py](../src/hr_navigator/tools/synthetic_hr.py), plus separately seeded fictional fixtures. `TrustedIdentity` is an internal trust boundary, not authentication; a future server must construct it from an authenticated session, never model arguments. These tools are not connected to a graph or endpoint and do not reserve or approve leave. See [Phase 3 status](../reports/phase_3_summary.md) for supported policies and failure boundaries.
- Graph development is gated by human-reviewed, frozen evaluation cases and recorded baseline numbers in the [product specification](product_spec.md). Reconcile document and synthetic operational evaluation scope before claiming that gate. No LangGraph is implemented; Member 3 owns orchestration, Member 4 owns tools/security, and Member 5 owns integration/evaluation.

## Running and consuming the handoff

Follow [README setup](../README.md#setup-and-tests) and corpus/index instructions; generated corpora, caches and credentials are local and excluded from Git. From the repository root, after building the accepted-OCR corpus, local BM25 needs no hosted API:

```bash
python scripts/search_corpus.py 'Does State include a Union territory?' --mode bm25 --size 200 --code 'Code on Wages'
python scripts/review_evidence.py 'Does State include a Union territory?' --code 'Code on Wages'
```

Member 3 can call [the Python review adapter](../src/hr_navigator/retrieval/review_adapter.py) without a subprocess. Load accepted-OCR chunks and registered pages, enrich pages with source context, and use `ReviewAdapter.retrieve(ReviewRequest(...))`. Branch on `evidence_only`, `review_required`, or `escalate`. Evidence excerpts appear in `passage`; draft citations use `quote_or_section`. This local BM25 adapter is separate from the measured hybrid configuration. See the [runnable handoff example](../reports/phase_2_summary.md#review-adapter-handoff-2026-11-22).

For the accepted hybrid configuration, use `scripts/search_corpus.py --mode hybrid_rerank --size 200` with its `--key-file`, `--ca-file`, `--base-url` and `--model` options and the accepted-OCR cache. See `--help`; the default search size is 350. `scripts/ask_documents.py --help` describes both hosted API configurations: it currently loads **350-token** chunks, so its draft results are not the 200-token benchmark. `scripts/review_evidence.py` displays excerpts for review. The README documents setup and the separate stub UI/API launch.

Run the existing synthetic-tool checks with `.venv/bin/python -m pytest -q tests/test_synthetic_hr.py tests/test_phase0.py`. No real HR integration or authenticated endpoint exists. Do not enter real employee details in the prototype; it records supplied queries and IDs in local traces.

## Key decisions and open checks

- Keep frozen sets and historical reports unchanged; don't tune against regression labels. The baseline reviews are reconciled (strict rubric, 19/240); independently review new relevance, grounding hold-out and safety cases before performance claims.
- Keep review-only output until evidence justifies changing it. Validate source versions, dates, conflicts, sparse pages and current applicability; obtain written faculty clarification and resolve redistribution scope.
- Separate synthetic handbook rules from statutory evidence. Do not infer unrecorded leave policies or treat a balance check as a reservation.

## Session entries

### 2026-11-22 — Member 1/2 handoff preparation

- Owner: team coordination / AI agent.
- Work: established this shared log and linked it from the README; summarized the existing handoff and Phase 3 split.
- Files: `docs/team_work_log.md`, `README.md`. Evidence: linked reports above.
- Validation: checked command flags and citation fields against current scripts and source; local Markdown links checked.
- Blockers / next action: outstanding independent reviews, written faculty clarification and the graph evaluation gate remain with the team.

### Session template

Copy this heading and fill it in for each session:

```markdown
### YYYY-MM-DD — Short description

- Owner:
- Work and decisions:
- Files / evidence:
- Validation and results:
- Blockers / next action / owner:
```

### 2026-11-22 — Handoff branch preparation

- Owner: team coordination.
- Work and decisions: packaged the domain and retrieval milestones, shared handoff, and initial synthetic HR tools for review. Evaluation artifacts identify assistant-reviewed judgments and preserve the earlier benchmark results.
- Files / evidence: the Member 1 closeout, Phase 2 and Phase 3 reports, and verification artifacts linked above.
- Validation and results: repository tests, frozen input checksums and the staged changes were checked before publication.
- Blockers / next action / owner: independent evaluation and faculty clarification remain open. Members 3 and 4 own the next implementation milestones.

### 2026-11-22 — Source and retrieval verification

- Owner: Members 1 and 2.
- Work and decisions: verified priority commencement notices and supersession, spot-checked all 11 accepted OCR pages, and documented the release decision to share the registry and official links. Prepared the faculty request, independent English review packet and Member 3 retrieval adapter.
- Files / evidence: [source verification](../reports/member_1_source_verification_2026-11-22.md), [OCR worksheet](../reports/member_1_ocr_spotcheck.csv), [review guide](relevance_english_independent_review_guide.md), and [Phase 2 verification](../reports/phase_2_summary.md).
- Validation and results: checked the adapter against the actual corpus for a traceable passage and missing-evidence escalation. Local tests exercise mocked draft checks. Existing frozen gold and grounding hashes passed.
- Blockers / next action / owner: a human reviewer records OCR and blind relevance decisions. Faculty supplies written counting scope. Member 3 integrates the review adapter when the project graph gate is satisfied.

### 2026-11-22 — Evaluation: red-team v1 (adversarial checks)

- Owner: evaluation (prompting, baselines and safety testing), with an AI agent. Files arrive in the separate red-team PR.
- Work and decisions: built a 49-item attack catalogue and ran it offline against the input guardrail, the evidence injection filter and the API (FastAPI test client, temporary folder). Guardrail blocked 6/24 attacks with 3/7 false alarms; filter caught 3/8 tampered passages with 3/4 false flags; API passed 1/9 checks. High findings: identity is taken from the request body, and traces store personal data unmasked. Re-run on the 2026-11-22 main gave identical results; Devanagari questions are now stopped at the API by the English-only check.
- Files / evidence: [red-team report](../reports/redteam_v1_report.md), `reports/redteam/`, `evaluation/redteam_attacks_v0.1.jsonl`, `scripts/run_redteam.py`, `src/hr_navigator/evaluation/redteam.py`.
- Validation and results: `tests/test_redteam.py`; offline only, the agent was a stub and no live model was called.
- Blockers / next action / owner: API and guardrail owners fix the high findings and re-run the script; the real-corpus false-alarm count needs the local pages file; agent attacks run once an agent entry point exists.

### 2026-11-22 — Evaluation: baseline reconciliation, safety set, hold-out drafts

- Owner: evaluation (prompting, baselines and safety testing), with an AI agent.
- Work and decisions: reconciled the two baseline reviews under the strict rubric by team decision (official closed-book baseline 19/240; 226/240 marks agreed). Split the behaviour draft: an 18-case document-only safety set (refusal, document injection, out-of-scope, clarify) for the current system, with tool and approval cases kept as the agent draft. Extended the grounding hold-out candidates from 8 to 20. The evaluation runner accepts more than one acceptable decision and adds tampered test pages to RAG evidence for injection cases; Member 1's English-only check in `RagSystem` is kept.
- Files / evidence: [baseline report](../reports/baseline_v1_report.md), [reconciled review](../reports/baseline_v1_review_reconciled.csv), [safety set guide](safety_doc_set_guide.md), [hold-out review guide](holdout_review_guide.md), `src/hr_navigator/evaluation/runner.py`, `systems.py`, `safety_set.py`.
- Validation and results: offline tests with fake systems and a fake page registry only; no live model run on the safety or hold-out sets.
- Blockers / next action / owner: team members review the 18 safety cases and freeze them (`scripts/freeze_safety_set.py`); a member with the corpus checks the 20 hold-out questions against the PDF pages and freezes them (`scripts/freeze_holdout.py`). Live closed-book and RAG runs need the API keys.


---

### 2026-11-23 — Track 5 (UI, FastAPI, Guardrails & Observability)

- **Owner:** Track 5 (UI / FastAPI / Security / Observability)[cite: 2, 9]
- **Changes Made:**
  - Wired `src/hr_navigator/server.py` (`GET /health` and `POST /chat`) with rate limiting (`src/hr_navigator/security/guardrails.py`), query routing with safe fallbacks, and JSONL trace logging (`src/hr_navigator/observability/tracer.py`)[cite: 2, 9].
  - Updated `app.py` with sample demo prompts, employee ID input, response metadata (status, route, latency, citations), and the **Metrics & Traces** view reading `reports/agent_traces.jsonl` and existing JSON reports under `reports/`[cite: 2, 9].
  - Documented Track 5 components and local startup commands in `README.md`[cite: 9].
- **Demo & Handoff Notes:**
  - All requests (`ok`, `refused`, and `error`) log to `reports/agent_traces.jsonl` so live counts, latency, refusals, and estimated cost appear in the dashboard[cite: 2, 9].
  - Ready for coordinator demo walkthrough with FastAPI running on port `8000` and Streamlit running `app.py`.

### 2026-11-23 — FastAPI launch instructions

- Owner: AI agent.
- Work and decisions: provided local API setup and launch instructions.
- Files / evidence: README and `pyproject.toml`.
- Validation and results: checked the documented command and separately required API dependencies.
- Blockers / next action / owner: none.

### 2026-11-23 — Connect document retrieval to chat UI

- Owner: AI agent.
- Work and decisions: connected `/chat` to the local review adapter, enabled optional configured chat-model drafts, preserved review and escalation decisions, and displayed source passages and citations in the UI.
- Files / evidence: `src/hr_navigator/server.py`, `app.py`, `tests/test_server_language.py`, `README.md`.
- Validation and results: seven focused API/adapter tests passed; a real corpus query returned three sources; Streamlit AppTest displayed them without exceptions. The wider suite was interrupted after 79 passes when it stalled. Live model drafting was not tested because the authorized chat endpoint was not configured.
- Blockers / next action / owner: set all four CHAT environment variables using the assigned endpoint to generate drafts; human review and evaluation gates remain open.

### 2026-11-23 — API interpreter troubleshooting

- Owner: AI agent.
- Work and decisions: diagnosed the Python 3.14 Uvicorn launch missing httpx; made the launch instructions use the project Python 3.11 interpreter explicitly.
- Files / evidence: `README.md`; user's traceback.
- Validation and results: Python 3.11 imports httpx and Uvicorn and loads the API through application startup. The sandbox blocked binding a local port.
- Blockers / next action / owner: restart the server with the documented interpreter.

### 2026-11-23 — Local chat configuration

- Owner: AI agent.
- Work and decisions: added a Git-ignored local chat configuration using existing key and certificate files, retaining environment overrides; documented setup.
- Files / evidence: `src/hr_navigator/server.py`, `.gitignore`, `README.md`, `tests/test_server_language.py`, local ignored configuration.
- Validation and results: eight focused API/adapter tests passed, including local configuration and client cleanup. A live endpoint test was rejected by automatic approval review because it would send a local credential and document-derived request externally.
- Blockers / next action / owner: confirm authorization for the configured endpoint and live test; independently evaluate retrieval and generated drafts.

### 2026-11-23 — Draft failure diagnostics

- Owner: AI agent.
- Work and decisions: distinguished sanitized chat-service errors from draft validation failures so the API can report the cause without exposing response bodies or credentials.
- Files / evidence: `src/hr_navigator/retrieval/draft_review.py`, `tests/test_review_adapter.py`.
- Validation and results: nine focused review-adapter and server tests passed; no live external API request was made.
- Blockers / next action / owner: user retries to provide the sanitized error; the earlier live test remains blocked by automatic approval review pending explicit authorization.

### 2026-11-23 — Correct local chat endpoint pairing

- Owner: AI agent.
- Work and decisions: corrected the ignored local VM04 chat endpoint from port 1035 to port 1034, matching the supplied course guide's VM04 certificate and endpoint pairing.
- Files / evidence: local ignored `configs/chat.local.json`; supplied Track B inference guide.
- Validation and results: checked the guide's endpoint and certificate table; no external request was sent. User must retry to confirm connectivity and group authorization.
- Blockers / next action / owner: group assignment remains to be confirmed; live generation and retrieval quality remain unverified.

### 2026-11-23 — Document collection selection

- Owner: AI agent.
- Work and decisions: traced a citation escalation to weak all-document retrieval and added a document collection filter to the UI and API, retaining existing citation checks. Improved the citation failure message.
- Files / evidence: `app.py`, `src/hr_navigator/server.py`, `src/hr_navigator/retrieval/draft_review.py`, `tests/test_server_language.py`, `README.md`.
- Validation and results: 29 focused tests passed. With the Code on Wages filter, the real corpus retrieves its definition on PDF page 4; a simulated model passed the end-to-end draft and citation checks. A live model draft has not been verified.
- Blockers / next action / owner: select the intended Code; actual model reliability and independent evaluation remain open.

### 2026-11-23 — Verbatim statutory definition answers

- Owner: AI agent.
- Work and decisions: added a direct evidence result for simple inclusion questions when exactly one matching Act clause can be verified against its registered PDF page. The API displays the source wording as the answer without requesting a model citation.
- Files / evidence: `src/hr_navigator/retrieval/review_adapter.py`, `src/hr_navigator/server.py`, and `tests/test_review_adapter.py`.
- Validation and results: thirty focused tests passed. A real-corpus API smoke test returned Code on Wages PDF page 4 with and without the document filter, using a stub that fails if the model is called.
- Blockers / next action / owner: general questions still depend on retrieval and model citation quality.

### 2026-11-23 — Retrieve definitions from named Acts

- Owner: AI agent.
- Work and decisions: corrected the chat API's named-Code definition retrieval to start at the Act's definition heading and include nearby text for qualifications.
- Files / evidence: `src/hr_navigator/retrieval/review_adapter.py`, `src/hr_navigator/server.py`.
- Validation and results: real-corpus API smoke checks with a simulated model retrieved and cited the Code on Wages definition for both default and Code-filtered queries. Thirty focused checks passed.
- Blockers / next action / owner: live model output remains unverified.

### 2026-11-23 — Quote named statutory definitions directly

- Owner: AI agent.
- Work and decisions: added a direct source result for named-Code definition questions with a verified clause boundary. The result retains separate PDF citations for a definition that continues onto the next page.
- Files / evidence: `src/hr_navigator/retrieval/review_adapter.py`, `tests/test_review_adapter.py`.
- Validation and results: 31 focused tests passed. The real-corpus API returned Code on Wages PDF pages 4 and 5 for the reported question with and without the filter. The test client was configured to fail if it attempted a model call.
- Blockers / next action / owner: broader questions still depend on the general drafting flow.

### 2026-11-23 — Commit the document chat integration

- Owner: AI agent.
- Work and decisions: grouped draft failure diagnostics and the document chat integration into separate commits on the Track 5 branch.
- Files / evidence: API, Streamlit chat, review adapter, focused tests, README and this log.
- Validation and results: 31 focused tests passed, and the diff passed whitespace checks. Local model configuration, credentials and generated traces were excluded.
- Blockers / next action / owner: broader live model behavior remains unverified.

### 2026-11-23 — Make the chat input visible

- Owner: AI agent.
- Work and decisions: moved the Streamlit chat input above the conversation history in Assistant Demo.
- Files / evidence: `app.py`.
- Validation and results: Streamlit AppTest rendered the input, submitted a typed message to a mocked API, and displayed the reply.
- Blockers / next action / owner: none.

### 2026-11-23 — Retrieval interface handoff

- Owner: AI agent.
- Work and decisions: inspected the current retrieval, chat API and synthetic tool interfaces for a colleague handoff.
- Files / evidence: `src/hr_navigator/retrieval/review_adapter.py`, `src/hr_navigator/server.py`, `src/hr_navigator/tools/synthetic_hr.py`.
- Validation and results: checked function signatures, data models and routing directly against the source; no code behavior was changed.
- Blockers / next action / owner: live model behavior and independent evaluation remain unverified; orchestration and synthetic tool integration remain open.

### 2026-11-23 — Accept quoted terms in definition questions

- Owner: AI agent.
- Work and decisions: fixed named-Code definition lookup for terms surrounded by straight or curly quotation marks.
- Files / evidence: `src/hr_navigator/retrieval/review_adapter.py` and `tests/test_review_adapter.py`.
- Validation and results: 35 focused tests passed. Real-corpus API smoke checks returned the worker definition on PDF page 5 and the employee definition on PDF page 3 without a hosted model call.
- Blockers / next action / owner: none for the reported questions.

### 2026-11-23 — Improve the general document chat path

- Owner: AI agent.
- Work and decisions: reranked interactive search results locally, applied named-Code scope before ranking, and preserved context around the matching span. The hosted model now selects short passage IDs and the server attaches registered PDF text. Unsupported or invalid drafts escalate with candidate passages when available. The server audit now uses isolated fixtures for its model boundary.
- Files / evidence: interactive retrieval, draft review and API code, server audit, focused tests, and README.
- Validation and results: 137 tests passed and 2 skipped. Real-corpus API smoke checks retrieved the expected provision for five varied questions with a simulated chat model. The smoke checks also confirmed escalation for missing personal-record evidence.
- Blockers / next action / owner: hosted model behavior and independent retrieval accuracy are still unverified. Paraphrases and questions outside the corpus can still return insufficient evidence.

### 2026-11-23 — Dock the chat input and stream progress

- Owner: AI agent.
- Work and decisions: docked the composer at the viewport bottom in Assistant Demo. Added a streaming API route that emits retrieval, drafting and checking progress before the final checked response. The JSON chat route remains available.
- Files / evidence: `app.py`, `src/hr_navigator/server.py`, review adapter and draft code, and `tests/test_server_language.py`.
- Validation and results: 138 tests passed and 2 skipped. Streamlit AppTest confirmed the bottom container and displayed a response from a mocked stream. The API regression test verified event order and the checked result.
- Blockers / next action / owner: live hosted model streaming was not exercised.

### 2026-11-23 — Publish Track 5 chat updates

- Owner: AI agent.
- Work and decisions: prepared the general document retrieval, citation handling, and streaming chat updates for the existing Track 5 branch and PR 13.
- Files / evidence: API, Streamlit UI, retrieval and draft review, server audit, tests, README and this log.
- Validation and results: the latest full suite passed with 138 passed and 2 skipped. Checked the diff for whitespace and excluded the local model configuration, credentials and generated traces.
- Blockers / next action / owner: live hosted model behavior remains unverified.

### 2026-11-23 — Prepare manual chat test prompts

- Owner: AI agent.
- Work and decisions: provided prompts with expected statutory answers and cases that should request clarification or escalate.
- Files / evidence: official India Code texts for the Code on Wages and Industrial Relations Code.
- Validation and results: checked expected answers against the cited Act sections. The prompts were prepared for manual UI testing.
- Blockers / next action / owner: none.

### 2026-11-23 — Clarify personal minimum-wage questions

- Owner: AI agent.
- Work and decisions: added an API clarification before retrieval for requests for a personal minimum-wage rate. Streamlit carries the original question into the next reply and offers a way to start a new question.
- Files / evidence: `app.py`, `src/hr_navigator/server.py`, and `tests/test_server_language.py`.
- Validation and results: 139 tests passed and 2 skipped. A Streamlit-to-API smoke check verified the exact reported prompt, the follow-up data reaching the pipeline, and escalation when no rate schedule is available.
- Blockers / next action / owner: the app requires supporting corpus evidence to draft a rate. Hosted model output for a completed follow-up was not tested.

### 2026-11-23 — Explain the minimum-wage corpus limit

- Owner: AI agent.
- Work and decisions: checked the indexed source registry for rate schedules and made personal rate follow-ups explain the missing source and the distinction between payday and the affected wage period.
- Files / evidence: `src/hr_navigator/server.py`, `tests/test_server_language.py`, and the accepted OCR source metadata.
- Validation and results: 139 tests passed and 2 skipped. The reported two-turn scenario now returns an explicit missing-source result without generic Code citations or a model call.
- Blockers / next action / owner: exact-rate support requires verified rate notifications and a way to establish their applicability.

### 2026-11-23 — Correct drafts after a failed support check

- Owner: AI agent.
- Work and decisions: prioritized the named Act when a question does not ask for a separate instrument, and added one correction attempt after a failed support check. A corrected draft must pass the same checks.
- Files / evidence: `src/hr_navigator/retrieval/review_adapter.py`, `src/hr_navigator/retrieval/draft_review.py`, `tests/test_review_adapter.py`.
- Validation and results: 141 tests passed and 2 skipped. The real-corpus streaming API ranked Code on Wages PDF page 9 first for the six-week wage-period example and accepted a simulated correction. A second failed check still escalates.
- Blockers / next action / owner: live hosted model behavior remains unverified.

### 2026-11-23 — Handle incomplete drafts for multi-part prompts

- Owner: AI agent.
- Work and decisions: increased the interactive draft response budget, clarified how to cover each requested item, and added one format-recovery attempt for cut-off or malformed drafts. Citation and support checks still apply.
- Files / evidence: `src/hr_navigator/retrieval/draft_review.py` and `tests/test_review_adapter.py`.
- Validation and results: 143 tests passed and 2 skipped. The reported multi-part prompt recovered from a simulated truncation with real corpus passages. Repeated truncation still escalates.
- Blockers / next action / owner: the original provider response was not available to identify the exact format failure, and hosted behavior remains unverified.

### 2026-11-23 — Publish chat clarification and draft fixes

- Owner: AI agent.
- Work and decisions: grouped the minimum-wage clarification flow and draft recovery fixes into separate commits for the existing Track 5 PR.
- Files / evidence: Streamlit chat, API, retrieval and draft review, regression tests, and this log.
- Validation and results: 143 tests passed and 2 skipped. Checked the diff and excluded local credentials, model settings, and generated traces.
- Blockers / next action / owner: live hosted behavior remains unverified.
