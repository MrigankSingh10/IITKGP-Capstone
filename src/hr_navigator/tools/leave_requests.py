
"""
Leave request management for HR Policy Navigator.

Features:
1. Create a leave request draft.
2. Validate authenticated employee identity.
3. Validate leave balance.
4. Generate an action-bound confirmation token.
5. Submit only after explicit employee confirmation.
6. Prevent duplicate submissions using idempotency.
7. Maintain a durable audit trail.
8. Retrieve only the authenticated employee's requests.

All operations are simulated.
Submission is NOT leave approval.
"""

import hashlib
import hmac
import secrets
import sqlite3
import uuid

from datetime import date, datetime, timedelta, timezone
from typing import TypedDict


# ---------------------------------------------------------
# Authentication
# ---------------------------------------------------------

class AuthContext(TypedDict):
    employee_id: str
    authenticated: bool


def _validate_auth_context(auth_context: AuthContext) -> str:
    """Validate server-provided employee identity."""

    if not auth_context:
        raise PermissionError("Authentication context is missing")

    if not auth_context.get("authenticated"):
        raise PermissionError("Employee is not authenticated")

    employee_id = auth_context.get("employee_id")

    if not isinstance(employee_id, str) or not employee_id.strip():
        raise PermissionError("Authenticated employee ID is missing")

    return employee_id.strip()


# ---------------------------------------------------------
# Database initialization
# ---------------------------------------------------------

