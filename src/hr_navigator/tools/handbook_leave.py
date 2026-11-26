
"""Connect handbook rules to the leave calculator."""

import json
from datetime import date
from pathlib import Path

from hr_navigator.tools.holiday import get_holidays
from hr_navigator.tools.leave_calculator import calculate_leave_days


DAY_NUMBERS = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}


def calculate_leave_from_handbook(
    start: date,
    end: date,
    state: str,
    year: int,
    handbook_path: Path | None = None,
) -> dict:
    """Calculate leave using workweek, holidays and version from handbook."""

    if handbook_path is None:
        project_root = Path(__file__).resolve().parents[3]
        handbook_path = (
            project_root / "data" / "synthetic" / "acme_handbook_v0.1.json"
        )

    try:
        with Path(handbook_path).open("r", encoding="utf-8") as file:
            handbook = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {
            "success": False,
            "error": "Unable to read handbook",
        }

    workweek_config = handbook.get("workweek", {})
    working_day_names = workweek_config.get("working_days", [])

    if not isinstance(working_day_names, list) or not working_day_names:
        return {
            "success": False,
            "error": "Handbook workweek configuration is missing or invalid",
        }

    if any(day not in DAY_NUMBERS for day in working_day_names):
        return {
            "success": False,
            "error": "Handbook contains an unsupported weekday",
        }

    holiday_result = get_holidays(
        state=state,
        year=year,
        handbook_path=handbook_path,
    )

    if not holiday_result.get("success"):
        return holiday_result

    if start.year != year or end.year != year:
        return {
            "success": False,
            "error": "Leave dates must belong to the requested calendar year",
        }

    holidays = {
        date.fromisoformat(item["date"])
        for item in holiday_result["holidays"]
    }

    result = calculate_leave_days(
        start=start,
        end=end,
        workweek={DAY_NUMBERS[day] for day in working_day_names},
        holidays=holidays,
        policy_version=handbook.get("version", ""),
    )

    result["handbook_source"] = "acme_handbook_v0.1.json"
    result["holiday_source"] = holiday_result.get("source")
    return result
