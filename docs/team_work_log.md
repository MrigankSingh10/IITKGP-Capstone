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

- Keep frozen sets and historical reports unchanged; don't tune against regression labels. Reconcile the differing baseline reviews and independently review new relevance and grounding cases before performance claims.
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
