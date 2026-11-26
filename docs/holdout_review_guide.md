# Grounding hold-out set — review and freeze guide (v0.2 draft)

**Status:** reviewed and frozen as `evaluation/grounding_holdout_v1.jsonl` on 2026-11-24 (20 approved, none
rejected). An AI pre-review compared each expected answer with the page text; the evaluation owner confirmed
every row. Three expected answers (012, 013, 016) were updated to the page wording. Owner: evaluation.

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

## Match quotes to the OCR text

The freeze compares each quote character for character with the OCR page. Quotes copied from another
copy of a Code (for example India Code) can differ in line breaks, hyphenation or quote marks. Before
freezing, run:

```bash
python scripts/locate_holdout_quotes.py --review path/to/filled_sheet.csv
```

It finds each quote in `data/processed/accepted_ocr/pages.jsonl` while ignoring those differences, and
writes the exact OCR wording and PDF page number into `<sheet>_located.csv`. It lists any quote it can't
find. It never approves anything: check each row, set `review_verdict` and `reviewer`, then copy the sheet
to `evaluation/grounding_holdout_review_v0.2.csv`.

## Freeze (once)

```bash
python -m pytest -q tests/test_holdout_set.py
python scripts/freeze_holdout.py
```

The script uses the same checks as the fresh set (quote must appear on the cited page, title and URL
must match the page registry), drops rejected rows, refuses to freeze fewer than 15 approved cases,
rejects questions already in `gold_v1` or `grounding_fresh_v1`, and never overwrites
`grounding_holdout_v1.*`.

## Final run (once)

After the pipeline is fixed, run the frozen hold-out once, directly on RAG and end-to-end through the
chat API, then review and summarise as usual:

```bash
python scripts/run_evaluation.py run --test-set grounding_holdout_v1 --system rag --final
python scripts/run_evaluation.py run --test-set grounding_holdout_v1 --system api --final
python scripts/run_evaluation.py review-sheet --test-set grounding_holdout_v1 --runs reports/evaluation/grounding_holdout_v1__*.jsonl
python scripts/run_evaluation.py summarize --test-set grounding_holdout_v1 --runs reports/evaluation/grounding_holdout_v1__*.jsonl
```

Without `--final` the runner refuses, so the set cannot be used for tuning by accident.

Each system can measure the hold-out **once**. The first `--final` run of a system is recorded in
`evaluation/run_once_log.jsonl` (test set, its checksum, system, output file, start time); commit that
file with the results so the whole team sees it. After that, the runner refuses another run of the same
system on the same hold-out, even with a different `--output` or `--name`. `rag` and `api` are separate
systems, so the two documented runs above are each allowed once (for `callable`, each entrypoint counts
as its own system).

If a run stops part-way (network error, laptop sleeps, a `--limit` check), repeat **the same command**
with the same `--output` and `--name`: it finishes the unanswered questions and does not ask the
answered ones again. A complete run cannot be repeated; summarise its file instead.

