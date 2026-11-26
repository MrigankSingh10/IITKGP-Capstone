import pytest
from datetime import date

from hr_navigator.tools.leave_calculator import calculate_leave_days


def test_weekdays_only():
    result = calculate_leave_days(
        start=date(2027, 1, 25),  # Monday
        end=date(2027, 1, 29),    # Friday
        workweek={0, 1, 2, 3, 4},
        holidays=set(),
        policy_version="0.1-draft",
    )

    assert result["success"] is True
    assert result["leave_days"] == 5
    assert len(result["chargeable_dates"]) == 5


def test_weekend_excluded():
    result = calculate_leave_days(
        start=date(2027, 1, 30),  # Saturday
        end=date(2027, 1, 31),    # Sunday
        workweek={0, 1, 2, 3, 4},
        holidays=set(),
        policy_version="0.1-draft",
    )

    assert result["leave_days"] == 0
    assert len(result["excluded_weekends"]) == 2


def test_holiday_excluded():
    result = calculate_leave_days(
        start=date(2027, 1, 25),
        end=date(2027, 1, 29),
        workweek={0, 1, 2, 3, 4},
        holidays={date(2027, 1, 26)},
        policy_version="0.1-draft",
    )

    assert result["leave_days"] == 4
    assert result["excluded_holidays"] == ["2027-01-26"]


def test_invalid_date_range():
    with pytest.raises(ValueError, match="Start date cannot be after end date"):
        calculate_leave_days(
            start=date(2027, 1, 29),
            end=date(2027, 1, 25),
            workweek={0, 1, 2, 3, 4},
            holidays=set(),
            policy_version="0.1-draft",
        )


def test_empty_policy_version():
    with pytest.raises(ValueError, match="Policy version is required"):
        calculate_leave_days(
            start=date(2027, 1, 25),
            end=date(2027, 1, 25),
            workweek={0, 1, 2, 3, 4},
            holidays=set(),
            policy_version="",
        )


def test_invalid_workweek():
    with pytest.raises(ValueError, match="Invalid workweek configuration"):
        calculate_leave_days(
            start=date(2027, 1, 25),
            end=date(2027, 1, 25),
            workweek={0, 7},
            holidays=set(),
            policy_version="0.1-draft",
        )


def test_invalid_holiday_type():
    with pytest.raises(ValueError, match="Invalid holiday date"):
        calculate_leave_days(
            start=date(2027, 1, 25),
            end=date(2027, 1, 25),
            workweek={0, 1, 2, 3, 4},
            holidays={"2027-01-25"},
            policy_version="0.1-draft",
        )


def test_calculation_is_not_approval():
    result = calculate_leave_days(
        start=date(2027, 1, 25),
        end=date(2027, 1, 25),
        workweek={0, 1, 2, 3, 4},
        holidays=set(),
        policy_version="0.1-draft",
    )

    assert result["approval_required"] is True
    assert result["approved"] is False
