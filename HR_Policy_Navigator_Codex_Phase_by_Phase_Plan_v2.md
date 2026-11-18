# HR Policy Navigator — Codex Master Implementation Plan (Track B)

**Use this file as the implementation contract for Codex.** Build incrementally. Do **not** implement every phase in a single run. For each phase, make the changes, run checks, write a short progress report, and stop for review. The five team members will work in parallel through clear module interfaces.

## 1. Project constraints and confirmed inputs

**Course:** upGrad Track B — API-side Multi-Agent Operations Copilot; four-week team capstone; team size **five** (the rubric template assumes six). Work only with the course-provided OpenAI-compatible **hosted ≤8B chat inference endpoint** and embedding endpoint. Do not fine-tune, switch to a frontier model, or deploy a second generative model to evade this restriction.

**From the uploaded Track B guidelines (pp. 4–5):**

- **Week 1:** written task/refusal specification; **60–100 realistic, gold-answer questions frozen before agent development**; compare **at least three prompting strategies** with a single-prompt / single-agent baseline.
- **Week 2:** RAG over **500–2,000 documents**; chunking experiments; **hybrid BM25 + dense** retrieval; reranking; citation-grounded answers; **retrieval recall@k** separately from response accuracy.
- **Week 3:** a **multi-agent or tool-using** system with **at least three tools**, explicit **planner → executor → critic**, cross-turn persistent state, and protections against malformed JSON, failed tools, infinite loops, and token-budget exhaustion.
- **Weeks 3–4:** measure end-to-end accuracy, completion rate, mean tool calls, token/cost and latency per query; trace runs through LangSmith, Langfuse or OpenTelemetry; distinguish retrieval misses, reasoning errors, tool-call errors, and hallucinations.
- **Week 4:** Streamlit/React UI, containerized deployment, rate limiting, caching, prompt-injection tests against the corpus, PII protection, refusal rules, and a human-in-the-loop boundary for consequential operations.
- **Submission:** Git repository, trace dashboard, evaluation report (with failure taxonomy), **12-page technical report** and **10-minute live demo**. Cap agent execution at **10 steps per query**. Discuss specifically how the small ≤8B model was made reliable.
- **Rubric:** technical depth 30%, consistent progress 25%, working deployment 20%, report and demo 25%.

**Verified from `Labour_Codes_Corpus(1).zip`:** 126 distinct downloadable PDFs; **1,767 PDF pages** total, of which **25 have fewer than 100 extractable characters**. All PDFs parsed in the initial audit. Folder groups and their page totals:

| Folder group | Pages |
|---|---:|
| Occupational Safety, Health and Working Conditions Code | 690 |
| Code on Social Security | 484 |
| Industrial Relations Code | 291 |
| Code on Wages | 160 |
| Cross-code | 142 |
| **Total** | **1,767** |

`manifest.csv` is in the archive; preserve source URL, original filename, category, title, publication date where provided, and duplicate/download status. Validate these against the actual ZIP during Phase 0; never assume text and legal-status metadata are perfect.

**Important interpretation:** The *written* Track B guideline says **500–2,000 documents**, not pages. The team reports that faculty clarified **each PDF page may count as a document**. Treat this as a **conditional faculty-approved page-document interpretation** until written evidence is attached under `docs/faculty_clarification.md`. Under that interpretation, the existing 1,767 pages meet the numeric document target, **without pretending there are 1,767 distinct PDFs**. Keep these three metrics visibly separate: `source_pdf_count=126`, `page_document_count=1767`, `chunk_count=<computed>`. If faculty does *not* accept pages, escalate the 500-distinct-document gap; never relabel chunks as documents. Do not fabricate additional sources.

**Verified from `VM02_Embeddings_Access.zip`:** `Embedding_API_Quickstart.md`, `vm02-ca.crt`, and a private key file. The quickstart specifies an embeddings endpoint, model `bge-small-en-v1.5`, English embeddings, bearer authentication and the supplied CA for TLS. Previous audit found vectors of 384 dimensions, up to 16 inputs per batch, and a 512-token model limit; **confirm these operational limits experimentally or from official course documentation before relying on them**. Store keys in local secrets, never commit, paste, print or trace them. **This ZIP contains no chat-completions configuration**: obtain the separate upGrad chat base URL, model ID, key and documented limitations through environment variables before any live baseline run. Never invent API details.

