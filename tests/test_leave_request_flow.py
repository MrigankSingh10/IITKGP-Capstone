
import sqlite3
import pytest

from datetime import date

from hr_navigator.db import migrate, seed_synthetic
from hr_navigator.tools.leave_calculator import calculate_leave_days
from hr_navigator.tools.leave_requests import (
    draft_leave_request,
    submit_leave_request,
    get_request_status,
    get_request_audit,
)


@pytest.fixture
def test_db():
    """Create an isolated in-memory database for testing."""

    connection = sqlite3.connect(":memory:")

    migrate(connection)
    seed_synthetic(connection)

    # Check whether an annual leave balance already exists.
    existing_balance = connection.execute(
        """
        SELECT 1
        FROM leave_balances
        WHERE employee_id = ?
          AND leave_type = ?
        """,
        ("demo-001", "annual"),
    ).fetchone()

    if existing_balance:
        connection.execute(
            """
            UPDATE leave_balances
            SET days = 10
            WHERE employee_id = ?
              AND leave_type = ?
            """,
            ("demo-001", "annual"),
        )
    else:
        # Use the actual leave_balances table schema.
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(leave_balances)"
            ).fetchall()
        }

        required_columns = {"employee_id", "leave_type", "days"}

        if not required_columns.issubset(columns):
            connection.close()
            raise RuntimeError(
                f"Unexpected leave_balances schema: {columns}"
            )

        connection.execute(
            """
            INSERT INTO leave_balances
                (employee_id, leave_type, days)
            VALUES (?, ?, ?)
            """,
            ("demo-001", "annual", 10),
        )

    connection.commit()

    yield connection

    connection.close()


@pytest.fixture
def auth_context():
    """Synthetic authenticated employee context."""

    return {
        "employee_id": "demo-001",
        "authenticated": True,
    }


def test_leave_calculation():
    """Verify weekends and holidays are excluded."""

    calculation = calculate_leave_days(
        start=date(2027, 1, 25),
        end=date(2027, 1, 29),
        workweek={0, 1, 2, 3, 4},
        holidays={date(2027, 1, 26)},
        policy_version="0.1-draft",
    )

    assert calculation["success"] is True
    assert calculation["leave_days"] == 4


def test_leave_request_draft_and_submission(test_db, auth_context):
    """Verify leave draft creation and explicit submission."""

    calculation = calculate_leave_days(
        start=date(2027, 1, 25),
        end=date(2027, 1, 29),
        workweek={0, 1, 2, 3, 4},
        holidays={date(2027, 1, 26)},
        policy_version="0.1-draft",
    )

    # Create leave request draft.
    draft = draft_leave_request(
        connection=test_db,
        auth_context=auth_context,
        leave_type="annual",
        calculation=calculation,
        idempotency_key="pytest-request-001",
    )

    assert draft["success"] is True, (
        f"Draft creation failed: {draft}"
    )

    assert draft.get("draft_id")
    assert draft.get("approval_token")

    # Simulate explicit employee confirmation.
    result = submit_leave_request(
        connection=test_db,
        auth_context=auth_context,
        draft_id=draft["draft_id"],
        approval_token=draft["approval_token"],
    )

    assert result["success"] is True, (
        f"Submission failed: {result}"
    )

    # Verify request status.
    status = get_request_status(
        test_db,
        auth_context,
    )

    assert status is not None

    # Verify audit history.
    audit = get_request_audit(
        test_db,
        auth_context,
        draft["draft_id"],
    )

    assert audit is not None
    assert len(audit) > 0



def test_idempotent_draft_retry_reissues_confirmation_token(test_db, auth_context):
    """An active draft retry preserves the draft and returns a fresh token."""
    calculation = calculate_leave_days(
        start=date(2027, 1, 25),
        end=date(2027, 1, 26),
        workweek={0, 1, 2, 3, 4},
        holidays=set(),
        policy_version="0.1-draft",
    )

    first = draft_leave_request(
        connection=test_db,
        auth_context=auth_context,
        leave_type="annual",
        calculation=calculation,
        idempotency_key="pytest-idempotent-retry-001",
    )
    retry = draft_leave_request(
        connection=test_db,
        auth_context=auth_context,
        leave_type="annual",
        calculation=calculation,
        idempotency_key="pytest-idempotent-retry-001",
    )

    assert first["success"] is True
    assert retry["success"] is True
    assert retry["already_exists"] is True
    assert retry["draft_id"] == first["draft_id"]
    assert retry["approval_token"]
    assert retry["approval_token"] != first["approval_token"]

    old_token_result = submit_leave_request(
        connection=test_db,
        auth_context=auth_context,
        draft_id=first["draft_id"],
        approval_token=first["approval_token"],
    )
    assert old_token_result["success"] is False
    assert old_token_result["error"] == "Invalid confirmation token"

    new_token_result = submit_leave_request(
        connection=test_db,
        auth_context=auth_context,
        draft_id=retry["draft_id"],
        approval_token=retry["approval_token"],
    )
    assert new_token_result["success"] is True
    assert new_token_result["status"] == "submitted"
