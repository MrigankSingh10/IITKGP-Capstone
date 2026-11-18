import csv
import io
import json
import sqlite3
import ssl
import zipfile

import fitz
import httpx
import pytest

from hr_navigator.clients.api import APIConfig, APIError, HostedClient
from hr_navigator.db import migrate, seed_synthetic
from hr_navigator.ingestion.audit import audit, safe_members


def make_pdf():
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), 'A short synthetic page')
    data = doc.tobytes()
    doc.close()
    return data


def make_zip(path, name='code/file.pdf'):
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('manifest.csv', 'filename,source_url,status\nfile.pdf,https://example.org/file.pdf,downloaded\n')
        z.writestr(name, make_pdf())


def test_audit_page_and_immutable_registry(tmp_path):
    archive = tmp_path / 'corpus.zip'
    make_zip(archive)
    out, raw = tmp_path / 'reports', tmp_path / 'raw'
    report = audit(archive, raw, out)
    assert 'Source PDFs: 1' in report and 'Page documents: 1' in report
    assert 'Sparse pages (<100 characters): 1' in report
    rows = list(csv.DictReader(io.StringIO((out / 'corpus_inventory.csv').read_text())))
    rec = json.loads((out / 'source_registry.jsonl').read_text())
    assert rows[0]['source_pdf_id'] == rec['sha256']
    assert rec['manifest_matches'][0]['source_url'] == 'https://example.org/file.pdf'
    audit(archive, raw, out)
    make_zip(archive, 'other/file.pdf')
    with pytest.raises(ValueError, match='immutable'):
        audit(archive, raw, out)


@pytest.mark.parametrize('name', ['../escape.pdf', '/absolute.pdf', 'C:/evil.pdf', 'a\\evil.pdf'])
def test_rejects_unsafe_zip(tmp_path, name):
    archive = tmp_path / 'bad.zip'
    make_zip(archive, name)
    with zipfile.ZipFile(archive) as z, pytest.raises(ValueError):
        safe_members(z)


def test_migration_seed_and_foreign_key():
    db = sqlite3.connect(':memory:')
    migrate(db)
    migrate(db)
    seed_synthetic(db)
    seed_synthetic(db)
    assert db.execute('select count(*) from employees').fetchone()[0] == 1
    assert db.execute('pragma user_version').fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("insert into leave_balances values ('missing','demo', 1)")


def test_client_retry_and_usage():
    calls = []
    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={'data': [], 'usage': {'total_tokens': 3}})
    ca = ssl.get_default_verify_paths().cafile
    client = HostedClient(APIConfig('https://example.org/v1', 'model', 'secret', ca),
                          transport=httpx.MockTransport(handler), sleeper=lambda _: None)
    try:
        client.embed(['test'])
        assert len(calls) == 2 and client.usage == {'total_tokens': 3}
        assert calls[1].url.path == '/v1/embeddings'
        assert 'secret' not in repr(client.config)
    finally:
        client.close()


def test_client_sanitizes_errors():
    ca = ssl.get_default_verify_paths().cafile
    client = HostedClient(APIConfig('https://example.org/v1', 'model', 'secret', ca),
                          transport=httpx.MockTransport(lambda _: httpx.Response(401, text='secret')))
    try:
        with pytest.raises(APIError, match='HTTP 401') as exc:
            client.embed(['test'])
        assert 'secret' not in str(exc.value)
    finally:
        client.close()


def test_https_required():
    with pytest.raises(ValueError):
        APIConfig('http://example.org/v1', 'm', 'k', 'ca')
