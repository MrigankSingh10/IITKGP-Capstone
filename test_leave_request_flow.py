
"""
Complete local leave request workflow demonstration.

Modules used:
- db.py
- employee.py
- holiday.py
- leave_calculator.py
- leave_requests.py

All transactions are simulated.
"""

import sqlite3
from datetime import date

from hr_navigator.db import migrate, seed_synthetic

from hr_navigator.tools.employee import (
    get_employee_profile,
    get_leave_balance
)

from hr_navigator.tools.holiday import get_holidays

from hr_navigator.tools.leave_calculator import (
    calculate_leave_days
)

from hr_navigator.tools.leave_requests import (
    draft_leave_request,
    submit_leave_request,
    get_request_status,
    get_request_audit
)


def main():

    print("\n====================================")
    print(" HR POLICY NAVIGATOR")
    print(" LOCAL LEAVE REQUEST DEMONSTRATION")
    print("====================================\n")

    # -------------------------------------------------
    # STEP 1: Initialize database
    # -------------------------------------------------

    print("STEP 1: Initializing database...")

    connection = sqlite3.connect(":memory:")

    migrate(connection)
    seed_synthetic(connection)

    # Add a demonstration annual leave balance.
    # The existing seed provides only a 'demo' balance.

    connection.execute(
        """
        INSERT OR REPLACE INTO leave_balances
        (employee_id, leave_type, days)
        VALUES (?, ?, ?)
        """,
        ("demo-001", "annual", 10)
    )

    connection.commit()

    print("Database initialized successfully.")

    # -------------------------------------------------
    # STEP 2: Authenticate employee
    # -------------------------------------------------

    print("\nSTEP 2: Employee authentication context...")

    auth_context = {
        "employee_id": "demo-001",
        "authenticated": True
    }

    print("Employee ID:", auth_context["employee_id"])

    # -------------------------------------------------
    # STEP 3: Employee profile lookup
    # -------------------------------------------------

    print("\nSTEP 3: Retrieving employee profile...")

    profile = get_employee_profile(
        connection,
        auth_context
    )

    print("Employee profile:", profile)

    if not profile["success"]:
        print("Employee lookup failed.")
        connection.close()
        return

    # -------------------------------------------------
    # STEP 4: Retrieve leave balance
    # -------------------------------------------------

    print("\nSTEP 4: Checking annual leave balance...")

    balance_result = get_leave_balance(
        connection,
        auth_context,
        "annual"
    )

    print("Leave balance:", balance_result)

    if not balance_result["success"]:
        print("Unable to retrieve leave balance.")
        connection.close()
        return

    available_balance = balance_result["balance_days"]

    # -------------------------------------------------
    # STEP 5: Retrieve holiday calendar
    # -------------------------------------------------

    print("\nSTEP 5: Retrieving holiday calendar...")

    holiday_result = get_holidays(
        state="Karnataka",
        year=2027
    )

    print("Holiday information:", holiday_result)

    if not holiday_result["success"]:
        print("Holiday calendar unavailable.")
        connection.close()
        return

    holiday_dates = {
        date.fromisoformat(item["date"])
        for item in holiday_result["holidays"]
    }

    # -------------------------------------------------
    # STEP 6: Calculate leave days
    # -------------------------------------------------

    print("\nSTEP 6: Calculating leave days...")

    start_date = date(2027, 1, 25)
    end_date = date(2027, 1, 29)

    calculation = calculate_leave_days(
        start=start_date,
        end=end_date,
        workweek={0, 1, 2, 3, 4},
        holidays=holiday_dates,
        policy_version=holiday_result["policy_version"]
    )

    print("Leave calculation:", calculation)

    if not calculation["success"]:
        print("Leave calculation failed.")
        connection.close()
        return

    required_days = calculation["leave_days"]

    print("\nRequired leave days:", required_days)
    print("Available leave balance:", available_balance)

    if required_days > available_balance:
        print("Insufficient leave balance.")
        connection.close()
        return

    # -------------------------------------------------
    # STEP 7: Create leave request draft
    # -------------------------------------------------

    print("\nSTEP 7: Creating leave request draft...")

    draft = draft_leave_request(
        connection=connection,
        auth_context=auth_context,
        leave_type="annual",
        calculation=calculation,
        idempotency_key="demo-annual-leave-001"
    )

    print("Draft result:", draft)

    if not draft["success"]:
        print("Unable to create leave request.")
        connection.close()
        return

    if draft.get("already_exists"):
        print(
            "Existing draft found. "
            "Use a fresh idempotency key for a new demonstration."
        )
        connection.close()
        return

    draft_id = draft["draft_id"]

    # -------------------------------------------------
    # STEP 8: Explicit employee confirmation
    # -------------------------------------------------

    print("\nSTEP 8: Employee confirmation required.")

    print("------------------------------------")
    print("LEAVE REQUEST SUMMARY")
    print("------------------------------------")
    print("Employee:", profile["employee"]["display_name"])
    print("Leave type:", draft["leave_type"])
    print("Start date:", draft["start_date"])
    print("End date:", draft["end_date"])
    print("Leave days:", draft["leave_days"])
    print("Status:", draft["status"])
    print("Draft ID:", draft_id)
    print("------------------------------------")

    print(
        "Confirmation expires at:",
        draft["token_expires_at"]
    )

    confirmation = input(
        "\nDo you confirm submission? (yes/no): "
    )

    if confirmation.strip().lower() != "yes":

        print("\nEmployee did not confirm submission.")
        print("No submission operation was performed.")

        print("\nCurrent request status:")

        print(
            get_request_status(
                connection,
                auth_context,
                draft_id
            )
        )

        connection.close()
        return

    # -------------------------------------------------
    # STEP 9: Submit leave request
    # -------------------------------------------------

    print("\nSTEP 9: Submitting leave request...")

    submission = submit_leave_request(
        connection=connection,
        auth_context=auth_context,
        draft_id=draft_id,
        approval_token=draft["approval_token"]
    )

    print("Submission result:", submission)

    # -------------------------------------------------
    # STEP 10: Retrieve request status
    # -------------------------------------------------

    print("\nSTEP 10: Retrieving leave request status...")

    status = get_request_status(
        connection,
        auth_context,
        draft_id
    )

    print("Request status:", status)

    # -------------------------------------------------
    # STEP 11: Retrieve audit history
    # -------------------------------------------------

    print("\nSTEP 11: Retrieving audit history...")

    audit = get_request_audit(
        connection,
        auth_context,
        draft_id
    )

    print("Audit history:", audit)

    # -------------------------------------------------
    # STEP 12: Final summary
    # -------------------------------------------------

    print("\n====================================")
    print(" WORKFLOW EXECUTION COMPLETED")
    print("====================================")

    if submission["success"]:
        print("Request status: SUBMITTED")
        print("Approval status: PENDING")
        print("Approved:", submission["approved"])
    else:
        print("Submission unsuccessful:", submission["error"])

    print("====================================\n")

    connection.close()


if __name__ == "__main__":
    main()
