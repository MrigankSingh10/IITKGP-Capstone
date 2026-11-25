"""End-to-end tests for natural-language leave-balance chat routing."""

from fastapi.testclient import TestClient

from hr_navigator import server


def test_chat_question_returns_displayable_synthetic_leave_balances(
    monkeypatch, tmp_path
):
    monkeypatch.setenv(
        "HR_NAVIGATOR_DEMO_DB_PATH", str(tmp_path / "synthetic-demo.sqlite3")
    )
    monkeypatch.setattr(server, "log_trace", lambda _event: None)

    # A balance question must be handled by the employee tool, not the fallback.
    def unexpected_fallback(**_kwargs):
        raise AssertionError("Leave-balance question reached the generic agent route")

    monkeypatch.setattr(server, "invoke_agent_or_stub", unexpected_fallback)

    with TestClient(server.app) as client:
        response = client.post(
            "/chat",
            json={
                "session_id": "leave-balance-e2e",
                "employee_id": "demo-001",
                "query": "What is my leave balance?",
            },
        )

    assert response.status_code == 200
    body = response.json()

    # app.py renders this answer through st.markdown(body["answer"]) and shows
    # the simulated-data notice when body["simulated"] is true.
    assert body["route_taken"] == "leave_balance_tool"
    assert body["simulated"] is True
    assert "Asha Rao" in body["answer"]
    assert "Annual leave: **12 days**" in body["answer"]
    assert "Sick leave: **6 days**" in body["answer"]
    assert "fictional test data" in body["answer"]


def test_chat_routes_a_specific_annual_balance_question(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "HR_NAVIGATOR_DEMO_DB_PATH", str(tmp_path / "synthetic-demo.sqlite3")
    )
    monkeypatch.setattr(server, "log_trace", lambda _event: None)

    with TestClient(server.app) as client:
        response = client.post(
            "/chat",
            json={
                "session_id": "annual-balance-e2e",
                "employee_id": "demo-002",
                "query": "How much annual leave do I have available?",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["route_taken"] == "leave_balance_tool"
    assert body["simulated"] is True
    assert "Vikram Nair" in body["answer"]
    assert "Annual leave: **2 days**" in body["answer"]
    assert "Sick leave" not in body["answer"]
