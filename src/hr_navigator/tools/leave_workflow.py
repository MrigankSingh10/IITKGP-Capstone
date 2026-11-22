
"""Orchestrates handbook-based leave calculation and request drafting."""

from datetime import date
import sqlite3

from hr_navigator.tools.handbook_leave import (
    calculate_leave_from_handbook,
)

from hr_navigator.tools.leave_requests import (
    draft_leave_request,
)


def create_leave_draft(
    connection: sqlite3.Connection,
    auth_context: dict,
    leave_type: str,
    start_date: date,
    end_date: date,
    state: str,
    year: int,
    idempotency_key: str,
) -> dict:
    """
    Calculate leave using handbook rules and create a draft.

    This function does not submit or approve leave.
    """

    # Step 1: Calculate leave using handbook rules.
    calculation = calculate_leave_from_handbook(
        start=start_date,
        end=end_date,
        state=state,
        year=year,
    )

    # Stop if handbook or calculation validation fails.
    if not calculation.get("success"):
        return {
            "success": False,
            "stage": "calculation",
            "error": calculation.get("error"),
            "calculation": calculation,
        }

    # Step 2: Create a leave request draft.
    draft = draft_leave_request(
        connection=connection,
        auth_context=auth_context,
        leave_type=leave_type,
        calculation=calculation,
        idempotency_key=idempotency_key,
    )

    if not draft.get("success"):
        return {
            "success": False,
            "stage": "draft",
            "error": draft.get("error"),
            "calculation": calculation,
        }

    # Step 3: Return the calculation and draft for employee review.
    return {
        "success": True,
        "stage": "draft_created",
        "calculation": calculation,
        "draft": draft,
        "message": (
            "Leave draft created. "
            "Employee confirmation is required before submission."
        ),
    }
