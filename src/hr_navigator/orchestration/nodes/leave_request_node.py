
from datetime import date

from langgraph.runtime import Runtime

from hr_navigator.orchestration.state import HRState, HRContext
from hr_navigator.tools.leave_workflow import create_leave_draft


def leave_request_node(
    state: HRState,
    runtime: Runtime[HRContext],
) -> dict:
    """
    Prepare a leave-request draft.

    Does not submit or approve the request.
    Database connection and idempotency key are supplied
    through trusted server-side runtime context.
    """

    required_fields = [
        "auth_context",
        "leave_type",
        "start_date",
        "end_date",
        "state",
        "year",
    ]

    missing = [
        field for field in required_fields
        if state.get(field) is None
    ]

    if missing:
        return {
            "status": "needs_clarification",
            "response": (
                "Please provide the following details: "
                + ", ".join(missing)
            ),
        }

    try:
        start_date = date.fromisoformat(state["start_date"])
        end_date = date.fromisoformat(state["end_date"])

        if start_date > end_date:
            return {
                "status": "needs_clarification",
                "response": "Start date cannot be after end date.",
            }

        # Read trusted server-side dependencies.
        db_connection = runtime.context["db_connection"]
        idempotency_key = runtime.context["idempotency_key"]

        if not idempotency_key:
            return {
                "status": "error",
                "error": "Missing server-generated idempotency key.",
            }

        result = create_leave_draft(
            connection=db_connection,
            auth_context=state["auth_context"],
            leave_type=state["leave_type"],
            start_date=start_date,
            end_date=end_date,
            state=state["state"],
            year=state["year"],
            idempotency_key=idempotency_key,
        )

        if not result.get("success"):
            return {
                "status": "error",
                "error": result.get("error"),
                "calculation": result.get("calculation"),
            }

        return {
            "status": "awaiting_confirmation",
            "calculation": result["calculation"],
            "leave_draft": result["draft"],
            "confirmation_required": True,
            "response": (
                "Your leave request draft is ready. "
                "Please review the dates and leave days "
                "before confirming submission."
            ),
        }

    except ValueError as exc:
        return {
            "status": "needs_clarification",
            "response": str(exc),
        }
