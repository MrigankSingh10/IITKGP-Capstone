
from langgraph.runtime import Runtime

from hr_navigator.orchestration.state import HRState, HRContext


def submit_node(
    state: HRState,
    runtime: Runtime[HRContext],
) -> dict:
    """
    Submit the leave request after explicit employee confirmation.

    Services are injected through trusted runtime context.
    """

    if state.get("confirmation") != "confirm":
        return {
            "status": "error",
            "response": "Employee confirmation is missing.",
        }

    draft_id = state.get("draft_id")

    if not draft_id:
        return {
            "status": "error",
            "response": "Leave request draft ID is missing.",
        }

    services = runtime.context["services"]

    result = services.submit_confirmed_request(
        draft_id=draft_id,
        employee_context=state["auth_context"],
    )

    if not result.get("success"):
        return {
            "status": "error",
            "response": result.get(
                "error",
                "Leave request submission failed.",
            ),
        }

    return {
        "status": "submitted",
        "response": (
            "Your leave request has been submitted successfully."
        ),
        "request_id": result.get("request_id")
        or result.get("draft_id"),
    }