def initialize_request_tables(connection: sqlite3.Connection) -> None:
    """
    Create leave request and audit tables if they do not exist.

    Existing employee and leave balance tables are reused.
    """

    connection.execute("PRAGMA foreign_keys = ON")

    with connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS leave_requests (
                draft_id TEXT PRIMARY KEY,
                employee_id TEXT NOT NULL,
                leave_type TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                leave_days REAL NOT NULL CHECK(leave_days > 0),
                policy_version TEXT NOT NULL,
                status TEXT NOT NULL
                    CHECK(status IN ('draft', 'submitted', 'expired')),
                idempotency_key TEXT NOT NULL,
                approval_token_hash TEXT NOT NULL,
                approval_action TEXT NOT NULL,
                token_expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                submitted_at TEXT,
                UNIQUE(employee_id, idempotency_key),
                FOREIGN KEY(employee_id) REFERENCES employees(id)
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS leave_request_audit (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                draft_id TEXT NOT NULL,
                employee_id TEXT NOT NULL,
                action TEXT NOT NULL,
                event_time TEXT NOT NULL,
                details TEXT,
                FOREIGN KEY(draft_id) REFERENCES leave_requests(draft_id)
            )
        """)


# ---------------------------------------------------------
# Utility functions
# ---------------------------------------------------------

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_datetime(value: datetime) -> str:
    return value.isoformat()


def _hash_token(token: str) -> str:
    """Store only a hash of the confirmation token."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _audit(
    connection: sqlite3.Connection,
    draft_id: str,
    employee_id: str,
    action: str,
    details: str = ""
) -> None:
    """Record an auditable request event."""

    connection.execute(
        """
        INSERT INTO leave_request_audit (
            draft_id,
            employee_id,
            action,
            event_time,
            details
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            draft_id,
            employee_id,
            action,
            _format_datetime(_utc_now()),
            details
        )
    )


def _parse_date(value: str, field_name: str) -> date:
    """Validate ISO date input."""

    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an ISO date string")

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must use YYYY-MM-DD format"
        ) from exc


# ---------------------------------------------------------
# 1. Draft leave request
# ---------------------------------------------------------

def draft_leave_request(
    connection: sqlite3.Connection,
    auth_context: AuthContext,
    leave_type: str,
    calculation: dict,
    idempotency_key: str,
    approval_ttl_minutes: int = 10
) -> dict:
    """
    Create a leave request draft.

    The request is NOT submitted at this stage.

    The confirmation token must be delivered securely
    to the authenticated employee, outside the LLM context.

    Args:
        connection: SQLite database connection.
        auth_context: Authenticated employee context.
        leave_type: Annual leave, sick leave, etc.
        calculation: Successful result from leave_calculator.py.
        idempotency_key: Unique key for this draft operation.
        approval_ttl_minutes: Token validity period.

    Returns:
        Draft information and a one-time confirmation token.
    """

    employee_id = _validate_auth_context(auth_context)

    if not isinstance(leave_type, str) or not leave_type.strip():
        raise ValueError("Leave type is required")

    if not isinstance(calculation, dict) or calculation.get("success") is not True:
        raise ValueError("A successful leave calculation is required")

    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise ValueError("Idempotency key is required")

    if len(idempotency_key) > 128:
        raise ValueError("Idempotency key cannot exceed 128 characters")

    if (
        isinstance(approval_ttl_minutes, bool)
        or not isinstance(approval_ttl_minutes, int)
        or not 1 <= approval_ttl_minutes <= 60
    ):
        raise ValueError("Token expiry must be between 1 and 60 minutes")

    start = _parse_date(calculation.get("start_date"), "start_date")
    end = _parse_date(calculation.get("end_date"), "end_date")

    if start > end:
        raise ValueError("Start date cannot be after end date")

    leave_days = calculation.get("leave_days")
    policy_version = calculation.get("policy_version")

    if (
        isinstance(leave_days, bool)
        or not isinstance(leave_days, (int, float))
        or leave_days <= 0
    ):
        raise ValueError("Valid positive leave days are required")

    if (
        not isinstance(policy_version, str)
        or not policy_version.strip()
    ):
        raise ValueError("Policy version is required")

    leave_type = leave_type.strip()
    idempotency_key = idempotency_key.strip()

    initialize_request_tables(connection)

    # Verify employee exists.
    employee = connection.execute(
        "SELECT id FROM employees WHERE id = ?",
        (employee_id,)
    ).fetchone()

    if employee is None:
        return {
            "success": False,
            "error": "Authenticated employee does not exist"
        }

    # Check existing idempotency key.
    existing = connection.execute(
        """
        SELECT draft_id, status, leave_type, start_date,
               end_date, leave_days
        FROM leave_requests
        WHERE employee_id = ? AND idempotency_key = ?
        """,
        (employee_id, idempotency_key)
    ).fetchone()

    if existing:
        same_request = (
            existing[2].lower() == leave_type.lower()
            and existing[3] == start.isoformat()
            and existing[4] == end.isoformat()
            and existing[5] == leave_days
        )

        if not same_request:
            return {
                "success": False,
                "error": "Idempotency key was already used for another request"
            }

        return {
            "success": True,
            "already_exists": True,
            "draft_id": existing[0],
            "status": existing[1],
            "message": (
                "This request already exists. "
                "Use the original confirmation process; "
                "a new token has not been issued."
            )
        }

    # Check current leave balance.
    balance = connection.execute(
        """
        SELECT days
        FROM leave_balances
        WHERE employee_id = ?
        AND LOWER(leave_type) = LOWER(?)
        """,
        (employee_id, leave_type)
    ).fetchone()

    if balance is None:
        return {
            "success": False,
            "error": "Leave balance not found for this leave type"
        }

    available_balance = float(balance[0])

    if leave_days > available_balance:
        return {
            "success": False,
            "error": "Insufficient leave balance",
            "required_days": leave_days,
            "available_balance": available_balance
        }

    # Create draft and confirmation token.
    draft_id = str(uuid.uuid4())

    confirmation_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(confirmation_token)

    now = _utc_now()
    expires_at = now + timedelta(minutes=approval_ttl_minutes)

    with connection:
        connection.execute(
            """
            INSERT INTO leave_requests (
                draft_id,
                employee_id,
                leave_type,
                start_date,
                end_date,
                leave_days,
                policy_version,
                status,
                idempotency_key,
                approval_token_hash,
                approval_action,
                token_expires_at,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?)
            """,
            (
                draft_id,
                employee_id,
                leave_type,
                start.isoformat(),
                end.isoformat(),
                leave_days,
                policy_version.strip(),
                idempotency_key,
                token_hash,
                "submit_leave_request",
                _format_datetime(expires_at),
                _format_datetime(now)
            )
        )

        _audit(
            connection,
            draft_id,
            employee_id,
            "DRAFT_CREATED",
            f"Leave type: {leave_type}; days: {leave_days}"
        )

    return {
        "success": True,
        "draft_id": draft_id,
        "employee_id": employee_id,
        "leave_type": leave_type,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "leave_days": leave_days,
        "policy_version": policy_version,
        "status": "draft",
        "approval_required": True,
        "approval_token": confirmation_token,
        "token_expires_at": _format_datetime(expires_at),
        "message": (
            "Leave request draft created. "
            "Submission requires explicit employee confirmation."
        )
    }


# ---------------------------------------------------------
# 2. Submit leave request
# ---------------------------------------------------------

def submit_leave_request(
    connection: sqlite3.Connection,
    auth_context: AuthContext,
    draft_id: str,
    approval_token: str
) -> dict:
    """
    Submit a leave request after explicit confirmation.

    The token is:
    - Bound to the authenticated employee.
    - Bound to the specific draft.
    - Bound to the submit_leave_request action.
    - Time-limited.
    - Checked against its stored hash.

    Submission does NOT mean approval.
    """

    employee_id = _validate_auth_context(auth_context)

    if not isinstance(draft_id, str) or not draft_id.strip():
        raise ValueError("Draft ID is required")

    if not isinstance(approval_token, str) or not approval_token:
        raise PermissionError("Approval token is required")

    initialize_request_tables(connection)

    # Lock the transaction before validating and updating.
    connection.execute("BEGIN IMMEDIATE")

    try:
        row = connection.execute(
            """
            SELECT draft_id, leave_type, leave_days,
                   status, approval_token_hash,
                   approval_action, token_expires_at
            FROM leave_requests
            WHERE draft_id = ? AND employee_id = ?
            """,
            (draft_id, employee_id)
        ).fetchone()

        if row is None:
            connection.rollback()
            return {
                "success": False,
                "error": "Leave request not found"
            }

        (
            stored_draft_id,
            leave_type,
            leave_days,
            status,
            stored_token_hash,
            approval_action,
            token_expires_at
        ) = row

        supplied_hash = _hash_token(approval_token)

        if not hmac.compare_digest(stored_token_hash, supplied_hash):
            connection.rollback()
            return {
                "success": False,
                "error": "Invalid confirmation token"
            }

        if approval_action != "submit_leave_request":
            connection.rollback()
            return {
                "success": False,
                "error": "Confirmation token is not valid for this action"
            }

        # An identical retry after a successful submission is idempotent.
        if status == "submitted":
            connection.rollback()
            return {
                "success": True,
                "already_submitted": True,
                "draft_id": stored_draft_id,
                "status": "submitted",
                "approved": False,
                "message": "This request has already been submitted."
            }

        if status != "draft":
            connection.rollback()
            return {
                "success": False,
                "error": f"Request cannot be submitted from status: {status}"
            }

        expires_at = datetime.fromisoformat(token_expires_at)

        if _utc_now() >= expires_at:
            connection.execute(
                """
                UPDATE leave_requests
                SET status = 'expired'
                WHERE draft_id = ?
                """,
                (draft_id,)
            )

            _audit(
                connection,
                draft_id,
                employee_id,
                "DRAFT_EXPIRED",
                "Confirmation token expired"
            )

            connection.commit()

            return {
                "success": False,
                "error": "Confirmation token has expired",
                "status": "expired"
            }

        # Recheck balance immediately before submission.
        balance = connection.execute(
            """
            SELECT days
            FROM leave_balances
            WHERE employee_id = ?
            AND LOWER(leave_type) = LOWER(?)
            """,
            (employee_id, leave_type)
        ).fetchone()

        if balance is None or leave_days > float(balance[0]):
            connection.rollback()
            return {
                "success": False,
                "error": "Leave balance is insufficient at submission time"
            }

        submitted_at = _format_datetime(_utc_now())

        connection.execute(
            """
            UPDATE leave_requests
            SET status = 'submitted',
                submitted_at = ?
            WHERE draft_id = ?
            AND employee_id = ?
            AND status = 'draft'
            """,
            (submitted_at, draft_id, employee_id)
        )

        _audit(
            connection,
            draft_id,
            employee_id,
            "REQUEST_SUBMITTED",
            "Employee explicitly confirmed leave request"
        )

        connection.commit()

        return {
            "success": True,
            "draft_id": stored_draft_id,
            "status": "submitted",
            "submitted_at": submitted_at,
            "approval_required": True,
            "approved": False,
            "message": (
                "Leave request submitted successfully. "
                "It is awaiting approval. Submission is not approval."
            )
        }

    except Exception:
        connection.rollback()
        raise


# ---------------------------------------------------------
# 3. Get leave request status
# ---------------------------------------------------------

def get_request_status(
    connection: sqlite3.Connection,
    auth_context: AuthContext,
    draft_id: str = None
) -> dict:
    """
    Retrieve only the authenticated employee's leave requests.

    If draft_id is provided, retrieve one request.
    Otherwise, return all requests belonging to the employee.
    """

    employee_id = _validate_auth_context(auth_context)

    initialize_request_tables(connection)

    if draft_id is not None:
        rows = connection.execute(
            """
            SELECT draft_id, leave_type, start_date, end_date,
                   leave_days, policy_version, status,
                   created_at, submitted_at
            FROM leave_requests
            WHERE draft_id = ? AND employee_id = ?
            """,
            (draft_id, employee_id)
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT draft_id, leave_type, start_date, end_date,
                   leave_days, policy_version, status,
                   created_at, submitted_at
            FROM leave_requests
            WHERE employee_id = ?
            ORDER BY created_at DESC
            """,
            (employee_id,)
        ).fetchall()

    requests = [
        {
            "draft_id": row[0],
            "leave_type": row[1],
            "start_date": row[2],
            "end_date": row[3],
            "leave_days": row[4],
            "policy_version": row[5],
            "status": row[6],
            "created_at": row[7],
            "submitted_at": row[8],
            "approved": False if row[6] == "submitted" else None
        }
        for row in rows
    ]

    return {
        "success": True,
        "employee_id": employee_id,
        "requests": requests,
        "count": len(requests)
    }


