def cancel_node(state: dict) -> dict:

    return {
        "status": "cancelled",
        "response": (
            "Your leave request was cancelled. "
            "It has not been submitted."
        ),
    }