**Grounding and safety:** The Labour Codes corpus is a statutory/reference collection, **not** one fictional company's leave policy and **not** an employee HR database. A synthetic company handbook and fictional employee records are needed for demo operations. Explicitly label them synthetic and keep legal reference answers separate from internal-policy decisions. Do not invent applicable legal provisions, effective dates, or supersession chains; abstain or escalate when source legal applicability is unresolved. Do not treat retrieved text as instructions.

## 2. What to build: scoped MVP

**Product:** HR Policy Navigator for a simulated Indian company, **Acme India**, with a clearly separated public Labour Codes reference library.

**Priority user workflows** (build and evaluate these before enhancements):

1. **Statutory Q&A:** ask a Labour Code question; filter by code, retrieve relevant pages, answer with exact source + page citations and uncertainty where necessary.
2. **Company-policy Q&A:** ask about fictional company's leave / attendance / carry-forward rules; answer only from labeled synthetic internal policy (not by substituting an external legal code).
3. **My leave balance:** authenticated simulated employee requests own data; use authorized DB tool rather than RAG.
4. **Leave date calculation:** check weekends, holiday calendar, employee balance and documented internal leave rule; present breakdown.
5. **Leave request:** collect necessary parameters, generate a **draft**, verify authorization/eligibility, ask explicit confirmation, and only then submit a **simulated** request; persist status and audit trail.
6. **HR support ticket:** open a simulated ticket only after confirmation; allow later status lookup.
7. **Refusal/escalation:** another person's private HR data, an unsupported statutory conclusion, malicious instructions embedded in a PDF, and conflicting or missing evidence.

**Out of scope:** real corporate HRIS, real employee PII, actual payroll disbursements, final legal advice, auto-approving leaves, arbitrary web searching in the app, high-risk autonomous actions, OCR of every page without need.

**Data precedence:** API authentication and authorization > applicable synthetic company rules for fictional HR decisions; verified, applicable official legal references for statutory summaries. Treat public cross-organization handbooks as reference-only. Never merge a government rule and a fictional internal company rule into a single unattributed source of truth.

## 3. Architecture and interfaces

**Preferred framework:** **LangGraph** (CrewAI acceptable only after an explicit team decision, but do not build both). Use a single permitted hosted ≤8B model for every reasoning-agent role, with different prompts and constrained schemas.

Five genuine specialized agent nodes:

- **Supervisor / Planning Agent:** intent classification, jurisdiction/source routing, plan and next tool selection; produces JSON validated by Pydantic.
- **Policy Research Agent:** page-level RAG, filtered hybrid search, reranking, version/citation checks and evidence packaging.
- **HR Operations Agent:** orchestrates deterministic tools and employee-specific state, with no unrestricted SQL or direct side effects from LLM output.
- **Compliance / Critic Agent:** verifies evidence, numerical correctness, confidentiality, prompt injection, refusal and approval requirements; issues `pass`, `revise`, `clarify`, `refuse`, or `escalate` with bounded feedback.
- **Response Agent:** writes final grounded user response; may not add unsupported claims or citations.

**Graph sketch:** `START → security/input gate → supervisor → (policy research | HR operations | both | clarification/refusal) → evidence assembly → critic → (response | bounded replan | approval interrupt | escalation) → END`. A deterministic tool executor is **not** another unconstrained LLM agent. Map planner/executor/critic roles visibly in traces. Limit workflow to **10 steps/query** (count and define what constitutes a step), max 1–2 critic retries, and bounded context/token expenditure. Hard-stop with an honest failure response when exceeded.

Minimum tools, typed and independently unit-tested:

- `search_policy(query, source_scope, labour_code, date_filter, top_k)` → ranked page/chunk citations.
- `get_employee_profile(auth_context)` → only own profile.
- `get_leave_balance(auth_context, leave_type)` → only own data.
- `get_holidays(state, year)` → deterministic calendar.
- `calculate_leave_days(start, end, workweek, holidays, policy_version)` → deterministic result.
- `draft_leave_request(...)`, `submit_leave_request(draft_id, approval_token)` → confirmation-gated, idempotent writes.
- `create_hr_ticket(..., approval_token)` and `get_request_status(...)` → simulation only.

