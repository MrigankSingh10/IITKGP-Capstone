"""Unit tests for the concrete SQLite-backed leave graph service."""

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from hr_navigator.db import migrate, seed_scenario_fixtures
from hr_navigator.orchestration.services import SQLiteLeaveServices
from hr_navigator.tools.leave_calculator import calculate_leave_days
from hr_navigator.tools.leave_requests import draft_leave_request, get_request_status


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = PROJECT_ROOT / "evaluation" / "scenario_fixtures_v0.1.json"


@pytest.fixture
def leave_database():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    migrate(connection)
    seed_scenario_fixtures(connection, FIXTURE_PATH)
    try:
        yield connection
    finally:
        connection.close()


def test_sqlite_service_submits_confirmed_draft_to_database(leave_database):
    auth_context = {"employee_id": "demo-001", "authenticated": True}
    calculation = calculate_leave_days(
        start=date(2027, 1, 25),
        end=date(2027, 1, 26),
        workweek={0, 1, 2, 3, 4},
        holidays=set(),
        policy_version="0.1-draft",
    )
    draft = draft_leave_request(
        connection=leave_database,
        auth_context=auth_context,
        leave_type="annual",
        calculation=calculation,
        idempotency_key="sqlite-service-confirm-001",
    )
    assert draft["success"] is True

    services = SQLiteLeaveServices(leave_database)
    services.register_draft_token(draft["draft_id"], draft["approval_token"])
    result = services.submit_confirmed_request(draft["draft_id"], auth_context)

    assert result["success"] is True
    assert result["status"] == "submitted"
    assert result["request_id"] == draft["draft_id"]

    status = get_request_status(
        leave_database, auth_context, draft["draft_id"]
    )
    assert status["requests"][0]["status"] == "submitted"


def test_sqlite_service_fails_closed_without_a_confirmation_token(leave_database):
    services = SQLiteLeaveServices(leave_database)

    result = services.submit_confirmed_request(
        draft_id="unknown-draft",
        employee_context={
            "employee_id": "demo-001",
            "authenticated": True,
        },
    )

    assert result["success"] is False
    assert "confirmation token" in result["error"].lower()
