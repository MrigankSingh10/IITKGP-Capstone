from typing import TypedDict, Optional, Any


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

    # Human confirmation
    confirmation_required: bool
    confirmed: bool

    # Workflow control
    status: str
    error: Optional[str]
    retry_count: int