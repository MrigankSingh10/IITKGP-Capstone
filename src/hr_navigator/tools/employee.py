
"""Employee-specific tools for the HR Policy Navigator."""

import sqlite3
from typing import TypedDict


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

    if not employee_id or not employee_id.strip():
        raise PermissionError("Authenticated employee ID is missing")

    return employee_id.strip()


def get_employee_profile(
    connection: sqlite3.Connection,
    auth_context: AuthContext
) -> dict:
    """Retrieve the authenticated employee's profile."""

    employee_id = _validate_auth_context(auth_context)

    try:
        row = connection.execute(
            """
            SELECT id, display_name
            FROM employees
            WHERE id = ?
            """,
            (employee_id,)
        ).fetchone()

        if row is None:
            return {
                "success": False,
                "error": "Employee profile not found"
            }

        return {
            "success": True,
            "employee": {
                "employee_id": row[0],
                "display_name": row[1]
            }
        }

    except sqlite3.Error:
        return {
            "success": False,
            "error": "Unable to retrieve employee profile"
        }


def get_leave_balance(
    connection: sqlite3.Connection,
    auth_context: AuthContext,
    leave_type: str
) -> dict:
    """Retrieve the authenticated employee's leave balance."""

    employee_id = _validate_auth_context(auth_context)

    if not leave_type or not leave_type.strip():
        return {
            "success": False,
            "error": "Leave type is required"
        }

    try:
        row = connection.execute(
            """
            SELECT leave_type, days
            FROM leave_balances
            WHERE employee_id = ?
            AND LOWER(leave_type) = LOWER(?)
            """,
            (employee_id, leave_type.strip())
        ).fetchone()

        if row is None:
            return {
                "success": False,
                "error": "Leave balance not found"
            }

        return {
            "success": True,
            "employee_id": employee_id,
            "leave_type": row[0],
            "balance_days": row[1]
        }

    except sqlite3.Error:
        return {
            "success": False,
            "error": "Unable to retrieve leave balance"
        }
