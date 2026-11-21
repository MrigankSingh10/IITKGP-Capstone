"""Development-only evaluation of a preselected section and window candidate."""

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, "src")
from hr_navigator.retrieval.search import search
from hr_navigator.retrieval.embeddings import read_vector


def read(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def summary(rows, key):
    return {
        **{
            f"hit_at_{n}": sum(row[key] is not None and row[key] <= n for row in rows) / len(rows)
            for n in (3, 5, 10, 30)
        },
        "mrr_at_10": sum(1 / row[key] if row[key] and row[key] <= 10 else 0 for row in rows)
        / len(rows),
    }


path = "evaluation/grounding_fresh_v1.jsonl"
cases = [
    c
    for c in read(path)
    if c.get("source_pdf_id")
    and c.get("pdf_page_number")
    and c.get("expected_decision") == "review_required"
]
db = sqlite3.connect("file:data/indexes/accepted_ocr.sqlite?mode=ro", uri=True)
qdb = sqlite3.connect("file:data/indexes/grounding_fresh_queries.sqlite?mode=ro", uri=True)
model = "bge-small-en-v1.5"
out = {
    "development_sha256": sha(path),
    "scope": "Development only; one source-linked page per case, incomplete labels and not independently adjudicated.",
    "results": {},
}
for size in (200, 350):
    path = f"data/processed/accepted_ocr/chunks_{size}.jsonl"
    chunks = read(path)
    vectors = {
        c["chunk_id"]: v for c in chunks if (v := read_vector(db, model, c["text"])) is not None
    }
    rows = []
    for c in cases:
        target = f"{c['source_pdf_id']}:page_{c['pdf_page_number']:04d}"
        v = read_vector(qdb, model, c["question"])
        assert v is not None
        row = {"id": c["case_id"], "target_page": target}
        for name, section, window in [
            ("before", False, False),
            ("window", False, True),
            ("combined", True, True),
        ]:
            pages = [
                r["page_id"]
                for r in search(
                    c["question"],
                    chunks,
                    vectors,
                    v,
                    top_k=30,
                    mode="hybrid_rerank",
                    section_candidates_enabled=section,
                    proximity_enabled=window,
                )
            ]
            row[name] = pages.index(target) + 1 if target in pages else None
        rows.append(row)
        print(size, row, flush=True)
    out["results"][str(size)] = {
        "chunk_sha256": sha(path),
        "before": summary(rows, "before"),
        "window": summary(rows, "window"),
        "combined": summary(rows, "combined"),
        "cases": rows,
    }
    print(
        size,
        {k: out["results"][str(size)][k] for k in ("before", "window", "combined")},
        flush=True,
    )
Path("reports/retrieval_window_dev.json").write_text(json.dumps(out, indent=2) + "\n")