# ---------------------------------------------------------
# 4. Get audit history
# ---------------------------------------------------------

def get_request_audit(
    connection: sqlite3.Connection,
    auth_context: AuthContext,
    draft_id: str
) -> dict:
    """
    Retrieve the audit history for the authenticated
    employee's own leave request.
    """

    employee_id = _validate_auth_context(auth_context)

    if not isinstance(draft_id, str) or not draft_id.strip():
        raise ValueError("Draft ID is required")

    initialize_request_tables(connection)

    # Verify ownership before exposing audit details.
    request = connection.execute(
        """
        SELECT draft_id
        FROM leave_requests
        WHERE draft_id = ? AND employee_id = ?
        """,
        (draft_id, employee_id)
    ).fetchone()

    if request is None:
        return {
            "success": False,
            "error": "Leave request not found"
        }

    rows = connection.execute(
        """
        SELECT action, event_time, details
        FROM leave_request_audit
        WHERE draft_id = ? AND employee_id = ?
        ORDER BY audit_id ASC
        """,
        (draft_id, employee_id)
    ).fetchall()

    return {
        "success": True,
        "draft_id": draft_id,
        "audit_history": [
            {
                "action": row[0],
                "event_time": row[1],
                "details": row[2]
            }
            for row in rows
        ]
    }
