from langgraph.types import interrupt


def confirmation_node(state: dict) -> dict:
    """
    Pause the workflow until the employee confirms
    or cancels the proposed leave request.
    """

    decision = interrupt({
        "type": "leave_request_confirmation",
        "message": "Do you want to submit this leave request?",
        "draft": {
            "leave_type": state["leave_type"],
            "start_date": state["start_date"],
            "end_date": state["end_date"],
            "leave_days": state["calculation"]["leave_days"],
        },
        "options": ["confirm", "cancel"],
    })

    if decision not in ("confirm", "cancel"):
        return {
            "status": "invalid_confirmation",
            "response": "Please confirm or cancel the request.",
        }

    return {
        "confirmation": decision,
        "status": (
            "confirmed" if decision == "confirm"
            else "cancelled"
        ),
    }