# HR Policy Navigator

An IIT Kharagpur Track B capstone prototype for finding evidence in a collection of Indian Labour Codes documents. The intended system will distinguish statutory references from a fictional company's internal HR policy, cite original sources, and support controlled HR workflows. The current implementation focuses on corpus ingestion, evaluation and experimental document retrieval; it is not a production HR assistant or legal advice.

## Current progress

- **Corpus audit:** Imported 126 source PDFs (1,767 pages), matched them to the supplied manifest, and recorded source IDs, titles, URLs and extraction results. Twenty-five pages had sparse extracted text. Source dates, legal applicability and redistribution rights still require verification.
- **Evaluation and baselines:** Froze 80 document-only questions in `evaluation/gold_v1.jsonl` and scored all 240 closed-book responses (zero-shot 11.3%, few-shot 12.5%, decomposition 17.5%); failure patterns and tokens per query are in `reports/baseline_v1_report.md`. A 40-case behaviour set for refusals, injection, company policy, tools and approvals is drafted in `evaluation/scenarios_v0.1.jsonl` and awaits team sign-off before freezing (see `docs/scenario_set_guide.md`). Cost per query awaits a price in `configs/pricing.json`.
- **Retrieval prototype:** Extracts page-contained chunks at two sizes, searches with BM25, dense FAISS or hybrid ranking, and returns source and page metadata. Dense indexing currently covers pages heuristically classified as Latin script; lexical search covers extractable chunks across scripts.
- **Review work:** Added queues for sparse-page OCR, source dates and possible versions, plus a template for independent retrieval relevance review. OCR candidates require human approval and are not automatically indexed. See `docs/phase_2_review_guide.md`.
- **Grounded answers:** A prototype checks source identity and exact quotations, but a live test produced an incorrect answer with genuine, irrelevant quotes. It therefore escalates to human review rather than presenting an unverified answer.

No agent graph, production service or real HR integration has been implemented. Faculty confirmation of how pages count toward the document requirement is pending. See `reports/phase_2_summary.md` and `reports/retrieval_v1_report.md` for results and limitations; earlier phase reports describe the project at the time they were written.

## Project layout

| Path | Purpose |
| --- | --- |
| `src/hr_navigator/` | Corpus ingestion, API client, retrieval and prototype data model |
| `scripts/` | Audit, page/chunk generation, baseline evaluation, retrieval and review utilities |
| `configs/` | BGE tokenizer used to measure chunk sizes |
| `evaluation/` | Frozen document-only questions and review templates |
| `docs/` | Product specification, fictional handbook and review guides |
| `reports/` | Audit, baseline and retrieval results and review worksheets |
| `data/synthetic/` | Fictional Acme handbook data |

The public legal corpus is separate from the synthetic Acme policy. Employee records and handbook examples are fictional; they do not establish actual entitlements.

## Setup

Requires Python 3.11 or newer:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
make test
make lint
```

For the optional local OCR review workflow, install `pip install -e '.[ocr]'`. The OCR model's output must be checked against the original page before use.

The original corpus ZIP, credentials, certificates, generated pages and embedding cache are local-only and excluded by `.gitignore`. Place the supplied corpus ZIP in `inputs/` and run the audit with its actual filename:

```bash
python scripts/audit_corpus.py 'inputs/<corpus-archive>.zip'
python scripts/build_pages.py
```

Alternatively, `make audit` expects the specific filename shown in the `Makefile`. The audit rejects unsafe archive paths and size limits, stores PDFs by SHA256, and preserves manifest matches in a source registry. Inspect extraction errors and unmatched metadata before relying on it. The registry refuses changed inputs; use a separate report directory for a different corpus version. Page and chunk files are written under `data/processed/` and remain local.

## Search and embeddings

BM25 search runs locally after the pages and chunks are built:

```bash
python scripts/search_corpus.py 'Does State include a Union territory?' --mode bm25 --code 'Code on Wages'
```

Results include the original title, PDF page number, source URL and matching text. Build the local embedding cache to use dense or hybrid search. Set `EMBEDDING_BASE_URL` to the authorized endpoint and supply the course-provided key and CA certificate locally:

```bash
python scripts/build_embeddings.py \
  --key-file VM02_Embeddings_Access/shared-embedding-key.txt \
  --ca-file VM02_Embeddings_Access/vm02-ca.crt \
  --base-url "$EMBEDDING_BASE_URL" --model bge-small-en-v1.5
```

Use `python scripts/search_corpus.py --help` for dense and hybrid options. The cache resumes without re-embedding saved text. The included BGE-small tokenizer is from the public model repository; check its redistribution terms and those of the corpus before sharing. Language detection is heuristic and mixed-language coverage is not validated. Date filters fail closed until source dates are verified.

## Review and next steps

Review sparse pages and proposed OCR against the original PDFs, verify source dates and version relationships, and independently annotate retrieval relevance using `docs/phase_2_review_guide.md`. The optional `scripts/apply_reviewed_ocr.py` creates a separate page file from explicitly approved rows; it does not update indexes. Complete human scoring of the saved baseline responses before claiming improvement or beginning agent development. Reliable answer support checks, adversarial evaluation, legal applicability and faculty clarification remain open.

For API-backed experiments, use `.env.example` as a template for local environment variables; the application does not automatically load `.env`. Keep keys and certificates out of the repository, use the appropriate separate chat and embedding credentials, and retain TLS verification. Confirm endpoint assignment and operational limits before live use. Docker Compose provides an audit skeleton, not a running application.
