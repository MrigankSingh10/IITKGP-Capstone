# Phase 2 progress — retrieval prototype; gate not yet met

User approved proceeding while Phase 1 baseline correctness review remains deferred; saved responses and gold stay frozen. This is not a measured baseline-to-RAG accuracy improvement. No LangGraph has been implemented.

## Data and embedding

The page registry has 126 source PDFs and 1,767 logical page documents, including 25 sparse pages, with no extraction errors. Original SHA256, filename, title, source URL, code, PDF page number and text are preserved. Printed page and current applicability are not assumed. Script heuristic labels: 737 Latin, 723 mixed, 294 Devanagari and 13 unknown/sparse; legacy encodings can make these unreliable. Thirteen pages had no extractable tokens, but remain in the page registry. OCR is not installed; sparse pages require review and targeted OCR. Source dates and legal status remain unvalidated, so date filtering fails closed. Page-as-document faculty approval and redistribution rights remain pending.

Two within-page BGE-tokenized settings produce 9,586 chunks (200 tokens with 40 overlap) and 5,586 chunks (350 with 60 overlap). These are chunks, not page documents; both exceed 2,000, so faculty interpretation of the cap needs confirmation. 2,651 and 1,598 chunks respectively from Latin-script heuristic pages are eligible for dense indexing; mixed and Devanagari pages remain in lexical search. The English embedding API was used for 4,176 unique corpus texts; a further 19 query vectors were cached. Verified TLS, batches up to 16 and 384-dimensional vectors were observed, and the provided quickstart documents 512 model tokens. Chunk sizes use the BGE tokenizer; incremental cache and retry/backoff are implemented. No claim is made that mixed/Hindi embeddings have been evaluated.

## Retrieval and safety

Implemented metadata/scope filters, local BM25, FAISS cosine dense ranking built from cached vectors, reciprocal rank fusion, page-level deduplication, deterministic lexical reranking, source/page/URL validation and exact quote checks. No external reranker or extra generative model is used. See `retrieval_v1_report.md` for a provisional 19-question, two-chunk-size comparison. This is not a fully independently reviewed relevance set.

A live smoke test asking whether State includes a Union territory produced a wrong generated answer and real but irrelevant quotes; source/page existence did not establish entailment. Consequently the prototype answer function fails closed to human review even if quote checks pass. A second live test returned escalation. No reliable automatic citation-grounded answer is claimed. Date/version conflict resolution, automated support checking and robust injection evaluation are not complete.

## Checks and outstanding gate

15 unit tests passed, lint passed; PyMuPDF/FAISS emitted deprecation warnings. Live embedding and chat calls worked; VM04 group assignment remains unconfirmed. To meet the Phase 2 exit gate: targeted OCR or explicit reviewed exclusions for sparse pages, validated source dates and version conflicts, independently reviewed diverse query/page relevance annotations, trustworthy citation-grounded answer and adversarial tests, and confirmed faculty interpretation. Complete the deferred Phase 1 baseline scoring before agent development. Test set tuning remains prohibited.
