# Phase 2 progress — retrieval prototype; gate not yet met

User approved proceeding while Phase 1 baseline correctness review remains deferred; saved responses and gold stay frozen. This is not a measured baseline-to-RAG accuracy improvement. No LangGraph has been implemented.

## Data and embedding

The page registry has 126 source PDFs and 1,767 logical page documents, including 25 sparse pages, with no extraction errors. Original SHA256, filename, title, source URL, code, PDF page number and text are preserved. Printed page and current applicability are not assumed. Script heuristic labels: 737 Latin, 723 mixed, 294 Devanagari and 13 unknown/sparse; legacy encodings can make these unreliable. Thirteen pages had no extractable tokens, but remain in the page registry. Local OCR has been run on the 25 sparse pages; see the update below. OCR candidates require human review and are not indexed. Source dates and legal status remain unvalidated, so date filtering fails closed. Page-as-document faculty approval and redistribution rights remain pending.

Two within-page BGE-tokenized settings produce 9,586 chunks (200 tokens with 40 overlap) and 5,586 chunks (350 with 60 overlap). These are chunks, not page documents; both exceed 2,000, so faculty interpretation of the cap needs confirmation. 2,651 and 1,598 chunks respectively from Latin-script heuristic pages are eligible for dense indexing; mixed and Devanagari pages remain in lexical search. The English embedding API was used for 4,176 unique corpus texts; a further 19 query vectors were cached. Verified TLS, batches up to 16 and 384-dimensional vectors were observed, and the provided quickstart documents 512 model tokens. Chunk sizes use the BGE tokenizer; incremental cache and retry/backoff are implemented. No claim is made that mixed/Hindi embeddings have been evaluated.

## Retrieval and safety

Implemented metadata/scope filters, local BM25, FAISS cosine dense ranking built from cached vectors, reciprocal rank fusion, page-level deduplication, deterministic lexical reranking, source/page/URL validation and exact quote checks. No external reranker or extra generative model is used. See `retrieval_v1_report.md` for a provisional 19-question, two-chunk-size comparison. This is not a fully independently reviewed relevance set.

A live smoke test asking whether State includes a Union territory produced a wrong generated answer and real but irrelevant quotes; source/page existence did not establish entailment. Consequently the prototype answer function fails closed to human review even if quote checks pass. A second live test returned escalation. No reliable automatic citation-grounded answer is claimed. Date/version conflict resolution, automated support checking and robust injection evaluation are not complete.

## Checks and outstanding gate

16 unit tests passed, lint passed; PyMuPDF/FAISS emitted deprecation warnings. Live embedding and chat calls worked; VM04 group assignment remains unconfirmed. To meet the Phase 2 exit gate: targeted OCR or explicit reviewed exclusions for sparse pages, validated source dates and version conflicts, independently reviewed diverse query/page relevance annotations, trustworthy citation-grounded answer and adversarial tests, and confirmed faculty interpretation. Complete the deferred Phase 1 baseline scoring before agent development. Test set tuning remains prohibited.

## Follow-up: sparse pages and source review

On 2026-11-18 RapidOCR was run locally on all 25 sparse pages, with no OCR exceptions. Eleven of the 12 image-based Social Security pages produced substantial candidate text; the twelfth produced none. One other page produced no candidate text. Remaining short pages also received candidates. All output is unreviewed and has not been added to search or embedded; original page text and original PDF/page identities remain intact. OCR confidence is not legal or transcription accuracy. The full candidate sheet is `reports/sparse_ocr_review_readable.csv`, and the original extracted OCR text is in ignored `data/processed/sparse_ocr_candidates.jsonl`. Once reviewers explicitly approve and identify themselves, `scripts/apply_reviewed_ocr.py` can produce a separate reviewed page registry without altering the original or indexes; rebuilding and evaluating chunks/indexes still requires work.

`reports/source_date_review.csv` checks manifest dates against simple date strings in the first three extracted pages: 78 are text matches and 48 need manual review. These are search results, not verified publication dates or legal status. `reports/possible_source_versions.json` flags one identical-normalized-title group for review and does not establish supersession. `evaluation/relevance_review_template.csv` is a blank worksheet for independently reviewing the existing 19 questions; it is not yet an independently annotated relevance set. `docs/phase_2_review_guide.md` explains the review.

Citation validation now also checks title and verifies quoted text on the original registered page, including page-ID consistency; it cannot verify semantic support. The response workflow remains fail-closed. Phase 2 therefore remains incomplete pending human OCR/relevance review, confirmed source status and faculty interpretation, and a reliably evaluated grounding approach.

During OCR setup Homebrew began upgrading dependencies. The attempted installation was interrupted after several upgrades; Homebrew reported an interrupted linkage repair for libxrender. The affected package versions remain installed, and `tesseract --version` succeeds, but other Homebrew software was not comprehensively tested. The OCR run used RapidOCR in the project virtual environment instead.
