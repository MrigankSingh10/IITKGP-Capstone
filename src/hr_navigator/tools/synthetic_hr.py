"""Read-only synthetic HR tools. Authentication must happen at the server boundary.

Never construct TrustedIdentity from model arguments or user-provided identity claims.
These adapters perform no authentication and must not be exposed directly to clients.
"""
from datetime import date, timedelta
import json
from pathlib import Path
import sqlite3

from pydantic import BaseModel, ConfigDict, Field


class ToolError(ValueError):
    """A request cannot be answered safely from the available fictional data."""


class TrustedIdentity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    employee_id: str = Field(min_length=1)


class EmployeeProfile(BaseModel):
    employee_id: str
    display_name: str
    state: str


class LeaveBalance(BaseModel):
    leave_type: str
    days: float


class LeaveCalculation(BaseModel):
    start: date
    end: date
    working_days: int
    policy_version: str
    holiday_state: str


class SyntheticHRTools:
    """Adapters for a pre-seeded, fictional database and the supplied handbook."""

    def __init__(self, connection: sqlite3.Connection, handbook_path: Path):
        self.connection = connection
        self.policy = json.loads(handbook_path.read_text(encoding="utf-8"))
        if self.policy.get("scope") != "internal fictional policy":
            raise ToolError("A synthetic handbook is required")

    def get_employee_profile(self, auth_context: TrustedIdentity) -> EmployeeProfile:
        if not isinstance(auth_context, TrustedIdentity):
            raise ToolError("Trusted server identity required")
        row = self.connection.execute(
            "SELECT e.id, e.display_name, d.state FROM employees e "
            "JOIN synthetic_employee_details d ON d.employee_id = e.id WHERE e.id = ?",
            (auth_context.employee_id,),
        ).fetchone()
        if row is None:
            raise ToolError("Employee profile unavailable")
        return EmployeeProfile(employee_id=row[0], display_name=row[1], state=row[2])

    def get_leave_balance(self, auth_context: TrustedIdentity, leave_type: str) -> LeaveBalance:
        self.get_employee_profile(auth_context)
        row = self.connection.execute(
            "SELECT days FROM leave_balances WHERE employee_id = ? AND leave_type = ?",
            (auth_context.employee_id, leave_type),
        ).fetchone()
        if row is None:
            raise ToolError("Leave balance unavailable")
        return LeaveBalance(leave_type=leave_type, days=row[0])

    def get_holidays(self, state: str, year: int, policy_version: str) -> list[date]:
        self._check_version(policy_version)
        calendar = self.policy.get("holidays", {})
        if state != calendar.get("state") or year != calendar.get("year"):
            raise ToolError("Holiday calendar unavailable for state and year")
        return [date.fromisoformat(item["date"]) for item in calendar["dates"]]

    def calculate_leave_days(
        self, start: date, end: date, state: str, policy_version: str
    ) -> LeaveCalculation:
        self._check_version(policy_version)
        if not isinstance(start, date) or not isinstance(end, date) or end < start:
            raise ToolError("Invalid date range")
        workweek = self.policy.get("workweek", {})
        if workweek.get("working_days") != ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"] or workweek.get("holidays_excluded") is not True:
            raise ToolError("Workweek policy unavailable or unsupported")
        # Validate every year first, including ranges that contain no weekdays.
        holidays = set()
        for year in range(start.year, end.year + 1):
            holidays.update(self.get_holidays(state, year, policy_version))
        count = 0
        current = start
        while current <= end:
            if current.weekday() < 5 and current not in holidays:
                count += 1
            if current == end:
                break
            current += timedelta(days=1)
        return LeaveCalculation(start=start, end=end, working_days=count,
                                policy_version=policy_version, holiday_state=state)

    def check_leave_balance(self, auth_context: TrustedIdentity, leave_type: str,
                            start: date, end: date, policy_version: str) -> LeaveCalculation:
        profile = self.get_employee_profile(auth_context)
        if leave_type not in ("annual", "sick") or not self.policy.get(f"{leave_type}_leave"):
            raise ToolError("Leave policy unavailable")
        calculation = self.calculate_leave_days(start, end, profile.state, policy_version)
        balance = self.get_leave_balance(auth_context, leave_type)
        if calculation.working_days > balance.days:
            raise ToolError("Insufficient leave balance")
        return calculation

    def _check_version(self, version: str) -> None:
        if not version or version != self.policy.get("version"):
            raise ToolError("Policy version unavailable")
