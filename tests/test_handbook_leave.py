
from datetime import date

from hr_navigator.tools.handbook_leave import (
    calculate_leave_from_handbook,
)


def test_leave_calculation_uses_handbook():
    result = calculate_leave_from_handbook(
        start=date(2027, 1, 25),
        end=date(2027, 1, 29),
        state="Karnataka",
        year=2027,
    )

    assert result["success"] is True
    assert result["leave_days"] == 4
    assert result["policy_version"] == "0.1-draft"
    assert result["excluded_holidays"] == ["2027-01-26"]
    assert result["approved"] is False


def test_unsupported_state_does_not_calculate():
    result = calculate_leave_from_handbook(
        start=date(2027, 1, 25),
        end=date(2027, 1, 29),
        state="Odisha",
        year=2027,
    )

    assert result["success"] is False
    assert result["needs_clarification"] is True
