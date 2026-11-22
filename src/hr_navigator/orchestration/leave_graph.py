from langgraph.graph import StateGraph, START, END

from hr_navigator.orchestration.state import HRState
from hr_navigator.orchestration.leave_request_node import (
    leave_request_node,
)


def build_leave_graph():

    graph = StateGraph(HRState)

    # Register nodes
    graph.add_node(
        "leave_request",
        leave_request_node,
    )

    # Define workflow
    graph.add_edge(START, "leave_request")

    graph.add_conditional_edges(
        "leave_request",
        route_after_leave_request,
        {
            "clarification": END,
            "confirmation": END,
            "error": END,
        },
    )

    return graph.compile()


def route_after_leave_request(state: HRState):

    status = state.get("status")

    if status == "awaiting_confirmation":
        return "confirmation"

    if status == "needs_clarification":
        return "clarification"

    return "error"