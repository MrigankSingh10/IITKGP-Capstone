
"""Deterministic leave-day calculator for HR Policy Navigator."""

from datetime import date, datetime
from typing import Iterable


def calculate_leave_days(
    start: date,
    end: date,
    workweek: Iterable[int],
    holidays: Iterable[date],
    policy_version: str,
) -> dict:
    """
    Calculate chargeable leave days.

    Python weekday convention:
        Monday = 0
        Sunday = 6

    This function calculates working days only.
    It does not approve or submit a leave request.
    """

    if not isinstance(start, date) or isinstance(start, datetime):
        raise ValueError("Invalid start date")

    if not isinstance(end, date) or isinstance(end, datetime):
        raise ValueError("Invalid end date")

    if start > end:
        raise ValueError("Start date cannot be after end date")

    if not policy_version or not policy_version.strip():
        raise ValueError("Policy version is required")

    working_days = set(workweek)
    holiday_dates = set(holidays)

    if not working_days or not working_days.issubset(set(range(7))):
        raise ValueError("Invalid workweek configuration")

    if not all(isinstance(day, date) and not isinstance(day, datetime)
               for day in holiday_dates):
        raise ValueError("Invalid holiday date")

    chargeable_dates = []
    excluded_weekends = []
    excluded_holidays = []

    current = start

    while current <= end:

        if current.weekday() not in working_days:
            excluded_weekends.append(current.isoformat())

        elif current in holiday_dates:
            excluded_holidays.append(current.isoformat())

        else:
            chargeable_dates.append(current.isoformat())

        current = date.fromordinal(current.toordinal() + 1)

    return {
        "success": True,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "leave_days": len(chargeable_dates),
        "chargeable_dates": chargeable_dates,
        "excluded_weekends": excluded_weekends,
        "excluded_holidays": excluded_holidays,
        "policy_version": policy_version,
        "approval_required": True,
        "approved": False,
        "message": (
            "Calculation completed. This is not a leave approval."
        ),
    }

def validate_leave_balance(
    required_days: int,
    available_balance: float
) -> dict:

    if required_days < 0 or available_balance < 0:
        raise ValueError("Leave days and balance cannot be negative")

    sufficient = required_days <= available_balance

    return {
        "sufficient_balance": sufficient,
        "required_days": required_days,
        "available_balance": available_balance,
        "remaining_balance": (
            available_balance - required_days
            if sufficient else None
        )
    }    
