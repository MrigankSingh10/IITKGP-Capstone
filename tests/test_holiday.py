
import pytest

from hr_navigator.tools.holiday import get_holidays

result = get_holidays("Karnataka", 2027)

print(result)

def test_karnataka_2027_holidays():
    result = get_holidays("Karnataka", 2027)

    assert result["success"] is True
    assert result["supported"] is True
    assert len(result["holidays"]) == 2

    assert result["holidays"][0]["date"] == "2027-01-26"
    assert result["holidays"][1]["date"] == "2027-08-16"


def test_state_name_case_insensitive():
    result = get_holidays("karnataka", 2027)

    assert result["success"] is True


def test_unsupported_state():
    result = get_holidays("Odisha", 2027)

    assert result["success"] is False
    assert result["needs_clarification"] is True
    assert result["holidays"] == []


def test_unsupported_year():
    result = get_holidays("Karnataka", 2026)

    assert result["success"] is False
    assert result["needs_clarification"] is True


def test_empty_state():
    with pytest.raises(ValueError):
        get_holidays("", 2027)


def test_invalid_year():
    with pytest.raises(ValueError):
        get_holidays("Karnataka", "2027")
