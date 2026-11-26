# HR Policy Navigator

**IIT Kharagpur capstone project · Track B**

HR Policy Navigator is a prototype for finding evidence in Indian Labour Codes documents and producing cited drafts for human review. It combines a searchable PDF corpus, a FastAPI backend, a Streamlit interface, safety checks and a local trace dashboard. A separate demonstration uses fictional employee records to show a read-only leave-balance lookup.


## Problem and approach

Finding the relevant provision in a large collection of labour documents can be slow, and an unsupported generated answer can mislead users. This prototype retrieves passages with source and PDF-page provenance, then optionally generates a draft from selected evidence. Citation and support checks can reject a draft or escalate it for review. They do not establish legal correctness or current applicability.

The indexed corpus audit covers **126 source PDFs**, **1,767 PDF pages**, and **9,615 page-contained chunks** in the accepted-OCR 200-token configuration (or 5,605 in the alternative 350-token configuration). Eleven reviewed OCR transcriptions are included with warnings; original scans remain the source of truth. The active document workflow supports English questions and evidence, with script-based filtering limitations.

### Workflow

1. The user submits a question through Streamlit; the API applies input checks and routes it.
2. For document questions, the retrieval workflow searches indexed passages and retains source identity, page number and extraction warnings.
3. When a chat model is configured, the workflow can produce a cited draft and run citation, support and alignment checks. Uncertain cases escalate; accepted drafts still require human review. Without chat configuration, candidate passages can be shown for review.
4. Explicit personal leave-balance questions can instead use a locally seeded, fictional Acme employee database. This is a separate demo and does not establish real entitlements.
5. Request metadata is written to a local JSONL trace and displayed in **Evaluation & Telemetry**, alongside saved evaluation summaries.

The UI/API does not provide real employee authentication or a real HR integration. The repository contains additional workflow and tool code; the document chat path is not a LangGraph agent. See [product specification](docs/product_spec.md) and [phase reports](reports/phase_3_summary.md) for design goals and historical implementation status.

## Evaluation status

- The frozen [gold set](evaluation/gold_v1.jsonl) contains 80 document-only questions. The reconciled closed-book baseline was 19 correct out of 240 responses (7.9%); see the [baseline report](reports/baseline_v1_report.md).
- The separate 20-question grounding set was used for development, not an independent accuracy estimate; see [grounding regression results](reports/grounding_v3_regression.md).
- The [20-question grounding hold-out](evaluation/grounding_holdout_v1.jsonl) is frozen and reserved for one final measurement. The 18-case [document safety set](evaluation/safety_doc_v1.jsonl) is also frozen; see the [evaluation guide](docs/evaluation_runner_guide.md).

## Responsible AI and model card

| Topic | Project position |
| --- | --- |
| Intended use | Help a human locate evidence and review draft responses against the supplied documents; demonstrate synthetic leave-balance lookup. |
| Out of scope | Autonomous legal advice, verified current-law determinations, real HR decisions or processing real employee information. |
| Model and data | Hosted model and embedding endpoints are configured separately. The source corpus comprises supplied labour-document PDFs and accepted OCR; the leave demo uses fictional fixtures. No model training is claimed. |
| Adversarial tests | Offline red-team tests cover prompt attacks, evidence injection and API checks. [Findings and limitations](reports/redteam_v1_report.md); re-test the current system before making safety claims. |
| Human oversight | Check the original source and page, applicable dates and jurisdiction, and the full context before relying on a draft. |
| Privacy | Local traces can contain queries and identifiers. Pattern-based masking is incomplete; use fictional data and do not publish trace files containing sensitive information. |

## Run locally

### Prerequisites

- Python 3.11 or newer and the source corpus ZIP, which is excluded from Git and must be obtained separately.
- Optional hosted chat and embedding services for generated drafts and dense/hybrid retrieval. Keep credentials and certificates local.
- The Streamlit interface, Uvicorn, pandas and requests are installed separately from the package metadata.

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pip install uvicorn streamlit pandas requests
```

For OCR tooling, install `pip install -e '.[ocr]'`. The supplied Docker Compose configuration runs a corpus-audit task; it is not an application deployment.

### Prepare the document corpus

Place the authorized corpus ZIP in `inputs/` and replace the placeholder below with its actual filename:

```bash
python scripts/audit_corpus.py 'inputs/<corpus-archive>.zip'
python scripts/build_pages.py
```

For the accepted-OCR corpus and embedding index, configure the authorized embedding endpoint and use your own local key and CA certificate paths:

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

Inspect audit and extraction errors. Generated pages, indexes, caches, keys and certificates are local and excluded from Git. See `python scripts/search_corpus.py --help` for search modes and configuration. Local BM25 can search the original extracted corpus without a hosted API:

```bash
python scripts/search_corpus.py 'Does State include a Union territory?' \
  --mode bm25 --code 'Code on Wages' --data-dir data/processed
```

### Configure and launch

For generated answers, copy the configuration template and fill in the assigned endpoint, key path and CA certificate path:

```bash
cp -n configs/chat.example.json configs/chat.local.json
```

Alternatively set the four `CHAT_*` variables documented in [.env.example](.env.example) in the API process. They take precedence over the local JSON file; `.env` is not loaded automatically. Keep TLS verification enabled.

Start the API and UI in separate terminals, from the repository root:

```bash
PYTHONPATH=src .venv/bin/python -m uvicorn hr_navigator.server:app --reload --host 127.0.0.1 --port 8000
```

```bash
.venv/bin/python -m streamlit run app.py
```

Open the local URL printed by Streamlit. Select a fictional employee and ask “What is my leave balance?” for the synthetic demo, or ask an English document question after preparing the corpus. The **Evaluation & Telemetry** tab shows saved benchmarks and local request traces; the tab is not itself a publicly accessible dashboard.

### Optional Langfuse trace dashboard

Set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` in the API terminal to send traces to Langfuse. Run `.venv/bin/python scripts/trace_dashboard.py --send-test` to check the connection and print the dashboard link. The app does not load `.env` automatically. To avoid sending question text, set `LANGFUSE_SEND_QUERY_TEXT=false`. See the [trace dashboard guide](docs/trace_dashboard.md).

### Tests

```bash
make test
make lint
```

Some tests or full evaluation workflows need optional dependencies, corpus files or hosted services. See the test output and the [evaluation runner guide](docs/evaluation_runner_guide.md) for the scope and configuration of individual runs.

## Repository guide

| Path | Contents |
| --- | --- |
| `app.py`, `src/hr_navigator/server.py` | Streamlit interface and FastAPI endpoints |
| `src/hr_navigator/ingestion/`, `src/hr_navigator/retrieval/` | PDF processing, search and review-draft workflow |
| `src/hr_navigator/tools/`, `data/synthetic/` | Synthetic HR tools and fictional fixtures |
| `src/hr_navigator/security/`, `src/hr_navigator/observability/` | Input checks and local tracing |
| `evaluation/`, `reports/` | Evaluation sets, metrics, source audit and findings |
| `scripts/`, `tests/`, `docs/` | Reproduction commands, tests and project documentation |
