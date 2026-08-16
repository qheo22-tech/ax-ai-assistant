from typing import Literal, Optional
from pydantic import BaseModel


class LeaveAction(BaseModel):
    action: Literal[
        "query",
        "approve",
        "reject"
    ]

    request_id: Optional[int] = None
    status: Optional[str] = None
    employee_id: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class LeaveItem(BaseModel):
    request_id: int
    employee_id: str
    name: str
    department: str
    start_date: str
    end_date: str
    leave_days: int
    reason: str
    status: str


class LeaveResponse(BaseModel):
    type: Literal[
        "leave_list",
        "leave_action"
    ]

    action: Literal[
        "query",
        "approve",
        "reject"
    ]

    title: str

    count: int = 0

    items: list[LeaveItem] = []

    success: Optional[bool] = None

    request_id: Optional[int] = None

    message: Optional[str] = None