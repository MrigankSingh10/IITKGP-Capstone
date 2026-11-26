# HR Policy Navigator

An IIT Kharagpur Track B capstone prototype for finding and citing information in Indian Labour Codes documents. The current document-focused scope answers questions about the supplied PDFs without needing employee details or external HR actions. The repository also contains a separate fictional Acme handbook and early UI/API scaffolding; these do not establish real employee entitlements.

The retrieval workflow is experimental. Generated answers are drafts for review, and citation checks do not establish legal applicability or guarantee correctness. The FastAPI and Streamlit prototype uses the local document review adapter; it is not connected to a LangGraph agent.

## Team handoff and shared log

All members and AI agents: read and update the [shared team work log](docs/team_work_log.md) each session. It contains the Member 1/2 handoff, current ownership, decisions, validation and next actions.

## What is implemented

### Corpus, OCR and provenance

- Audited **126 original source PDFs** comprising **1,767 PDF pages**. Each page record retains the source PDF ID, title, original page number, URL and extraction information. Source-document, page-document and retrieval-chunk counts are distinct.
- Identified 25 pages with sparse native text. Eleven user-accepted OCR transcriptions are included in a separate indexed corpus with source warnings; 14 pages remain sparse or low-content, including two that appeared blank. Original PDF pages remain the source of truth.
- The accepted-OCR corpus contains **9,615 chunks** with the 200-token configuration and **5,605 chunks** with the 350-token configuration. These are two alternative indexes, not additional source documents.
- Document-status notes for the five sources used in the fresh evaluation are in [`reports/evaluation_document_status_2026-11-20.md`](reports/evaluation_document_status_2026-11-20.md). They do not establish the current status of every provision or document.

### Search and grounded drafts

- Page-contained chunks support BM25 keyword search, dense search using the hosted BGE embeddings API, hybrid rank fusion and lexical reranking. FAISS is used for vector search; a local SQLite cache stores embeddings.
- Search results include original PDF/page provenance. The review-only drafting workflow checks quote existence and applies source, subsection and selected wording checks; uncertain results escalate. Model support and alignment checks can still be wrong, so successful drafts remain labelled `review_required`.
- Dense indexing was built for text heuristically classified as Latin script; multilingual coverage has not been validated. Source dates and legal applicability remain incompletely verified.

### Evaluation

- [`evaluation/gold_v1.jsonl`](evaluation/gold_v1.jsonl) contains 80 frozen document-only questions. Three closed-book prompting strategies generated 240 saved baseline responses.
- The two reviews of those responses ([`baseline_v1_review.csv`](reports/baseline_v1_review.csv), strict; [`baseline_v1_review_team.csv`](reports/baseline_v1_review_team.csv), team) were reconciled under the strict rubric by team decision. The official closed-book baseline is **19/240 (7.9%)** in [`baseline_v1_review_reconciled.csv`](reports/baseline_v1_review_reconciled.csv); the reviews agreed on 226 of 240 marks (94.2%). Both original sheets are kept for traceability.
- A separate 20-question grounding set was used to develop and test the retrieval checks. The recorded regression runs are **development results**, not independent accuracy estimates. The latest full run preceded two later targeted fixes; see [`reports/grounding_v3_regression.md`](reports/grounding_v3_regression.md).
- Grounding hold-out: 20 questions (eight from [`grounding_holdout_candidates_v0.1.jsonl`](evaluation/grounding_holdout_candidates_v0.1.jsonl) plus twelve more) were reviewed against the corpus page text and frozen as [`grounding_holdout_v1.jsonl`](evaluation/grounding_holdout_v1.jsonl) on 2026-11-24. It has not been evaluated; it is reserved for one final measurement (see [`docs/holdout_review_guide.md`](docs/holdout_review_guide.md)).
- The behaviour scenarios were split: an 18-case document-only safety set, reviewed and frozen as [`safety_doc_v1.jsonl`](evaluation/safety_doc_v1.jsonl) on 2026-11-23 (see [`docs/safety_doc_set_guide.md`](docs/safety_doc_set_guide.md)) and the tool/approval cases kept as an agent draft until the agent exists.

### API and interface prototype

The repository includes a FastAPI service (`src/hr_navigator/server.py`), a Streamlit interface (`app.py`), basic input checks, rate limiting and trace logging. The service searches the accepted-OCR statutory corpus and can produce an unverified review draft when a chat model is configured. LangGraph, durable workflow state and real HR integrations are not implemented.

The prototype UI currently displays an employee-ID field and the API logs queries and the supplied ID to `reports/agent_traces.jsonl`. For the agreed document-only scope, use fictional test values and do not enter employee details. Trace files may contain what was entered and should not be shared or committed as project data.

## Repository layout

| Path | Contents |
| --- | --- |
| `src/hr_navigator/ingestion/` | Corpus audit and page extraction |
| `src/hr_navigator/retrieval/` | Embeddings, search, citation checks and review-only drafts |
| `src/hr_navigator/clients/` | Hosted model and embedding API adapters |
| `src/hr_navigator/server.py`, `app.py` | FastAPI and Streamlit prototypes |
| `scripts/` | Corpus, indexing, search and evaluation commands |
| `evaluation/` | Frozen questions, draft candidates and review worksheets |
| `reports/` | Corpus audit, evaluation results and review notes |
| `docs/` | Product specification and review guides |
| `data/synthetic/` | Fictional handbook data |

## Setup and tests

