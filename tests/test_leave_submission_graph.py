
import pytest

from langgraph.types import Command

from hr_navigator.orchestration.leave_graph import build_leave_graph


class FakeLeaveServices:
    """Test implementation of trusted leave services."""

    def __init__(self):
        self.tokens = {}
        self.submitted_drafts = []

    def register_draft_token(self, draft_id, approval_token):
        self.tokens[draft_id] = approval_token

    def submit_confirmed_request(
        self,
        draft_id,
        employee_context,
    ):
        token = self.tokens.get(draft_id)

        if not token:
            return {
                "success": False,
                "error": "Approval token not found.",
            }

        self.submitted_drafts.append(draft_id)

        return {
            "success": True,
            "draft_id": draft_id,
            "request_id": "REQ-001",
        }


@pytest.fixture
def services():
    return FakeLeaveServices()


@pytest.fixture
def runtime_context(services):
    return {
        "db_connection": object(),
        "idempotency_key": "test-idempotency-001",
        "services": services,
    }


def test_confirm_submits_leave_request(
    monkeypatch,
    services,
    runtime_context,
):
    from hr_navigator.orchestration.nodes import leave_request_node

    # Mock only draft creation; use the real graph,
    # confirmation node, router and submit node.
    def fake_create_leave_draft(**kwargs):
        return {
            "success": True,
            "calculation": {
                "success": True,
                "leave_days": 2,
            },
            "draft": {
                "draft_id": "DRAFT-001",
                "approval_token": "SECRET-TOKEN",
                "leave_type": "annual",
                "leave_days": 2,
            },
        }

    monkeypatch.setattr(
        leave_request_node,
        "create_leave_draft",
        fake_create_leave_draft,
    )

    graph = build_leave_graph()

    config = {
        "configurable": {
            "thread_id": "confirm-test-001",
        }
    }

    initial_state = {
        "auth_context": {
            "employee_id": "demo-001",
            "authenticated": True,
        },
        "leave_type": "annual",
        "start_date": "2027-01-25",
        "end_date": "2027-01-26",
        "state": "West Bengal",
        "year": 2027,
    }

    # Execute graph until employee confirmation is requested.
    interrupted = graph.invoke(
        initial_state,
        config=config,
        context=runtime_context,
    )

    assert "__interrupt__" in interrupted

    # Verify the draft ID is stored at the top level.
    assert interrupted["draft_id"] == "DRAFT-001"

    # Approval token must not be exposed in graph state.
    assert "approval_token" not in interrupted["leave_draft"]

    # Employee confirms submission.
    result = graph.invoke(
        Command(resume="confirm"),
        config=config,
        context=runtime_context,
    )

    assert result["confirmation"] == "confirm"
    assert result["status"] == "submitted"
    assert result["request_id"] == "REQ-001"

    # Verify trusted service was actually called.
    assert services.submitted_drafts == ["DRAFT-001"]


def test_cancel_does_not_submit_leave_request(
    monkeypatch,
    services,
    runtime_context,
):
    from hr_navigator.orchestration.nodes import leave_request_node

    def fake_create_leave_draft(**kwargs):
        return {
            "success": True,
            "calculation": {
                "success": True,
                "leave_days": 2,
            },
            "draft": {
                "draft_id": "DRAFT-002",
                "approval_token": "SECRET-TOKEN",
                "leave_type": "annual",
                "leave_days": 2,
            },
        }

    monkeypatch.setattr(
        leave_request_node,
        "create_leave_draft",
        fake_create_leave_draft,
    )

    graph = build_leave_graph()

    config = {
        "configurable": {
            "thread_id": "cancel-test-001",
        }
    }

    initial_state = {
        "auth_context": {
            "employee_id": "demo-001",
            "authenticated": True,
        },
        "leave_type": "annual",
        "start_date": "2027-01-25",
        "end_date": "2027-01-26",
        "state": "West Bengal",
        "year": 2027,
    }

    graph.invoke(
        initial_state,
        config=config,
        context=runtime_context,
    )

    result = graph.invoke(
        Command(resume="cancel"),
        config=config,
        context=runtime_context,
    )

    assert result["confirmation"] == "cancel"
    assert result["status"] == "cancelled"

    # Cancellation must never invoke submission.
    assert services.submitted_drafts == []
