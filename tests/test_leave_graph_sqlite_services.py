"""Graph integration tests using the real SQLite leave request service."""

import sqlite3
from pathlib import Path

import pytest
from langgraph.types import Command

from hr_navigator.db import migrate, seed_scenario_fixtures
from hr_navigator.orchestration.leave_graph import build_leave_graph
from hr_navigator.orchestration.services import SQLiteLeaveServices
from hr_navigator.tools.leave_requests import get_request_status


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = PROJECT_ROOT / "evaluation" / "scenario_fixtures_v0.1.json"


@pytest.fixture
def sqlite_leave_runtime(tmp_path):
    connection = sqlite3.connect(tmp_path / "leave-workflow.sqlite3")
    connection.row_factory = sqlite3.Row
    migrate(connection)
    seed_scenario_fixtures(connection, FIXTURE_PATH)

    auth_context = {
        "employee_id": "demo-001",
        "authenticated": True,
    }
    services = SQLiteLeaveServices(connection)
    runtime_context = {
        "db_connection": connection,
        "idempotency_key": "sqlite-graph-test-001",
        "services": services,
    }
    initial_state = {
        "auth_context": auth_context,
        "leave_type": "annual",
        "start_date": "2027-01-25",
        "end_date": "2027-01-29",
        "state": "Karnataka",
        "year": 2027,
    }

    try:
        yield connection, auth_context, runtime_context, initial_state
    finally:
        connection.close()


def _status_for(connection, auth_context, draft_id):
    result = get_request_status(connection, auth_context, draft_id)
    assert result["success"] is True
    assert result["count"] == 1
    return result["requests"][0]["status"]


def test_graph_confirmation_submits_to_real_sqlite_database(sqlite_leave_runtime):
    connection, auth_context, runtime_context, initial_state = sqlite_leave_runtime
    graph = build_leave_graph()
    config = {"configurable": {"thread_id": "sqlite-confirm-001"}}

    interrupted = graph.invoke(
        initial_state,
        config=config,
        context=runtime_context,
    )

    assert "__interrupt__" in interrupted
    draft_id = interrupted["draft_id"]
    assert "approval_token" not in interrupted["leave_draft"]
    assert _status_for(connection, auth_context, draft_id) == "draft"

    result = graph.invoke(
        Command(resume="confirm"),
        config=config,
        context=runtime_context,
    )

    assert result["confirmation"] == "confirm"
    assert result["status"] == "submitted"
    assert result["request_id"] == draft_id
    assert _status_for(connection, auth_context, draft_id) == "submitted"

    audit_actions = {
        row[0]
        for row in connection.execute(
            "SELECT action FROM leave_request_audit WHERE draft_id = ?",
            (draft_id,),
        )
    }
    assert "REQUEST_SUBMITTED" in audit_actions


def test_graph_cancellation_leaves_real_sqlite_draft_unsubmitted(
    sqlite_leave_runtime,
):
    connection, auth_context, runtime_context, initial_state = sqlite_leave_runtime
    graph = build_leave_graph()
    config = {"configurable": {"thread_id": "sqlite-cancel-001"}}

    interrupted = graph.invoke(
        initial_state,
        config=config,
        context=runtime_context,
    )
    assert "__interrupt__" in interrupted
    draft_id = interrupted["draft_id"]

    result = graph.invoke(
        Command(resume="cancel"),
        config=config,
        context=runtime_context,
    )

    assert result["confirmation"] == "cancel"
    assert result["status"] == "cancelled"
    assert _status_for(connection, auth_context, draft_id) == "draft"

    audit_actions = {
        row[0]
        for row in connection.execute(
            "SELECT action FROM leave_request_audit WHERE draft_id = ?",
            (draft_id,),
        )
    }
    assert "DRAFT_CREATED" in audit_actions
    assert "REQUEST_SUBMITTED" not in audit_actions


def test_graph_retry_of_existing_draft_can_still_be_confirmed(
    sqlite_leave_runtime,
):
    connection, auth_context, runtime_context, initial_state = sqlite_leave_runtime
    graph = build_leave_graph()
    first_config = {"configurable": {"thread_id": "sqlite-retry-first"}}
    retry_config = {"configurable": {"thread_id": "sqlite-retry-second"}}

    first_attempt = graph.invoke(
        initial_state,
        config=first_config,
        context=runtime_context,
    )
    assert "__interrupt__" in first_attempt

    retry_attempt = graph.invoke(
        initial_state,
        config=retry_config,
        context=runtime_context,
    )

    assert "__interrupt__" in retry_attempt
    assert retry_attempt["draft_id"] == first_attempt["draft_id"]
    assert "approval_token" not in retry_attempt["leave_draft"]

    result = graph.invoke(
        Command(resume="confirm"),
        config=retry_config,
        context=runtime_context,
    )

    assert result["status"] == "submitted"
    assert result["request_id"] == first_attempt["draft_id"]
    assert _status_for(
        connection, auth_context, first_attempt["draft_id"]
    ) == "submitted"
