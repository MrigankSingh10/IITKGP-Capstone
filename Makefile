.PHONY: test lint audit
test:
	python -m pytest
lint:
	ruff check .
audit:
	python scripts/audit_corpus.py inputs/Labour_Codes_Corpus\(1\).zip
