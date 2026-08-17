from typing import Literal, Optional
from pydantic import BaseModel


# ============================================================
# 휴가 요청 Action
# ============================================================

class LeaveAction(BaseModel):

    action: Literal[
        "query",
        "approve",
        "reject"
    ]

    request_id: Optional[int] = None

    status: Optional[str] = None

    # 조회 범위
    #
    # self     = 본인 휴가
    # team     = 팀/부서 휴가
    # all      = 전체 휴가
    # employee = 특정 직원 휴가
    #
    # 기본값은 self
    scope: Literal[
        "self",
        "team",
        "all",
        "employee"
    ] = "self"

    employee_id: Optional[str] = None

    start_date: Optional[str] = None

    end_date: Optional[str] = None


# ============================================================
# 휴가 조회 결과
# ============================================================

class LeaveItem(BaseModel):

    request_id: int

    employee_id: str

    name: str

    department: str

    position: str

    start_date: str

    end_date: str

    leave_days: int

    reason: str

    status: str


# ============================================================
# 휴가 Agent 응답
# ============================================================

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