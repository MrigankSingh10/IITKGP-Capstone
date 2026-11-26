"""Trusted SQLite-backed services used by the leave-submission graph.

The raw confirmation token is kept only in this in-process service object.
SQLite stores only the token hash; it never stores the raw token.
"""

from __future__ import annotations

import threading
from typing import Any

from hr_navigator.tools.leave_requests import submit_leave_request


class SQLiteLeaveServices:
    """Implement the graph's trusted leave services using SQLite."""

    def __init__(self, connection):
        self._connection = connection
        self._approval_tokens: dict[str, str] = {}
        self._lock = threading.RLock()

    def register_draft_token(
        self,
        draft_id: str,
        approval_token: str,
    ) -> None:
        if not isinstance(draft_id, str) or not draft_id.strip():
            raise ValueError("Draft ID is required")
        if not isinstance(approval_token, str) or not approval_token:
            raise ValueError("Approval token is required")

        with self._lock:
            # An idempotent retry can rotate the token for an existing draft.
            self._approval_tokens[draft_id] = approval_token

    def submit_confirmed_request(
        self,
        draft_id: str,
        employee_context: dict,
    ) -> dict[str, Any]:
        with self._lock:
            approval_token = self._approval_tokens.get(draft_id)

        if not approval_token:
            return {
                "success": False,
                "error": (
                    "The confirmation token is no longer available in this "
                    "demo session. Create a new leave request before confirming."
                ),
            }

        result = submit_leave_request(
            connection=self._connection,
            auth_context=employee_context,
            draft_id=draft_id,
            approval_token=approval_token,
        )
        if result.get("success"):
            result.setdefault("request_id", result.get("draft_id") or draft_id)
        return result
