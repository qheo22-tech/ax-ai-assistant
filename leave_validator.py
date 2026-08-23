import re

from leave_schema import LeaveAction

# ============================================================
# 3. Action 검증
# ============================================================

def validate_action(data: dict) -> LeaveAction:

    # --------------------------------------------------------
    # Action
    # --------------------------------------------------------

    action = data.get("action")

    if action not in {
        "query",
        "balance",
        "request",
        "approve",
        "reject"
    }:
        action = "query"


    # --------------------------------------------------------
    # Scope
    # --------------------------------------------------------

    scope = data.get("scope")

    if scope not in {
        "self",
        "team",
        "all",
        "employee"
    }:
        scope = "self"


    # --------------------------------------------------------
    # Request ID
    # --------------------------------------------------------

    request_id = data.get("request_id")

    if request_id is not None:

        try:
            request_id = int(request_id)

        except (ValueError, TypeError):
            request_id = None


    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    status = data.get("status")

    if status not in {
        "PENDING",
        "APPROVED",
        "REJECTED"
    }:
        status = None


    # --------------------------------------------------------
    # Employee ID
    # --------------------------------------------------------

    employee_id = data.get("employee_id")

    if employee_id:

        employee_id = str(
            employee_id
        ).strip().upper()

        if not re.match(
            r"^E\d+$",
            employee_id
        ):
            employee_id = None


    # --------------------------------------------------------
    # Employee Name
    # --------------------------------------------------------

    employee_name = data.get("employee_name")

    if employee_name:
        employee_name = str(
            employee_name
        ).strip()            


    # --------------------------------------------------------
    # Start Date
    # --------------------------------------------------------

    start_date = data.get("start_date")

    if start_date:

        start_date = str(
            start_date
        ).strip()

        if not re.match(
            r"^\d{4}-\d{2}-\d{2}$",
            start_date
        ):
            start_date = None


    # --------------------------------------------------------
    # End Date
    # --------------------------------------------------------

    end_date = data.get("end_date")

    if end_date:

        end_date = str(
            end_date
        ).strip()

        if not re.match(
            r"^\d{4}-\d{2}-\d{2}$",
            end_date
        ):
            end_date = None


    # --------------------------------------------------------
    # Balance Type
    # --------------------------------------------------------

    balance_type = data.get(
        "balance_type"
    )

    if balance_type not in {
        "remaining",
        "used",
        "total"
    }:
        balance_type = None


    # --------------------------------------------------------
    # balance인 경우만 기본값 적용
    # --------------------------------------------------------

    if (
        action == "balance"
        and balance_type is None
    ):
        balance_type = "remaining"


    # --------------------------------------------------------
    # request에서는 balance_type을 사용하지 않음
    #
    # LeaveAction schema에서 None을 허용해야 함
    # --------------------------------------------------------

    if action == "request":
        balance_type = None


    return LeaveAction(

        action=action,

        scope=scope,

        request_id=request_id,

        status=status,

        employee_id=employee_id,

        employee_name=employee_name,

        start_date=start_date,

        end_date=end_date,

        balance_type=balance_type

    )
