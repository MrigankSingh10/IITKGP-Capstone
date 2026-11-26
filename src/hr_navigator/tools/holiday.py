
"""
Holiday calendar tool for HR Policy Navigator.

Source:
data/synthetic/acme_handbook_v0.1.json

This module returns only holidays documented in the
versioned synthetic HR handbook.
"""

import json
from datetime import date
from pathlib import Path
from typing import Optional


# Locate the project-level synthetic handbook.
PROJECT_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_HANDBOOK_PATH = (
    PROJECT_ROOT
    / "data"
    / "synthetic"
    / "acme_handbook_v0.1.json"
)


def get_holidays(
    state: str,
    year: int,
    handbook_path: Optional[Path] = None
) -> dict:
    """
    Retrieve holidays for a state and year.

    Args:
        state: State name, e.g. Karnataka.
        year: Calendar year, e.g. 2027.
        handbook_path: Optional custom handbook JSON path.

    Returns:
        Dictionary containing holiday information or
        an explicit unsupported-calendar response.
    """

    # Validate inputs.
    if not isinstance(state, str) or not state.strip():
        raise ValueError("State name is required")

    if isinstance(year, bool) or not isinstance(year, int):
        raise ValueError("Year must be an integer")

    if year < 1900 or year > 2100:
        raise ValueError("Invalid calendar year")

    state = state.strip()

    # Resolve handbook location.
    path = Path(handbook_path) if handbook_path else DEFAULT_HANDBOOK_PATH

    # Read handbook.
    try:
        with path.open("r", encoding="utf-8") as file:
            handbook = json.load(file)

    except FileNotFoundError:
        return {
            "success": False,
            "error": "Synthetic HR handbook not found",
            "holidays": []
        }

    except (json.JSONDecodeError, OSError):
        return {
            "success": False,
            "error": "Unable to read synthetic HR handbook",
            "holidays": []
        }

    # Extract holiday calendar.
    calendar = handbook.get("holidays")

    if not isinstance(calendar, dict):
        return {
            "success": False,
            "error": "Holiday calendar is missing or invalid",
            "holidays": []
        }

    # Check whether the requested calendar is documented.
    supported_state = calendar.get("state", "")
    supported_year = calendar.get("year")

    if (
        state.casefold() != supported_state.strip().casefold()
        or year != supported_year
    ):
        return {
            "success": False,
            "supported": False,
            "needs_clarification": True,
            "state": state,
            "year": year,
            "error": (
                "Holiday calendar is not documented for "
                f"{state}, {year}. Please clarify or escalate."
            ),
            "holidays": [],
            "policy_version": handbook.get("version")
        }

    # Extract and validate holiday dates.
    holiday_records = calendar.get("dates")

    if not isinstance(holiday_records, list):
        return {
            "success": False,
            "error": "Holiday date records are invalid",
            "holidays": []
        }

    holidays = []

    try:
        for record in holiday_records:
            holiday_date = date.fromisoformat(record["date"])

            if holiday_date.year != year:
                raise ValueError("Holiday year does not match calendar year")

            holidays.append({
                "date": holiday_date.isoformat(),
                "label": record.get("label", "Holiday")
            })

    except (KeyError, TypeError, ValueError):
        return {
            "success": False,
            "error": "Invalid holiday record in handbook",
            "holidays": []
        }

    # Remove duplicate dates and sort.
    unique_holidays = {
        item["date"]: item for item in holidays
    }

    sorted_holidays = sorted(
        unique_holidays.values(),
        key=lambda item: item["date"]
    )

    return {
        "success": True,
        "supported": True,
        "needs_clarification": False,
        "state": supported_state,
        "year": year,
        "holidays": sorted_holidays,
        "policy_version": handbook.get("version"),
        "source": {
            "file": "acme_handbook_v0.1.json",
            "section": "5"
        }
    }
