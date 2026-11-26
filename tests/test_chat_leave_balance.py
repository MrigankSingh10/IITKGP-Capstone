"""End-to-end tests for natural-language leave-balance chat routing."""

from fastapi.testclient import TestClient

from hr_navigator import server
from hr_navigator.demo import (
    answer_leave_balance_question,
    connect_demo_database,
    is_leave_balance_question,
)


def test_chat_question_returns_displayable_synthetic_leave_balances(
    monkeypatch, tmp_path
):
    monkeypatch.setenv(
        "HR_NAVIGATOR_DEMO_DB_PATH", str(tmp_path / "synthetic-demo.sqlite3")
    )
    monkeypatch.setattr(server, "log_trace", lambda _event: None)

    # A balance question must be handled by the employee tool, not the fallback.
    def unexpected_fallback(*_args, **_kwargs):
        raise AssertionError("Leave-balance question reached document retrieval")

    monkeypatch.setattr(server, "run_hr_pipeline", unexpected_fallback)

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


def test_demo_balance_override_survives_a_later_balance_lookup(monkeypatch, tmp_path):
    db_path = tmp_path / "synthetic-demo.sqlite3"
    monkeypatch.setenv("HR_NAVIGATOR_DEMO_DB_PATH", str(db_path))

    connection = connect_demo_database(db_path)
    try:
        connection.execute(
            """
            UPDATE leave_balances
            SET days = ?
            WHERE employee_id = ? AND leave_type = ?
            """,
            (4, "demo-001", "annual"),
        )
        connection.commit()
    finally:
        connection.close()

    answer = answer_leave_balance_question(
        query="What is my annual leave balance?",
        employee_id="demo-001",
    )

    assert "Annual leave: **4 days**" in answer


def test_statutory_leave_entitlement_is_not_a_demo_balance_question():
    question = "What is the statutory leave entitlement under the law?"

    assert is_leave_balance_question(question) is False
    assert is_leave_balance_question("What is my leave entitlement?") is False
    assert is_leave_balance_question(
        "What leave entitlement applies under company policy?"
    ) is False


def test_statutory_entitlement_question_uses_document_retrieval(
    monkeypatch,
):
    from types import SimpleNamespace

    monkeypatch.setattr(server, "log_trace", lambda _event: None)
    monkeypatch.setattr(
        server,
        "run_hr_pipeline",
        lambda *_args, **_kwargs: (
            SimpleNamespace(
                decision="evidence_only",
                draft_not_verified=None,
                reason="Policy evidence was retrieved.",
                sources=[],
            ),
            {},
        ),
    )

    with TestClient(server.app) as client:
        response = client.post(
            "/chat",
            json={
                "session_id": "statutory-entitlement-review",
                "query": "What is the statutory leave entitlement under the law?",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["route_taken"] == "document_review"
    assert body["simulated"] is False
    assert body["answer"] == "Policy evidence was retrieved."