**Persistent LangGraph state:** session ID, server-derived simulated identity, source scope, intent, versioned plan, tools requested/results, evidence IDs, page citations, pending clarification, pending human approval, approval nonce/expiry, tool attempts, critic feedback, accumulated steps/tokens, trace ID. Persist state with SQLite-backed checkpointer suitable for the assignment. Never trust an employee ID supplied inside a prompt as identity.

**Final response JSON contract:** `decision`, `answer`, `sources[{source_pdf_id, original_title, page_number, source_url, quote_or_section, scope}]`, `calculations`, `tool_actions`, `uncertainty`, `approval_required`, `trace_id`. Every source link must map to a real indexed page; no fabricated citations or policy details.

**Technical stack:** Python 3.11+, FastAPI, LangGraph, Streamlit, SQLite, PyMuPDF, BM25, FAISS or Chroma, Pydantic, pytest, Docker Compose, Langfuse/OpenTelemetry or LangSmith subject to available deployment, and an explicitly measured reranking step. Prefer simple, reproducible pieces over unnecessary microservices. Avoid additional hosted generative endpoints.

## 4. Repository layout

```text
hr-policy-navigator/
  README.md
  pyproject.toml
  .env.example
  .gitignore
  docker-compose.yml
  inputs/                     # ignored local ZIPs and course PDF
  data/
    raw/                     # ignored original source PDFs
    processed/               # page JSONL and chunks
    indexes/                 # ignored embeddings/BM25 index
    synthetic/               # clearly marked sample company rules/employee data
  configs/
  src/hr_navigator/
    clients/                 # upGrad chat + embeddings adapters
    ingestion/               # manifest audit, extraction, OCR flags, chunking
    retrieval/               # BM25, dense, fusion, rerank, citations
    agents/                  # five specialized agent prompts/nodes
    orchestration/           # graph, state, budgets, checkpoints
    tools/                   # employee, leave, holiday, ticket tools
    security/                # authorization, approval, sanitization
    evaluation/              # baseline, retrieval, end-to-end, adversarial
    observability/
  apps/api/
  apps/ui/
  scripts/
  tests/
  evaluation/               # frozen, versioned gold set + scenarios
  reports/                  # audit, baseline, retrieval, agent comparisons
  docs/                     # spec, decisions, weekly notes, report, demo
```

**No real secret in version control**: ignore `inputs/`, private key and CA locations if local, `.env`, vector indexes and personal/test SQLite DBs. `.env.example` should have placeholders only. Check third-party corpus redistribution permissions before sharing the entire ZIP or repository.

## 5. Sequential phase gates and Codex instructions

### Phase 0 — Input audit, API adapters and skeleton (Days 1–2)

**Codex tasks:**
1. Inspect `inputs/Labour_Codes_Corpus(1).zip`, its manifest, and `inputs/VM02_Embeddings_Access.zip` locally without printing credentials; inspect course PDF for the detailed Track B contract.
2. Create package structure, pinned dependencies, README, `.gitignore`, `.env.example`, Makefile, test configuration and Docker skeleton.
3. Write a **safe ZIP importer** (path traversal and archive size checks) and immutable source registry with original source URLs, category, filename and SHA256.
4. Audit every PDF: page count, extraction character count/page, corrupt pages, language heuristics, sparse/scanned flags, duplicates; output `reports/corpus_inventory.csv` and `reports/corpus_audit.md`. Must reproduce **126 PDFs / 1,767 pages** or explain differences; flag **25 low-text pages**.
5. Build chat and embedding client **adapters** with local environment configuration, TLS CA verification, retry/backoff, timeout, usage accounting and mockable interfaces. Probe endpoint health only when credentials exist. Do not disable TLS verification or hard-code API host secrets.
6. Build minimal SQLite schema + synthetic database seeds; validate migrations in tests.

**Exit criteria:** unit tests and lint pass; inventory counts and metadata verified; no key leaked; absent chat API produces a clearly reported blocker, not a made-up success. **Stop before graph implementation**.

### Phase 1 — Specification, dataset and three prompt baselines (Week 1)

