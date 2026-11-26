"""Exercise the demo employee selection and balance shortcut through the API."""

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("streamlit", reason="UI dependencies are optional")
pytest.importorskip("pandas", reason="UI dependencies are optional")
pytest.importorskip("requests", reason="UI dependencies are optional")

from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from hr_navigator import server


def test_selected_employee_and_quick_prompt_reach_balance_tool(monkeypatch, tmp_path):
    monkeypatch.setenv("HR_NAVIGATOR_DEMO_DB_PATH", str(tmp_path / "demo.sqlite3"))
    monkeypatch.setattr(server, "log_trace", lambda _event: None)
    client = TestClient(server.app)
    sent_requests = []

    def post_to_api(_url, json, timeout):
        sent_requests.append(json)
        response = client.post("/chat", json=json)
        return SimpleNamespace(ok=response.is_success, json=response.json,
                               status_code=response.status_code, text=response.text)

    monkeypatch.setattr("requests.post", post_to_api)
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: client.get("/health"))
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
    app.run()
    assert not app.exception

    employee_selector = next(s for s in app.selectbox if s.label == "Fictional demo employee")
    employee_selector.select("Vikram Nair (demo-002)").run()
    assert not app.exception
    shortcut = next(b for b in app.button if b.label == "What is my leave balance?")
    shortcut.click().run()

    assert not app.exception
    assert sent_requests[-1]["employee_id"] == "demo-002"
    assert sent_requests[-1]["query"] == "What is my leave balance?"
    assert any("Vikram Nair" in m.value and "2 days" in m.value for m in app.markdown)
