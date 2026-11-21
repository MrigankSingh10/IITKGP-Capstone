# Member 1 closeout and Member 2 handoff

21 November 2026. Member 1's deliverables are complete for the capstone’s document-reference scope. The project uses the supplied corpus with the limits recorded below.

| Responsibility | Closure evidence |
| --- | --- |
| Define supported intents and refusal rules | [Domain specification](../docs/member_1_domain_rules.md) adopted under delegated authority. Covers answer, clarify, refuse, escalate, evidence hierarchy, version handling, privacy and confirmation. |
| Source and tag policy documents | [Source triage](member_1_source_triage.csv) covers 126 PDFs. All local SHA-256 hashes and page counts were verified, totalling 1,767 pages. All manifest URLs point to the Ministry hostname. Twenty-three priority documents have a checked instrument identity and document date with an original PDF page citation. The other 103 have manifest-based tags and unverified dates. Four source PDFs were located online. No remote byte comparison was made. |
| Own corpus quality and provenance | [Sparse-page dispositions](member_1_sparse_page_triage.csv) cover all 25 originally sparse pages. Keep 11 user-accepted transcriptions with OCR warnings, 12 navigation or illustrative pages with native text, and two visually blank pages as registered page identities. Assistant visual checks support those dispositions. Keep the source scans. No independent human check is recorded. |
| Handle amendments, versions and conflicts | [Source relationships](member_1_source_relationships.csv) records amendments, corrections, commencement evidence, the bilingual OSH Act pair and the Social Security letter conflict. Corporate policy comes from the [synthetic Acme handbook](../docs/acme_handbook_v0.1.md). |

## Priority source decisions

- The Ministry lists final 2026 Central Rules for all four codes. Use the final Gazette instruments in the corpus for questions about those rules. The 2025 draft copies are useful for questions about draft text. Match the language on corrigenda and check the scope of the actual rule before applying it. [Final Rules listing](https://www.labour.gov.in/offerings/schemes-and-services/details/labour-codes-gzNzQzMtQWa), [Ministry draft archive](https://www.labour.gov.in/offerings/schemes-and-services/details/labour-codes-2-ATO5YzMtQWa?archives=true).
- The Industrial Relations Code amendment replaces section 104(1) and adds section 104(1A). It states a deemed commencement date of 21 November 2025. For section 104 queries, retrieve it alongside the original Act. [Amendment Gazette](https://www.labour.gov.in/static/uploads/2026/02/91ef39e2096112f8b798e6c45c732e2f.pdf).
- The Social Security Act attributes Central Government rule-making to section 155 and State Government rule-making to section 156. The original ministry letter PDF page 10 prints section 155 for the state heading. Retain the letter as explanatory evidence, use the Act for statutory authority and surface the discrepancy. For commencement questions, pair S.O. 5319(E) with corrigendum S.O. 5936(E) and check any applicable earlier notices. [Act](https://www.indiacode.nic.in/bitstream/123456789/16823/1/aA2020-36.pdf), [Ministry letter](https://www.labour.gov.in/static/uploads/2026/03/d70bb9f7e87ec48bd64fde40329f9c09.pdf), [Gazette corrigendum](https://egazette.gov.in/WriteReadData/2025/268694.pdf).
- The Hindi and English OSH PDFs share Act No. 37 of 2020 and have distinct file hashes and page numbering. Route by requested language and cite the PDF actually used.

## Retrieval handoff

1. Join source tags and relationships on full `source_pdf_id` and sparse-page dispositions on `page_id`. Cite the existing registry URL, title and 1-based PDF page. The accepted OCR registry is the working corpus. Treat the sparse-page navigation and blank dispositions as evidence eligibility guidance.
2. Preserve typography or transcription warnings when surfacing letter pages. Supplement amended or corrected passages with their linked instruments where the question needs them. For the externally linked commencement corrigendum, cite the external Gazette only when available and clearly identify it as outside the existing indexed evidence.
3. Use `document_type` and `labour_code_manifest` as routing hints. `document_date` means the kind named in `document_date_kind`. Leave applicability filters closed until the relevant provision, date and jurisdiction are validated. Treat unverified dates or relationships as unknown.
4. The strict adjudicated [user baseline scores](baseline_v1_review.csv) are the working reference for the 80 document questions. They give 19 passes out of 240, split 6, 5 and 8 across zero-shot, few-shot and decomposition. The [team scoring](baseline_v1_review_team.csv) gives 33 out of 240, with 14 different verdicts. Preserve both and label the chosen rubric in comparisons. Final performance claims require independent review under a shared rubric.
5. Use the existing [relevance review template](../evaluation/relevance_review_template.csv) for independent page judgments. Keep those reviewers blind to the provisional rankings and model answers. The existing frozen sets can support regression checks. Member 2’s final evaluation still requires new examples and independent labels.

## Conditions outside this sign-off

- Faculty acceptance was reported by the user. Written wording and applicability to the chunk cap remain unconfirmed. Report the three counts separately: 126 source PDFs, 1,767 page documents and the index-specific chunk count.
- The full corpus has no verified redistribution clearance. The project will distribute the registry and official links rather than republish the source PDFs or the full OCR corpus.
- The corpus supports document-reference questions. Complete amendment histories and present applicability for individual employers, provisions or jurisdictions remain outside this release. Escalate those questions when the necessary evidence is missing.
