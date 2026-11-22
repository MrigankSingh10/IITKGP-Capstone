# Grounding hold-out set — review and freeze guide (v0.2 draft)

**Status:** 20 draft questions, none reviewed yet. Owner: Member 4. Reviewers: team members with the
local corpus PDFs.

## Why a hold-out set

The fresh grounding set (`grounding_fresh_v1`) is used while improving retrieval and prompts, so the
team has seen how the system does on it. The hold-out set is kept aside for the **final** grounding
measurement only. If we tune against it, the final number stops meaning anything.

**Blinding rules**
- Do not run the RAG pipeline on these questions while developing, and do not change chunking,
  `top_k`, reranking, prompts or thresholds because of a hold-out question.
- Run it once, after the pipeline is fixed, and report that run as the final grounding result.

## What is in v0.2

`evaluation/grounding_holdout_candidates_v0.2.jsonl` (Member 1's v0.1 file is left unchanged):

| Cases | Origin | State |
|---|---|---|
| holdout-draft-001 to 008 | Member 1's drafts (v0.1), copied unchanged | page number and quote already filled; need a reviewer's check |
| holdout-draft-009 to 020 | New drafts (Code on Wages 3, IR Code 4, Social Security 2, OSH 3) | written from the published Code text **without** the corpus pages; page number and quote are empty |

The new drafts avoid topics already in the gold and fresh sets (gratuity, grievance committees, wage
periods, overtime, floor wage, deductions, fines, canteens).

## How to review (about 2–3 minutes per question)

Open `evaluation/grounding_holdout_review_v0.2.csv` in Excel or Google Sheets. For each row:

1. Open the PDF named in `original_title` from the local corpus and find the `section`.
2. Check that the `expected_conditions` match what the Code actually says. Fix the wording if needed;
   keep it short and testable.
3. Fill `pdf_page_number` with the **PDF page number** (the page counter in the viewer, not the printed
   page number).
4. Copy an exact sentence from that page into `source_quote`. It must appear word for word in the OCR
   text, so copy from `data/processed/accepted_ocr/pages.jsonl` if the PDF text differs slightly.
5. Set `review_verdict` to `approved` or `rejected`, `reviewer` to `Team members` (or your role), and
   say why in `review_notes` if you changed or rejected something.

Reject a question if the section is not in the corpus, the answer depends on state rules, or it is
too similar to another question.

## Freeze (once)

```bash
python -m pytest -q tests/test_holdout_set.py
python scripts/freeze_holdout.py
```

The script uses the same checks as the fresh set (quote must appear on the cited page, title and URL
must match the page registry), drops rejected rows, refuses to freeze fewer than 15 approved cases,
rejects questions already in `gold_v1` or `grounding_fresh_v1`, and never overwrites
`grounding_holdout_v1.*`.