Python 3.11 or newer is required. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
make test
make lint
```

For OCR tooling, install `pip install -e '.[ocr]'`. The current package metadata does not include the UI/API packages; to run that prototype, separately install `fastapi`, `uvicorn`, `streamlit`, `pandas` and `requests` in the environment.

At the last recorded merge check, **58 tests passed and one was skipped** because the scenario set was not frozen. The current local test result may differ as the project changes.

## Build the corpus and search

The input corpus ZIP, raw PDFs, credentials, certificates, generated pages and embedding caches are local files excluded from version control. Obtain the supplied files separately, place the corpus ZIP in `inputs/`, then run:

```bash
python scripts/audit_corpus.py 'inputs/<corpus-archive>.zip'
python scripts/build_pages.py
```

Replace the placeholder with the real ZIP filename. The audit stores PDFs by SHA256 and records source metadata; inspect extraction and manifest errors before use. Generated files are written under `data/processed/`.

To search the original extracted corpus locally with BM25:

```bash
python scripts/search_corpus.py \
  'Does State include a Union territory?' \
  --mode bm25 --code 'Code on Wages' \
  --data-dir data/processed
```

Search defaults to the separately built accepted-OCR corpus at `data/processed/accepted_ocr/`. To build its embedding cache and index, use the course-provided key and CA files and set the authorized endpoint locally:

```bash
export EMBEDDING_BASE_URL='<authorized-embedding-base-url>'
python scripts/build_embeddings.py \
  --key-file VM02_Embeddings_Access/shared-embedding-key.txt \
  --ca-file VM02_Embeddings_Access/vm02-ca.crt \
  --base-url "$EMBEDDING_BASE_URL" --model bge-small-en-v1.5
python scripts/apply_reviewed_ocr.py
python scripts/build_ocr_candidate.py
python scripts/embed_ocr_candidate.py \
  --key-file VM02_Embeddings_Access/shared-embedding-key.txt \
  --ca-file VM02_Embeddings_Access/vm02-ca.crt \
  --base-url "$EMBEDDING_BASE_URL" --model bge-small-en-v1.5
python scripts/build_accepted_ocr_index.py
```

Run `python scripts/search_corpus.py --help` for dense and hybrid options. Those modes require the embedding API configuration; BM25 does not. Run `python scripts/ask_documents.py --help` for the experimental question workflow. Its `--draft-for-review` option needs both hosted APIs and returns a draft or escalation, not a verified final answer. `scripts/review_evidence.py` can display source excerpts for review.

Keep API keys and certificates local, use the appropriate credentials for each service and retain TLS verification. `.env.example` documents configuration names; the application does not automatically load `.env`.

## Run the UI/API prototype

Build the accepted-OCR corpus as described above, then install the UI/API packages into the same environment used by the project:

```bash
.venv/bin/python -m pip install fastapi uvicorn streamlit pandas requests
```

For generated answers, copy the tracked [chat configuration example](configs/chat.example.json) to your local configuration:

```bash
cp -n configs/chat.example.json configs/chat.local.json
```

Edit `configs/chat.local.json` with the endpoint and CA certificate assigned to your group and the path to your key file. Git ignores the local configuration, key, and certificate.

Paths are relative to the repository root. Alternatively, all four `CHAT_*` environment variables in `.env.example` can be set in the API process; they take precedence over the local file. The application does not load `.env` automatically.

Start the API, then start the UI in a second terminal from the repository root:

```bash
PYTHONPATH=src .venv/bin/python -m uvicorn hr_navigator.server:app --reload --host 127.0.0.1 --port 8000
```

```bash
.venv/bin/python -m streamlit run app.py
```

Without chat settings, the UI displays candidate passages for review. With them, the chat model selects passages by ID and the server attaches the registered source text. The UI shows a draft only when support and question alignment checks pass. If a draft cannot be verified, the app can still show candidate passages for manual review. The corpus covers statutory documents. It does not have personal leave records or an employer handbook. Use fictional queries. The API masks common identifiers before sending a question to the configured hosted model and before recording it in local traces.

Name the Code in your question or select a **Document collection** to narrow the search. Plain keyword search can miss paraphrases or relevant text outside the indexed corpus.

**Trace dashboard:** set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` to also send each chat trace to Langfuse, then run `python scripts/trace_dashboard.py --send-test` to get the dashboard link. See [`docs/trace_dashboard.md`](docs/trace_dashboard.md).

## Remaining work

- The safety set and the grounding hold-out are frozen. Run the safety set against RAG and the chat API, and run the hold-out once, after the pipeline is fixed.
- Improve and evaluate retrieval, source matching and grounded answers on questions not used to tune the workflow. Keep generated answers review-only until the evaluation supports a change.
- Continue source-date, version, legal-status, sparse-page and redistribution checks. The user reported faculty acceptance of page counting; written confirmation and its scope are not attached.
- Align the API/UI with the document-only scope, address trace handling and connect the retrieval workflow. Implement LangGraph and document-focused task completion in a later phase.

### Current language scope

The active document workflow supports English questions and English evidence. Passage filtering excludes Devanagari-containing and sparse chunks; it preserves eligible English chunks even on bilingual PDFs. This is a script heuristic, not a language guarantee: mixed-script English can be missed, and Romanized Hindi, other Latin-script languages and legacy-font text can pass. The document CLIs ask for English when input contains Devanagari. Historical sources and frozen evaluations are preserved. The offline `scripts/evaluate_relevance_english.py` reports the English-labeled subset of the assistant-reviewed pilot.