**Codex tasks:**
1. Write `docs/product_spec.md` with intents, refusals, source hierarchy, hallucination and legal-uncertainty policy, success metrics, tool contracts, and human approval boundaries.
2. Prepare a **short, versioned, explicitly fictional Acme India handbook**, with machine-readable leave / holiday / carry-forward rules, plus simulated employees and balances. Cite internal synthetic policy version when making calculations.
3. Author **80 realistic gold cases** before building agents: suggested mix: 25 official-law Q&A, 15 company-policy Q&A, 15 calculations/tool questions, 10 multi-turn actions, 10 privacy/refusal cases, 5 injection/failure cases. For each include `question`, `scope`, gold response/conditions, supported source PDF/page or synthetic policy section, required/forbidden tool actions, expected decision, and scoring method. Have humans review. Freeze as `evaluation/gold_v1.jsonl` with checksum and date; no test-set tuning after freeze.
4. Run the **single-agent, single-prompt** hosted ≤8B baseline comparing at least **three** prompt strategies: (a) zero-shot structured response, (b) few-shot structured response, (c) decomposition then concise answer/self-check without requesting private chain-of-thought. Consistent question set and decoding settings; save redacted runs, schema validity, correctness, refusal correctness, latency and token usage.
5. Capture 5–10 illustrative failure examples and explicitly characterize the ≤8B model's weaknesses.

**Exit criteria:** gold evaluation set frozen; three baseline runs measured **on the actual permitted chat endpoint**, or the stage is blocked until valid endpoint details arrive; documented human review. **No agent graph before this gate**.

### Phase 2 — Page-level ingestion and evidence-grounded hybrid RAG (Week 2)

**Codex tasks:**
1. Treat each original PDF as a **parent source** and each page as one **logical page-document** with stable IDs (`sha256:page_0001` or similar). Preserve: parent ID, original filename, official source URL, category, labour code, source title, PDF page index vs displayed printed page (when identifiable), language, extraction status and dates **only when validated**.
2. Process **1,767 page documents** from **126 sources**, excluding no page silently. Mark sparse/scanned pages, attempt targeted OCR only where necessary; keep failures visible in audit. Evaluate English coverage because `bge-small-en-v1.5` is English-oriented. For Hindi or bilingual content, keep raw text and report separately; do not claim embeddings work equally well without evidence. Respect a 2,000 logical page-document ceiling; any added synthetic pages must be counted and scoped separately.
3. Chunk *within* pages for experimentation (e.g. 200/350 tokens, overlap and heading-aware), allowing sensible table continuity without losing original page traceability. Each page remains **one logical document** irrespective of chunk count. Record source PDFs, page-documents, and chunks as separate counts. Chunk count can exceed 2,000, but flag this and check faculty interpretation of the cap.
4. Build dense embeddings using the course-provided English embedding API; validate dimension and batch/token constraints; use verified TLS, retries, throttling, caching and incremental reindexing. Build local **BM25** index.
5. Implement metadata-filtered retrieval, reciprocal-rank fusion, deduplication, and reranking. Candidate reranker must respect course model restrictions; test a lightweight local ranking approach if additional model access is disallowed. Never substitute an unapproved frontier service.
6. Compare BM25-only, dense-only, hybrid and hybrid+rerank. Use an independently annotated query-to-page relevance subset and report recall@3, recall@5, recall@10, MRR and latency. Compare at least two chunking setups.
7. Construct a citation validator guaranteeing every emitted PDF/page/URL exists in the registry. Ensure source scope is enforced (company policy vs statutory reference), and document/version conflicts are visible.

**Exit criteria:** reproducible page registry (1,767 pages), reliable indexes, testable hybrid+rerank retrieval, per-page citations, recall@k report and extraction-quality audit. Record faculty page-count clarification in docs; **never represent 1,767 pages as 1,767 distinct PDFs**.

### Phase 3 — LangGraph multi-agent orchestration and HR tools (Week 3)

**Codex tasks:**
1. Implement **Supervisor, Policy Research, HR Operations, Compliance/Critic and Response** as separate testable nodes with distinct prompts, typed input/output contracts and graph traces. Use **only the permitted ≤8B chat model** for reasoning nodes.
2. Add deterministic tool adapters: scoped employee lookup, balance lookup, holidays, leave calculator, policy search, draft leave request, confirmation-gated submission and ticket handling. Validate Pydantic schemas on both planner output and tool calls; sanitize and retry bounded malformed JSON safely.
3. Implement routing for statutory questions, company HR questions, mixed evidence+tool questions, clarification, refusal and escalation. Demonstrate the **planner → executor → critic** feedback loop; guard against infinite loops (≤10 graph/action steps/query) and max token budget.
4. Persist sessions and approval interruptions using SQLite checkpointer. Add bounded retries and timeouts. Implement idempotency and prevention of duplicate submissions, plus role-aware employee-data access.
5. Create a visible three-turn demo: 'What is the leave policy?' → 'How much leave do I have?' → 'Draft leave next week' → approve or cancel. Note: only synthetic company policy and employee data determine company leave entitlement.
6. Add unit and integration tests for unauthorized access, insufficient balance, overlapping requests, invalid dates, missing policy, failed tool, malformed JSON, malicious PDF instructions and loop budget exhaustion.

