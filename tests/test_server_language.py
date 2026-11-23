import pytest

pytest.importorskip('fastapi')
from fastapi.testclient import TestClient
from hr_navigator import server
from hr_navigator.retrieval.review_adapter import ReviewResult


@pytest.fixture(autouse=True)
def no_traces(monkeypatch):
    monkeypatch.setattr(server, 'log_trace', lambda *_args: None)


def test_chat_rejects_devanagari_before_retrieval(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError('Retrieval must not run')
    monkeypatch.setattr(server, 'run_hr_pipeline', unexpected)
    response = TestClient(server.app).post('/chat', json={'session_id': 'language-test', 'query': 'मजदूरी क्या है?'})
    assert response.status_code == 200
    assert response.json()['route_taken'] == 'unsupported_language'
    assert response.json()['citations'] == []


def test_chat_surfaces_review_draft_and_sources(monkeypatch):
    source = {'original_title': 'Test act', 'page_number': 2, 'quote_or_section': 'A quote'}
    result = ReviewResult('review_required', [source], draft_not_verified='A draft')
    monkeypatch.setattr(server, 'run_hr_pipeline', lambda query, labour_code: (result, {}))
    response = TestClient(server.app).post('/chat', json={'session_id': 'draft-test', 'query': 'What is leave?'})
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'review_required'
    assert body['answer'] == 'A draft'
    assert body['sources'] == [source]
    assert body['citations'] == ['Test act, PDF page 2']


def test_chat_reports_missing_corpus(monkeypatch):
    def unavailable(query, labour_code):
        raise FileNotFoundError('missing')
    monkeypatch.setattr(server, 'run_hr_pipeline', unavailable)
    response = TestClient(server.app).post('/chat', json={'session_id': 'missing-test', 'query': 'What is leave?'})
    assert response.status_code == 503


def test_local_chat_configuration_loads_key_and_closes_client(monkeypatch, tmp_path):
    import json
    config_dir = tmp_path / 'configs'
    config_dir.mkdir()
    (tmp_path / 'key.txt').write_text('test-key')
    (config_dir / 'chat.local.json').write_text(json.dumps({
        'base_url': 'https://example.test/v1', 'model': 'test-model',
        'key_file': 'key.txt', 'ca_file': 'ca.crt',
    }))
    monkeypatch.setattr(server, 'ROOT', tmp_path)
    for name in ('CHAT_BASE_URL', 'CHAT_MODEL', 'CHAT_API_KEY', 'CHAT_CA_FILE'):
        monkeypatch.delenv(name, raising=False)
    seen = {}
    class FakeClient:
        def __init__(self, config, retries):
            seen['config'] = config
            self.usage = {}
        def close(self):
            seen['closed'] = True
    class FakeAdapter:
        def retrieve(self, request, client):
            seen['question'] = request.question
            return ReviewResult('review_required', [], draft_not_verified='Draft')
    monkeypatch.setattr(server, 'HostedClient', FakeClient)
    monkeypatch.setattr(server, 'get_review_adapter', lambda: FakeAdapter())
    result, _ = server.run_hr_pipeline('A question?')
    assert result.draft_not_verified == 'Draft'
    assert seen['config'].api_key == 'test-key'
    assert seen['closed']


def test_chat_passes_selected_document_collection(monkeypatch):
    selected = []
    def pipeline(query, labour_code):
        selected.append(labour_code)
        return ReviewResult('escalate', [], reason='No evidence'), {}
    monkeypatch.setattr(server, 'run_hr_pipeline', pipeline)
    response = TestClient(server.app).post('/chat', json={
        'session_id': 'code-test', 'query': 'What is a wage?', 'labour_code': 'Code on Wages',
    })
    assert response.status_code == 200
    assert selected == ['Code on Wages']
