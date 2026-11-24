from langgraph.types import interrupt

from hr_navigator.orchestration.state import HRState


def confirmation_node(state: HRState) -> dict:
    decision = interrupt({
        "type": "leave_request_confirmation",
        "message": "Do you want to submit this leave request?",
        "draft": state.get("leave_draft", {}),
        "options": ["confirm", "cancel"],
    })

    if decision not in ("confirm", "cancel"):
        return {
            "status": "invalid_confirmation",
            "confirmation": None,
            "response": "Please choose confirm or cancel.",
        }

    return {
        "confirmation": decision,
        "status": (
            "confirmed" if decision == "confirm"
            else "cancelled"
        ),
    }