**Exit criteria:** genuine graph with five specialist nodes, ≥3 working tools, traceable decisions, persistent state, human-in-the-loop interrupt, safe refusal and bounded retry/replan; mock and live API smoke tests pass.

### Phase 4 — Evaluation, observability and safety (Late Week 3 – Week 4)

**Codex tasks:**
1. Evaluate **three comparable systems** using the frozen cases: simple LLM baseline, single-agent RAG baseline, and multi-agent LangGraph workflow. Use identical source permissions and evaluation slices where applicable; distinguish questions that require tools from policy-only questions.
2. Measure: grounded answer accuracy; schema validity; tool selection and execution success; end-to-end task completion; citation correctness; policy scope leakage; retrieval recall@k; p50/p95 latency; model tokens/request; estimated cost (only where rate is known); mean tool calls and steps/query.
3. Label each failed case with primary cause: **retrieval miss, reasoning error, tool-call error, hallucination**, plus optional safety/permission/format category. Include examples and mitigation, not just a single composite score.
4. Add Langfuse/LangSmith/OpenTelemetry tracing to show route, node latency, tool calls, validation failures and retry counts. **Redact PII, raw keys, tokens and sensitive record payloads** in traces. Keep local trace fallback if hosted service not available.
5. Run injection/red-team suite on adversarial content embedded in a retrieved page/chunk, another employee's data request, requests to falsify approvals, contradictions between policies, absent citations, and failed APIs. Enforce human review for requests and refuse unauthorized operations.
6. Perform an ablation (e.g. hybrid retrieval vs dense only, reranker on/off, critic on/off) so the report demonstrates *why* your design helps a ≤8B model rather than merely showing a fancy UI.

**Exit criteria:** reproducible evaluation report, honest pass/fail metrics, failure taxonomy, saved traces and safety log; no artificial scores or fabricated model cost.

### Phase 5 — Deployment, reporting and demo (Week 4)

**Codex tasks:**
1. Create Streamlit UI: chat, source PDF/page references, synthetic employee login selector (clearly demo-only), tool action previews, explicit approve/cancel, saved ticket/request history and readable error messages.
2. Expose FastAPI app; add health endpoints, input and request limits, rate limiting, caching for embeddings/retrieval and safe logs. Containerize app services with Docker Compose; indexes persist via volume. Document TLS CA setup in containers.
3. Ensure one-command repeatable local setup (excluding user-supplied credentials), sample `.env.example`, dataset audit instructions, dependency licenses and README architecture diagram.
4. Produce `docs/technical_report.md` drafted to **12-page** target: problem and scope, source provenance, baseline and three prompts, corpus/page interpretation, RAG experiments, graph/agents/tools, evaluation, failures, ethics/PII, latency/cost, lessons and limitations.
5. Write `docs/demo_script.md` for **10 minutes**: introduction (1m), source-grounded policy Q&A (2m), multi-tool leave case (3m), approval/refusal and failure handling (2m), trace + measured improvements (2m). Include an offline replay fallback only if clearly labeled as replay, not as a live success.
6. Final CI smoke tests, docs consistency review, screenshots/trace captures, team presentation rehearsal.

**Exit criteria:** Docker app runs from README with user-supplied endpoints; five-agent flow visible; final Git repository, trace dashboard, evaluation report, 12-page report and 10-minute demo ready.

## 6. Five-member ownership and integration

