
import sqlite3

from datetime import date

from hr_navigator.db import migrate, seed_synthetic

from hr_navigator.tools.leave_calculator import calculate_leave_days

from hr_navigator.tools.leave_requests import (
    draft_leave_request,
    submit_leave_request,
    get_request_status,
    get_request_audit
)


# 1. Initialize database
connection = sqlite3.connect(":memory:")

migrate(connection)
seed_synthetic(connection)

# Give the synthetic employee a demonstration balance.
connection.execute("""
    UPDATE leave_balances
    SET leave_type = 'annual', days = 10
    WHERE employee_id = 'demo-001'
""")
connection.commit()


# 2. Authenticated employee context
auth_context = {
    "employee_id": "demo-001",
    "authenticated": True
}


# 3. Calculate leave days
calculation = calculate_leave_days(
    start=date(2027, 1, 25),
    end=date(2027, 1, 29),
    workweek={0, 1, 2, 3, 4},
    holidays={date(2027, 1, 26)},
    policy_version="0.1-draft"
)

print("Calculation:", calculation)


# 4. Create leave request draft
draft = draft_leave_request(
    connection=connection,
    auth_context=auth_context,
    leave_type="annual",
    calculation=calculation,
    idempotency_key="demo-request-001"
)

print("\nDraft:", draft)


# 5. Explicit employee confirmation
if draft["success"] and not draft.get("already_exists"):

    confirmation = input(
        "\nDo you confirm submission? (yes/no): "
    )

    if confirmation.strip().lower() == "yes":

        # In this local demonstration only, the token is
        # passed directly. Never send it to an LLM or log it.
        result = submit_leave_request(
            connection=connection,
            auth_context=auth_context,
            draft_id=draft["draft_id"],
            approval_token=draft["approval_token"]
        )

        print("\nSubmission:", result)

    else:
        print("\nRequest not submitted.")


# 6. Retrieve request status
status = get_request_status(
    connection,
    auth_context
)

print("\nRequest status:", status)


# 7. Retrieve audit history
if draft["success"] and not draft.get("already_exists"):
    audit = get_request_audit(
        connection,
        auth_context,
        draft["draft_id"]
    )

    print("\nAudit history:", audit)


connection.close()
