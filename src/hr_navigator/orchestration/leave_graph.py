
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

from hr_navigator.orchestration.state import HRState, HRContext

from hr_navigator.orchestration.nodes.leave_request_node import (
    leave_request_node,
)
from hr_navigator.orchestration.nodes.confirmation_node import (
    confirmation_node,
)
from hr_navigator.orchestration.nodes.submit_node import (
    submit_node,
)
from hr_navigator.orchestration.nodes.cancel_node import (
    cancel_node,
)


def route_after_leave_request(state: HRState) -> str:
    status = state.get("status")

    if status == "awaiting_confirmation":
        return "confirmation"

    if status == "needs_clarification":
        return "clarification"

    return "error"


def route_after_confirmation(state: HRState) -> str:
    decision = state.get("confirmation")

    if decision == "confirm":
        return "submit"

    if decision == "cancel":
        return "cancel"

    return "error"


def build_leave_graph(checkpointer=None):
    graph = StateGraph(
        HRState,
        context_schema=HRContext,
    )

    # Register nodes
    graph.add_node("leave_request", leave_request_node)
    graph.add_node("confirmation", confirmation_node)
    graph.add_node("submit", submit_node)
    graph.add_node("cancel", cancel_node)

    # Register edges
    graph.add_edge(START, "leave_request")

    graph.add_conditional_edges(
        "leave_request",
        route_after_leave_request,
        {
            "confirmation": "confirmation",
            "clarification": END,
            "error": END,
        },
    )

    graph.add_conditional_edges(
        "confirmation",
        route_after_confirmation,
        {
            "submit": "submit",
            "cancel": "cancel",
            "error": END,
        },
    )

    graph.add_edge("submit", END)
    graph.add_edge("cancel", END)

    # InMemorySaver is suitable for local development only.
    if checkpointer is None:
        checkpointer = InMemorySaver()

    return graph.compile(checkpointer=checkpointer)
