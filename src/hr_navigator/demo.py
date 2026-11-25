"""Local-only routing and data access for the fictional Acme leave demo.

This module is intentionally separate from statutory-policy retrieval. It uses
only the repository's synthetic scenario fixtures and the existing employee
lookup tools; it is not an authentication or production HR integration.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path

from hr_navigator.db import migrate
from hr_navigator.tools.employee import get_employee_profile, get_leave_balance

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEMO_FIXTURES_PATH = PROJECT_ROOT / "evaluation" / "scenario_fixtures_v0.1.json"
DEFAULT_DEMO_DB_PATH = PROJECT_ROOT / "data" / "local" / "hr_navigator_demo.sqlite3"
DEFAULT_DEMO_EMPLOYEE_ID = "demo-001"
SUPPORTED_LEAVE_TYPES = ("annual", "sick")

_LEAVE_TERMS = re.compile(
    r"\b(?:leave|annual|sick|vacation|time[ -]?off|pto)\b", re.IGNORECASE
)
_BALANCE_TERMS = re.compile(
    r"\b(?:balance|balances|remaining|left|available|entitlement)\b",
    re.IGNORECASE,
)
_QUANTITY_TERMS = re.compile(
    r"\b(?:how many|how much|what is|what's|show|check)\b.*\b(?:days?|hours?)\b",
    re.IGNORECASE,
)


def is_leave_balance_question(query: str) -> bool:
    """Return True for natural-language questions asking about leave remaining."""
    return bool(_LEAVE_TERMS.search(query) and (
        _BALANCE_TERMS.search(query) or _QUANTITY_TERMS.search(query)
    ))


def requested_leave_type(query: str) -> str | None:
    """Return a specific supported leave type, or None for all leave types."""
    if re.search(r"\b(?:sick|medical)\b", query, re.IGNORECASE):
        return "sick"
    if re.search(
        r"\b(?:annual|vacation|earned|privilege|pto)\b", query, re.IGNORECASE
    ):
        return "annual"
    return None


def _load_demo_fixtures() -> dict:
    try:
        fixtures = json.loads(DEMO_FIXTURES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Synthetic demo fixtures could not be loaded") from exc

    if not str(fixtures.get("label", "")).startswith("SYNTHETIC"):
        raise RuntimeError("Refusing to load fixtures not labelled as synthetic")
    return fixtures


def connect_demo_database(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open and seed the local SQLite database with the fictional fixtures."""
    selected_path = Path(
        db_path or os.environ.get("HR_NAVIGATOR_DEMO_DB_PATH") or DEFAULT_DEMO_DB_PATH
    )
    selected_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(selected_path, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        migrate(connection)
        fixtures = _load_demo_fixtures()
        with connection:
            for employee in fixtures["employees"]:
                connection.execute(
                    """INSERT INTO employees (id, display_name) VALUES (?, ?)
                       ON CONFLICT(id) DO UPDATE SET display_name = excluded.display_name""",
                    (employee["id"], employee["display_name"]),
                )
            for balance in fixtures["leave_balances"]:
                connection.execute(
                    """INSERT INTO leave_balances (employee_id, leave_type, days)
                       VALUES (?, ?, ?)
                       ON CONFLICT(employee_id, leave_type)
                       DO UPDATE SET days = excluded.days""",
                    (balance["employee_id"], balance["leave_type"], balance["days"]),
                )
    except Exception:
        connection.close()
        raise
    return connection


def answer_leave_balance_question(
    query: str,
    employee_id: str | None,
) -> str:
    """Answer a leave-balance question using the existing employee tools."""
    selected_employee_id = (employee_id or DEFAULT_DEMO_EMPLOYEE_ID).strip()
    auth_context = {
        "employee_id": selected_employee_id,
        # This trusted context is synthetic demo plumbing, not real login auth.
        "authenticated": True,
    }

    connection = connect_demo_database()
    try:
        profile_result = get_employee_profile(connection, auth_context)
        if not profile_result.get("success"):
            return (
                f"I couldn't find fictional demo employee `{selected_employee_id}`. "
                "Choose demo-001, demo-002, demo-003, or demo-004 in the sidebar."
            )

        employee_name = profile_result["employee"]["display_name"]
        leave_type = requested_leave_type(query)
        leave_types = [leave_type] if leave_type else list(SUPPORTED_LEAVE_TYPES)
        balances: list[tuple[str, float]] = []

        for kind in leave_types:
            result = get_leave_balance(connection, auth_context, kind)
            if not result.get("success"):
                return (
                    f"I couldn't retrieve the simulated {kind} leave balance "
                    f"for `{selected_employee_id}`."
                )
            balances.append((result["leave_type"], float(result["balance_days"])))

        lines = [
            "**Simulated leave balance — fictional Acme demo data**",
            f"For **{employee_name}** (`{selected_employee_id}`):",
        ]
        for kind, days in balances:
            formatted_days = f"{days:g}"
            lines.append(f"- {kind.title()} leave: **{formatted_days} days**")
        lines.append(
            "\n*These balances are fictional test data for the local demo, "
            "not a real employee record or an official leave entitlement.*"
        )
        return "\n".join(lines)
    finally:
        connection.close()
