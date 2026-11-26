
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from hr_navigator.orchestration.state import HRState
from hr_navigator.orchestration.leave_graph import (
    route_after_confirmation,
)
from hr_navigator.orchestration.nodes.confirmation_node import (
    confirmation_node,
)


def submit_test_node(state: HRState) -> dict:
    return {
        "status": "submitted",
        "response": "Leave request submitted.",
    }


def cancel_test_node(state: HRState) -> dict:
    return {
        "status": "cancelled",
        "response": "Leave request cancelled.",
    }


def build_confirmation_test_graph():
    builder = StateGraph(HRState)

    builder.add_node("confirmation", confirmation_node)
    builder.add_node("submit", submit_test_node)
    builder.add_node("cancel", cancel_test_node)

    builder.add_edge(START, "confirmation")

    builder.add_conditional_edges(
        "confirmation",
        route_after_confirmation,
        {
            "submit": "submit",
            "cancel": "cancel",
            "error": END,
        },
    )

    builder.add_edge("submit", END)
    builder.add_edge("cancel", END)

    return builder.compile(checkpointer=InMemorySaver())


def run_confirmation(decision: str):
    graph = build_confirmation_test_graph()

    config = {
        "configurable": {
            "thread_id": f"test-{decision}"
        }
    }

    initial_state = {
        "leave_draft": {"leave_type": "casual"},
        "confirmation_required": True,
    }

    # First invocation pauses at the confirmation interrupt.
    interrupted = graph.invoke(initial_state, config=config)

    assert "__interrupt__" in interrupted

    # Resume the graph with the employee's decision.
    result = graph.invoke(
        Command(resume=decision),
        config=config,
    )

    return result


def test_confirm_routes_to_submit():
    result = run_confirmation("confirm")

    assert result["confirmation"] == "confirm"
    assert result["status"] == "submitted"
    assert result["response"] == "Leave request submitted."


def test_cancel_routes_to_cancel():
    result = run_confirmation("cancel")

    assert result["confirmation"] == "cancel"
    assert result["status"] == "cancelled"
    assert result["response"] == "Leave request cancelled."
