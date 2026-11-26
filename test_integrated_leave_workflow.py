
import sqlite3
from datetime import date

from hr_navigator.db import migrate, seed_synthetic

from hr_navigator.tools.employee import get_leave_balance

from hr_navigator.tools.leave_requests import (
    submit_leave_request,
    get_request_status,
)

from hr_navigator.tools.leave_workflow import create_leave_draft


# 1. Initialize database
connection = sqlite3.connect(":memory:")

migrate(connection)
seed_synthetic(connection)

# Add synthetic annual leave balance
connection.execute(
    """
    INSERT OR REPLACE INTO leave_balances
    (employee_id, leave_type, days)
    VALUES (?, ?, ?)
    """,
    ("demo-001", "annual", 10),
)
connection.commit()


# 2. Authenticated employee context
auth_context = {
    "employee_id": "demo-001",
    "authenticated": True,
}


# 3. Check current balance
balance = get_leave_balance(
    connection,
    auth_context,
    "annual",
)

print("\nCurrent balance:", balance)


# 4. Calculate leave and create draft through workflow
result = create_leave_draft(
    connection=connection,
    auth_context=auth_context,
    leave_type="annual",
    start_date=date(2027, 1, 25),
    end_date=date(2027, 1, 29),
    state="Karnataka",
    year=2027,
    idempotency_key="annual-demo-2027-001",
)

if not result["success"]:
    print("Workflow failed:", result)
    connection.close()
    raise SystemExit(1)


calculation = result["calculation"]
draft = result["draft"]


# 5. Show calculation to employee
print("\n--- Leave Calculation ---")
print("Required leave days:", calculation["leave_days"])
print("Chargeable dates:", calculation["chargeable_dates"])
print("Excluded holidays:", calculation["excluded_holidays"])
print("Policy version:", calculation["policy_version"])

print("\n--- Leave Draft ---")
print("Draft ID:", draft["draft_id"])
print("Leave type:", draft["leave_type"])
print("Status:", draft["status"])
print("Approval required:", draft["approval_required"])


# 6. Ask for explicit confirmation
confirmation = input(
    "\nDo you want to submit this leave request? (yes/no): "
).strip().lower()


if confirmation == "yes":

    submission = submit_leave_request(
        connection=connection,
        auth_context=auth_context,
        draft_id=draft["draft_id"],
        approval_token=draft["approval_token"],
    )

    print("\n--- Submission Result ---")
    print(submission)

else:
    print("\nSubmission cancelled.")
    print("The request remains a draft and has not been submitted.")


# 7. Retrieve request status
status = get_request_status(
    connection,
    auth_context,
    draft["draft_id"],
)

print("\n--- Final Request Status ---")
print(status)

connection.close()