| Member | Main ownership | Key outputs |
|---|---|---|
| **1 — Domain/data** | corpus import, page registry, legal/synthetic source separation, evaluation ground truth | manifests, audit, 80 gold cases, provenance |
| **2 — RAG** | extraction/targeted OCR, chunking, BM25, embeddings, reranker, citation validation | retrieval pipeline, recall@k experiments |
| **3 — Orchestration** | LangGraph supervisor, policy researcher, critic, response, typed state | graph, budget/retry logic, tests |
| **4 — HR tools/security** | SQLite, auth scope, leave engine, holidays, draft/approval and tickets | tool APIs, approval workflow, PII tests |
| **5 — Integration/deployment/eval** | FastAPI, Streamlit, trace stack, CI, Docker, end-to-end measurement | deployed app, evaluation comparisons, report/demo coordination |

**Shared duties:** All members contribute to Week 1 gold-case review, API characterization, tests, weekly demonstrations and final report. No one should own the entire reporting process alone. Agree on interface and JSON schemas on Day 1; use small PRs, code reviews and a shared issue board. Resolve version and dependency conflicts early.

## 7. Mandatory tests and milestone scoreboard

- [ ] 126 original PDF sources registered; 1,767 pages counted; 25 low-text pages explicitly flagged or reprocessed.
- [ ] Faculty page-as-document clarification attached or labeled pending; source / page / chunk counts separately reported.
- [ ] API keys private; embedding endpoint verified with supplied CA; chat endpoint validated independently.
- [ ] 60–100 gold queries created and **frozen before agent graph coding**; three prompt strategies measured.
- [ ] BM25, dense, hybrid and reranking implemented; ≥2 chunk strategies compared; recall@k measured separately.
- [ ] Five specialized agents, ≥3 tools and explicit planner→executor→critic loop, with ≤10 steps/query.
- [ ] Durable multi-turn state, tool failure/invalid JSON handling, maximum attempts and token budget.
- [ ] Employee authorization, refusal, prompt-injection tests, explicit human approval, idempotent writes.
- [ ] Baseline vs RAG vs multi-agent comparison with completion, latency, tool-call frequency, accuracy and failure taxonomy.
- [ ] Traces, Docker deployment, rate limits, caching, source citations, 12-page report and 10-minute demo.

**Blocking dependencies to log, not hide:** (a) chat-completions endpoint and key not in embeddings ZIP; (b) written faculty approval of page-level document counting, unless already available; (c) legal applicability/effective dates not necessarily captured by each PDF; (d) sparse/scanned pages and Hindi content requiring separate treatment; (e) source-file redistribution rights.

## 8. Copy-paste prompts to give Codex

### First prompt — start the project (do Phase 0 only)

> Read `HR_Policy_Navigator_Codex_Phase_by_Phase_Plan_v2.md` and the supplied Track B capstone PDF. We are a five-person team building a LangGraph multi-agent HR Policy Navigator, strictly against the course-supplied hosted ≤8B chat model and embeddings API. The Labour Codes ZIP has been audited as 126 original PDFs / 1,767 pages / 25 sparse pages. The faculty's reported page-level-document interpretation is **conditional until documented**. Treat source PDFs, page documents and chunks as three distinct counts. Start **Phase 0 only**. Audit input ZIPs safely without revealing credentials; scaffold the repo, adapters, corpus inventory, validation scripts, tests and safe configuration. Run tests, report actual results and blockers. Do not begin Phase 1 or generate speculative policy facts. Stop for my approval after Phase 0.

### Next-phase prompt (use with phase number)

> Read the master plan and the previous phase report. Implement **Phase [N] only**, preserving interfaces and passing existing tests. Before writing code, list the phase deliverables and acceptance criteria. After implementation, run tests, save a short `reports/phase_[N]_summary.md` with completed features, commands run, measured outcomes, API usage, risks, and unresolved issues. Do not silently skip any course requirements or proceed to the following phase.

### Final audit prompt

> Audit the repository against every Track B requirement in the plan, the course PDF and the frozen evaluation rubric. Inspect actual code and run tests rather than trusting README claims. Report a pass/partial/fail matrix with evidence paths; distinguish 126 PDFs from 1,767 page documents and the number of retrieval chunks; verify truthful performance tables and saved traces; identify every unsupported claim, sensitive-data exposure and missing deliverable. Make only targeted fixes and rerun tests; do not manufacture results.

---

**Design principle:** A credible, independently evaluated **five-agent application** with a real 1,767-page reference corpus and carefully separated fictional HR tools is better than a broad, legally unreliable chatbot. Keep the working system small, citations verifiable, and comparisons measurable.
