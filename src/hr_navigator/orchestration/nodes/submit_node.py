def submit_node(state: dict, services) -> dict:
    """
    Submit the leave request after confirmation.
    """

    if state.get("confirmation") != "confirm":
        return {
            "status": "error",
            "response": "Employee confirmation is missing.",
        }

    # The service must retrieve the approval token from
    # trusted server-side storage, not from the LLM or UI.
    result = services.submit_confirmed_request(
        draft_id=state["draft_id"],
        employee_context=services.auth_context,
    )

    if not result.get("success"):
        return {
            "status": "error",
            "response": result.get("error", "Submission failed."),
        }

    return {
        "status": "submitted",
        "response": "Your leave request has been submitted successfully.",
        "request_id": result.get("request_id"),
    }