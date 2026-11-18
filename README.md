# HR Policy Navigator — Phase 0

This repository is a Phase 0 foundation for a five-person Track B capstone. The corpus contains public legal references, not Acme policy. No agent graph or retrieval chunks have been implemented. Page-as-document counting is conditional on written faculty confirmation; source PDFs, page documents and chunks are distinct.

Python 3.11+: `python -m venv .venv`, activate it, then `pip install -e '.[dev]'`. Run `make test` and `make lint`. Place the supplied corpus ZIP in ignored `inputs/` and run `make audit`. The importer rejects unsafe paths and size limits, preserves original archive paths and matching manifest rows in an immutable registry, stores PDFs by SHA256, and reports every extractable page. Inspect unmatched manifest rows and extraction errors before relying on metadata. The registry refuses changed inputs; use a separate report directory for a new corpus version. Review redistribution rights before sharing corpus or reports.

Set local environment variables using `.env.example` as a template; the application does not automatically load `.env`. Use the matching provided CA file and separate chat and embedding credentials. Never disable TLS verification. `APIConfig.from_env('CHAT')` and `APIConfig.from_env('EMBEDDING')` configure the adapter. The VM04 certificate suggests, but does not prove, assignment to groups 046–065; verify assignment before live use. API limits must be confirmed before relying on them. Seeds in `hr_navigator.db` are fictional and do not define an actual leave policy.

The Docker Compose audit service is a skeleton. It requires the corpus ZIP and writes reports and raw data to local bind mounts. The project deliberately has no live service or agent implementation at this stage.

## Phase 2 document retrieval (experimental)

After placing the original corpus ZIP locally and running `make audit`, run `.venv/bin/python scripts/build_pages.py` to create ignored `data/processed/pages.jsonl` and 200/350-token page-contained chunk files. The tokenizer in `configs/bge-small-en-v1.5-tokenizer.json` is the public BAAI BGE-small-en-v1.5 tokenizer (downloaded from the model's Hugging Face repository; SHA256 `d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66`). Its licensing and redistribution terms, like those of the corpus, should be checked before distribution.

To populate the ignored local embedding cache with the supplied course endpoint:

```bash
.venv/bin/python scripts/build_embeddings.py \
  --key-file VM02_Embeddings_Access/shared-embedding-key.txt \
  --ca-file VM02_Embeddings_Access/vm02-ca.crt \
  --base-url "$EMBEDDING_BASE_URL" --model bge-small-en-v1.5
```

The cache resumes without repeating already embedded texts. Only Latin-script heuristic pages are densely indexed; all extractable text remains available to BM25. Script detection is imperfect, including for legacy encoded Hindi. Sparse pages remain present in the registry; no OCR is installed. Date filters fail closed until dates are verified.

Search without any endpoint call:

```bash
.venv/bin/python scripts/search_corpus.py 'Does State include a Union territory?' --mode bm25 --code 'Code on Wages'
```

The output provides matched text with original PDF title, page and URL. Hybrid search additionally requires the embedding flags shown in `scripts/search_corpus.py --help`. The local scorer builds a filtered FAISS index from cached vectors in memory per query; BM25 is calculated locally. The prototype `scripts/ask_documents.py --help` uses both course APIs, but currently escalates instead of presenting an unverified generated answer: a live test found an incorrect answer with genuine but irrelevant quotations. Citation validation checks identity and quote presence, not whether the answer follows. Treat source text as untrusted and check applicability independently. See `reports/phase_2_summary.md` and `reports/retrieval_v1_report.md` before using results.
