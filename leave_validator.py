import re

from leave_schema import LeaveAction, LeavePlan


# ============================================================
# 단일 Action 검증
# ============================================================

def validate_single_action(data: dict) -> LeaveAction:

    action = data.get("action")

    if action not in {
        "query",
        "balance",
        "request",
        "approve",
        "reject",
        "excel"
    }:
        action = "query"


    scope = data.get("scope")

    if scope not in {
        "self",
        "team",
        "all",
        "employee"
    }:
        scope = "self"


    request_id = data.get("request_id")

    if request_id is not None:

        try:
            request_id = int(request_id)

        except (ValueError, TypeError):
            request_id = None


    status = data.get("status")

    if status not in {
        "PENDING",
        "APPROVED",
        "REJECTED"
    }:
        status = None


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


    employee_name = data.get("employee_name")

    if employee_name:
        employee_name = str(
            employee_name
        ).strip()


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


    balance_type = data.get(
        "balance_type"
    )

    if balance_type not in {
        "remaining",
        "used",
        "total"
    }:
        balance_type = None


    if (
        action == "balance"
        and balance_type is None
    ):
        balance_type = "remaining"


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


# ============================================================
# 전체 Plan 검증
# ============================================================

def validate_action(data: dict) -> LeavePlan:

    actions = data.get("actions")

    if not isinstance(actions, list):
        raise ValueError(
            "actions가 리스트가 아닙니다."
        )

    if not actions:
        raise ValueError(
            "실행할 action이 없습니다."
        )

    validated_actions = []

    for action_data in actions:

        if not isinstance(action_data, dict):
            raise ValueError(
                "잘못된 action 형식입니다."
            )

        validated_actions.append(
            validate_single_action(
                action_data
            )
        )

    return LeavePlan(
        actions=validated_actions
    )