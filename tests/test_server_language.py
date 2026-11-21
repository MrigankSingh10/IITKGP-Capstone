import pytest

pytest.importorskip('fastapi')
from fastapi.testclient import TestClient  # noqa: E402

from hr_navigator import server  # noqa: E402


def test_chat_rejects_devanagari_before_placeholder(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError('Placeholder must not run')

    monkeypatch.setattr(server, 'invoke_agent_or_stub', unexpected)
    client = TestClient(server.app)
    response = client.post('/chat', json={'session_id': 'language-test', 'query': 'मजदूरी क्या है?'})
    assert response.status_code == 200
    assert response.json()['answer'] == 'Please ask your question in English.'
    assert response.json()['route_taken'] == 'unsupported_language'
    assert response.json()['citations'] == []


def test_chat_english_reaches_existing_placeholder(monkeypatch):
    monkeypatch.setattr(server, 'log_trace', lambda *_args: None)
    client = TestClient(server.app)
    response = client.post('/chat', json={'session_id': 'english-test', 'query': 'What is leave?'})
    assert response.status_code == 200
    assert response.json()['route_taken'] == 'stub_route'
