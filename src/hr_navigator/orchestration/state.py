
from typing import TypedDict, Optional, Protocol


class HRState(TypedDict, total=False):
    # Conversation
    query: str
    intent: str
    response: str

    # Authenticated identity
    auth_context: dict

    # Leave details
    leave_type: str
    start_date: str
    end_date: str
    state: str
    year: int

    # Workflow results
    employee: dict
    leave_balance: float
    calculation: dict
    leave_draft: dict
    draft_id: str
    request_id: str

    # Human confirmation
    confirmation_required: bool
    confirmation: Optional[str]

    # Workflow control
    status: str
    error: Optional[str]
    retry_count: int


class LeaveServices(Protocol):
    """Trusted server-side leave submission services."""

    def register_draft_token(
        self,
        draft_id: str,
        approval_token: str,
    ) -> None:
        ...

    def submit_confirmed_request(
        self,
        draft_id: str,
        employee_context: dict,
    ) -> dict:
        ...


class HRContext(TypedDict):
    """Trusted dependencies supplied by the application server."""

    db_connection: object
    idempotency_key: str
    services: LeaveServices
