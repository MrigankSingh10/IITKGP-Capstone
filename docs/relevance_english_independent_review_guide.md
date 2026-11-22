# English relevance review: independent labeling

Review `evaluation/relevance_english_independent_review.csv` without consulting ranked results, generated answers, assistant labels, or any proposed page list. The 12 English questions were written by an assistant after inspecting the corpus; the page judgments are not yet independent. They are document questions, not claims about current applicability. A qualified reviewer should independently find every relevant page in the original PDFs, using 1-based PDF page numbers and full page IDs from `data/processed/accepted_ocr/pages.jsonl`. Check original scans for OCR uncertainty. Record ambiguities, source conflicts and limits in `notes`. If evidence is absent, incomplete, or a question is ambiguous, leave it unapproved for adjudication or exclusion; do not guess. Another qualified reviewer should resolve disagreements. Labels cannot be assumed exhaustive without a comprehensive corpus review.

Fill `relevant_page_ids` with semicolon-separated IDs, `reviewer` with the reviewer's name, and `review_status` with `approved` only after review. Keep IDs, questions, language, order, and column names unchanged. No labels have been prefilled. After all rows are independently reviewed and approved, freeze locally with:

```bash
.venv/bin/python scripts/freeze_english_independent_review.py
```

The freezer checks the fixed question checksum, named approval, unique valid statutory page IDs and output non-overwrite; it cannot verify human independence or relevance. It creates JSONL and a SHA-256 sidecar compatible with `scripts/evaluate_relevance_fresh.py score` when explicitly passed as `--frozen`. The existing scorer requires cached query vectors; do not generate embeddings or transfer benchmark data without authorization. Preserve the original review and frozen results. The fixed packet question checksum (compact JSON array of `[case_id, question, query_language]` in row order) is `e0d53a111cdae69d4be5f23d51b25a644eb29fa837855c46fd099bb0068bea49`.

An exact normalized-text comparison of question fields in existing evaluation CSV/JSONL and report CSV/JSON files found no matches. This does not rule out related provisions or semantic overlap, nor does it make the questions independently authored.
