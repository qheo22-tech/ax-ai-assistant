import json
import re

from leave_prompts import leave_action_chain

from leave_tools import (
    get_leave_requests,
    get_leave_balance,
    request_leave,
    approve_leave,
    reject_leave,
    find_employee,
    create_leave_excel
)

from leave_schema import (
    LeaveAction,
    LeaveItem,
    LeaveResponse
)

from leave_parser import parse_action_result
from leave_validator import validate_action
from leave_formatter import convert_leave_items


# ============================================================
# Leave Agent
# ============================================================

def handle_leave(
    question: str,
    actor_employee_id: str,
    request_id: int = None,
    previous_action: str = None,
    messages=None,
    last_result=None,
):

    # ========================================================
    # STEP 1
    # 자연어 → JSON
    # ========================================================

    if request_id is not None:

        # 이전 승인/거절 요청에 대한
        # 신청번호 선택이므로 LLM을 호출하지 않는다.

        action_data = {
            "action": previous_action,
            "scope": "employee",
            "request_id": request_id,
            "status": None,
            "employee_name": None,
            "employee_id": None,
            "start_date": None,
            "end_date": None,
            "balance_type": None
        }

        print("[LEAVE FOLLOWUP]")
        print(action_data)

    else:

        # ====================================================
        # 최근 대화
        # ====================================================

        history = ""

        if messages:

            history = "\n".join(
                f"{message['role']}: {message['content']}"
                for message in messages
            )

        # ====================================================
        # 이전 업무 결과
        # ====================================================

        previous_result = ""

        if last_result:

            previous_result = json.dumps(
                last_result,
                ensure_ascii=False
            )

        print("[LEAVE HISTORY]")
        print(history)

        print("[LEAVE PREVIOUS RESULT]")
        print(previous_result)

        raw_result = leave_action_chain.invoke({
            "question": question,
            "history": history,
            "previous_result": previous_result
        })

        print("[LEAVE ACTION RAW]")
        print(repr(raw_result))

        # ====================================================
        # STEP 2
        # JSON 파싱
        # ====================================================

        try:

            action_data = parse_action_result(
                raw_result
            )

        except Exception as e:

            print("[LEAVE ACTION ERROR]")
            print(e)

            return LeaveResponse(

                type="leave_action",

                action="query",

                title="휴가 요청 처리 실패",

                count=0,

                items=[],

                success=False,

                message=(
                    "휴가 요청을 정확하게 "
                    "분석하지 못했습니다."
                )

            ).model_dump()


    # ========================================================
    # STEP 3
    # Action 검증
    # ========================================================

    try:

        plan = validate_action(
            action_data
        )

        print("[LEAVE PLAN]")
        print(plan.model_dump())

        print("[LEAVE ACTION COUNT]")
        print(len(plan.actions))

        for i, action_item in enumerate(plan.actions):

            print(
                f"[LEAVE ACTION {i}]"
            )

            print(
                action_item.model_dump()
            )

        # ====================================================
        # 첫 번째 Action
        # ====================================================

        action = plan.actions[0]

        # ====================================================
        # Excel Action이 있는지 확인
        #
        # 예:
        #
        # actions:
        #   0 -> query
        #   1 -> excel
        #
        # ====================================================

        excel_action = next(
            (
                action_item
                for action_item in plan.actions
                if action_item.action == "excel"
            ),
            None
        )

        print("[LEAVE MAIN ACTION]")
        print(action.model_dump())

        print("[LEAVE EXCEL ACTION]")

        if excel_action:

            print(
                excel_action.model_dump()
            )

        else:

            print(None)

    except Exception as e:

        print("[LEAVE VALIDATION ERROR]")
        print(e)

        return LeaveResponse(

            type="leave_action",

            action="query",

            title="휴가 요청 처리 실패",

            count=0,

            items=[],

            success=False,

            message=(
                "휴가 요청의 조건을 "
                "확인하지 못했습니다."
            )

        ).model_dump()


    # ========================================================
    # 승인 / 거절 request_id 안전 검증
    # ========================================================

    if (
        action.action in ("approve", "reject")
        and request_id is None
    ):

        # 현재 질문에 사용자가 직접 번호를 말했는지 확인
        #
        # "23번 승인"
        # "23 승인"
        #
        # 둘 다 허용

        explicit_request_id = re.search(
            r"\b(\d+)(?:\s*번)?\b",
            question
        )

        if not explicit_request_id:

            # LLM이 과거 대화에서 임의로 추론한 번호는 제거

            if action.request_id is not None:

                print(
                    f"[REQUEST ID OVERRIDE] "
                    f"question={question!r}, "
                    f"llm_request_id={action.request_id} "
                    f"-> None"
                )

            action.request_id = None

        else:

            action.request_id = int(
                explicit_request_id.group(1)
            )


    # ========================================================
    # 조회 상태 보정
    # ========================================================

    if action.action == "query":

        normalized_question = question.replace(
            " ",
            ""
        )

        if "승인된" in normalized_question:

            action.status = "APPROVED"

        elif (
            "거절" in normalized_question
            or "반려" in normalized_question
        ):

            action.status = "REJECTED"

        elif "대기" in normalized_question:

            action.status = "PENDING"

        print("[LEAVE ACTION]")
        print(action.model_dump())


    # ========================================================
    # STEP 4
    # 휴가 일수 조회
    # ========================================================

    if action.action == "balance":

        print(
            f"[LEAVE BALANCE] "
            f"employee={actor_employee_id}, "
            f"balance_type={action.balance_type}"
        )

        result = get_leave_balance.invoke({

            "actor_employee_id":
                actor_employee_id

        })

        print("[LEAVE BALANCE RESULT]")
        print(result)

        if not isinstance(result, dict):

            return LeaveResponse(

                type="leave_action",

                action="balance",

                title="휴가 일수",

                count=0,

                items=[],

                success=False,

                message=(
                    "휴가 일수 조회 결과가 "
                    "올바르지 않습니다."
                )

            ).model_dump()


        if result.get("success") is False:

            return LeaveResponse(

                type="leave_action",

                action="balance",

                title="휴가 일수",

                count=0,

                items=[],

                success=False,

                message=result.get(
                    "message",
                    "휴가 일수를 조회하지 못했습니다."
                )

            ).model_dump()


        balance_type = action.balance_type


        if balance_type == "used":

            days = result.get(
                "used_days"
            )

            title = "사용한 휴가"

            message = (
                f"사용한 휴가는 "
                f"{days}일입니다."
            )


        elif balance_type == "total":

            days = result.get(
                "total_days"
            )

            title = "총 휴가"

            message = (
                f"총 휴가는 "
                f"{days}일입니다."
            )


        else:

            days = result.get(
                "remaining_days"
            )

            title = "남은 휴가"

            message = (
                f"남은 휴가는 "
                f"{days}일입니다."
            )


        if days is None:

            return LeaveResponse(

                type="leave_action",

                action="balance",

                title=title,

                count=0,

                items=[],

                success=False,

                message=(
                    f"{title} 조회 결과에 "
                    "일수 정보가 없습니다."
                )

            ).model_dump()


        response = LeaveResponse(

            type="leave_action",

            action="balance",

            title=title,

            count=0,

            items=[],

            success=True,

            message=message

        )

        print("[LEAVE AGENT]")
        print(response.model_dump())

        return response.model_dump()


    # ========================================================
    # STEP 5
    # 휴가 조회
    # ========================================================

    if action.action == "query":

        employee_id = action.employee_id

        print("[LEAVE QUERY]")

        print(
            f"scope={action.scope}, "
            f"employee_id={employee_id}, "
            f"status={action.status}, "
            f"actor={actor_employee_id}"
        )


        result = get_leave_requests.invoke({

            "status":
                action.status,

            "employee_id":
                employee_id,

            "start_date":
                action.start_date,

            "end_date":
                action.end_date,

            "actor_employee_id":
                actor_employee_id,

            "scope":
                action.scope

        })


        print("[LEAVE TOOL RESULT]")
        print(result)


        if (
            isinstance(result, dict)
            and "error" in result
        ):

            return LeaveResponse(

                type="leave_action",

                action="query",

                title="휴가 조회",

                count=0,

                items=[],

                success=False,

                message=result["error"]

            ).model_dump()


        items = convert_leave_items(
            result
        )


        # ====================================================
        # 제목
        # ====================================================

        if actor_employee_id == "E016":

            title_prefix = "전체"

        elif action.employee_id:

            title_prefix = action.employee_id

        elif action.scope == "self":

            title_prefix = "내"

        elif action.scope == "team":

            title_prefix = "팀원"

        elif action.scope == "all":

            title_prefix = "전체"

        else:

            title_prefix = "내"


        if action.status == "PENDING":

            title = (
                f"{title_prefix} "
                "승인 대기 휴가 목록"
            )

        elif action.status == "APPROVED":

            title = (
                f"{title_prefix} "
                "승인된 휴가 목록"
            )

        elif action.status == "REJECTED":

            title = (
                f"{title_prefix} "
                "거절된 휴가 목록"
            )

        else:

            title = (
                f"{title_prefix} "
                "휴가 목록"
            )


        # ====================================================
        # Query Response
        # ====================================================

        response = LeaveResponse(

            type="leave_list",

            action="query",

            title=title,

            count=len(items),

            items=items,

            success=True

        )


        print("[LEAVE AGENT]")
        print(response.model_dump())


        # ====================================================
        # STEP 5-1
        # Query + Excel 동시 요청
        #
        # 사용자가:
        #
        # "전체 휴가 목록 보여주고 엑셀로 다운로드해줘"
        #
        # 라고 했을 때 여기로 들어온다.
        # ====================================================

        if excel_action:

            print("[LEAVE EXCEL]")
            print(
                "Query 결과를 Excel로 생성합니다."
            )


            try:

                # LeaveItem → dict
                excel_items = [
                    item.model_dump()
                    for item in items
                ]


                print("[LEAVE EXCEL ITEMS]")
                print(excel_items)

                excel_result = create_leave_excel.invoke({
                    "leave_data": excel_items
                })


                print(
                    "[LEAVE EXCEL RESULT]"
                )

                print(
                    excel_result
                )


                # ====================================================
                # Excel 결과가 dict인 경우
                # ====================================================

                if isinstance(
                    excel_result,
                    dict
                ):

                    return {

                        "type":
                            "leave_list",

                        "action":
                            "excel",

                        "title":
                            title,

                        "count":
                            len(items),

                        "items":
                            excel_items,

                        "success":
                            excel_result.get(
                                "success",
                                True
                            ),

                        "message":
                            excel_result.get(
                                "message",
                                "엑셀 파일이 생성되었습니다."
                            ),

                        "file_path":
                            excel_result.get(
                                "file_path"
                            )

                    }


                # ====================================================
                # Excel 결과가 단순 파일 경로인 경우
                # ====================================================

                return {

                    "type":
                        "leave_list",

                    "action":
                        "excel",

                    "title":
                        title,

                    "count":
                        len(items),

                    "items":
                        excel_items,

                    "success":
                        True,

                    "message":
                        "엑셀 파일이 생성되었습니다.",

                    "file_path":
                        excel_result

                }


            except Exception as e:

                print(
                    "[LEAVE EXCEL ERROR]"
                )

                print(e)


                # 조회는 성공했지만
                # Excel 생성만 실패

                return {

                    "type":
                        "leave_list",

                    "action":
                        "query",

                    "title":
                        title,

                    "count":
                        len(items),

                    "items":
                        [
                            item.model_dump()
                            for item in items
                        ],

                    "success":
                        False,

                    "message":
                        (
                            "휴가 목록은 조회했지만 "
                            "엑셀 파일 생성에 실패했습니다."
                        )

                }


        # ====================================================
        # Excel 요청이 없는 일반 Query
        # ====================================================

        return response.model_dump()


    # ========================================================
    # STEP 6
    # 휴가 신청
    # ========================================================

    if action.action == "request":

        print(
            f"[LEAVE REQUEST] "
            f"employee={actor_employee_id}, "
            f"start={action.start_date}, "
            f"end={action.end_date}"
        )


        # ----------------------------------------------------
        # 날짜가 없는 경우
        # ----------------------------------------------------

        if (
            not action.start_date
            or not action.end_date
        ):

            response = LeaveResponse(

                type="leave_action",

                action="request",

                title="휴가 신청",

                count=0,

                items=[],

                success=False,

                message=(
                    "휴가 신청 날짜를 알려주세요. "
                    "예: 2026-08-25부터 "
                    "2026-08-26일까지 휴가 신청해줘"
                )

            )


            print("[LEAVE REQUEST]")
            print(
                "날짜가 없어 휴가 신청을 "
                "진행하지 않습니다."
            )

            print("[LEAVE AGENT]")
            print(response.model_dump())

            return response.model_dump()


        # ----------------------------------------------------
        # 날짜가 있는 경우
        # ----------------------------------------------------

        result = request_leave.invoke({

            "start_date":
                action.start_date,

            "end_date":
                action.end_date,

            "reason":
                "",

            "actor_employee_id":
                actor_employee_id

        })


        print("[LEAVE REQUEST RESULT]")
        print(result)


        # ----------------------------------------------------
        # Tool 결과 검증
        # ----------------------------------------------------

        if not isinstance(
            result,
            dict
        ):

            return LeaveResponse(

                type="leave_action",

                action="request",

                title="휴가 신청",

                count=0,

                items=[],

                success=False,

                message=(
                    "휴가 신청 처리 결과가 "
                    "올바르지 않습니다."
                )

            ).model_dump()


        # ----------------------------------------------------
        # 최종 Response
        # ----------------------------------------------------

        response = LeaveResponse(

            type="leave_action",

            action="request",

            title="휴가 신청",

            count=0,

            items=[],

            success=result.get(
                "success",
                False
            ),

            request_id=result.get(
                "request_id"
            ),

            message=result.get(
                "message"
            )

        )


        print("[LEAVE AGENT]")
        print(response.model_dump())

        return response.model_dump()


    # ========================================================
    # STEP 7
    # 휴가 승인
    # ========================================================

    if action.action == "approve":

        request_id = action.request_id


        # ====================================================
        # STEP 7-1
        # 신청번호가 없는 경우
        # ====================================================

        if request_id is None:

            # ------------------------------------------------
            # 이름으로 승인 요청한 경우
            # ------------------------------------------------

            if (
                action.employee_name
                and not action.employee_id
            ):

                employees = find_employee.invoke({

                    "name":
                        action.employee_name

                })


                print(
                    "[LEAVE EMPLOYEE SEARCH]"
                )

                print(
                    employees
                )


                # 직원 없음
                if not employees:

                    return LeaveResponse(

                        type="leave_action",

                        action="approve",

                        title="직원 조회",

                        count=0,

                        items=[],

                        success=False,

                        message=(
                            f"{action.employee_name} "
                            "직원을 찾을 수 없습니다."
                        )

                    ).model_dump()


                # 동명이인
                if len(employees) > 1:

                    employee_list = ", ".join(

                        f"{e['name']} "
                        f"({e['employee_id']}, "
                        f"{e['department']})"

                        for e in employees

                    )


                    return LeaveResponse(

                        type="leave_action",

                        action="approve",

                        title="직원 선택",

                        count=len(employees),

                        items=[],

                        success=False,

                        message=(
                            f"{action.employee_name} 직원이 "
                            f"{len(employees)}명 있습니다.\n"
                            f"{employee_list}\n"
                            "사번 또는 부서를 지정해주세요."
                        )

                    ).model_dump()


                # 이름이 유일하면 사번 확정

                action.employee_id = (
                    employees[0]["employee_id"]
                )


                print(
                    f"[LEAVE EMPLOYEE RESOLVED] "
                    f"{action.employee_name} "
                    f"-> {action.employee_id}"
                )


            # ------------------------------------------------
            # 사번이 확정된 경우
            # ------------------------------------------------

            if action.employee_id:

                result = get_leave_requests.invoke({

                    "status":
                        "PENDING",

                    "employee_id":
                        action.employee_id,

                    "start_date":
                        action.start_date,

                    "end_date":
                        action.end_date,

                    "actor_employee_id":
                        actor_employee_id,

                    "scope":
                        "employee"

                })


                print(
                    "[LEAVE APPROVE TARGET]"
                )

                print(
                    result
                )


                # Tool 에러
                if (
                    isinstance(result, dict)
                    and "error" in result
                ):

                    return LeaveResponse(

                        type="leave_action",

                        action="approve",

                        title="휴가 승인",

                        count=0,

                        items=[],

                        success=False,

                        message=result["error"]

                    ).model_dump()


                items = convert_leave_items(
                    result
                )


                # 승인할 휴가가 없음
                if not items:

                    return LeaveResponse(

                        type="leave_action",

                        action="approve",

                        title="휴가 승인",

                        count=0,

                        items=[],

                        success=False,

                        message=(
                            f"{action.employee_name or action.employee_id}"
                            "의 승인 대기 휴가가 없습니다."
                        )

                    ).model_dump()


                # 승인할 휴가가 여러 개이므로
                # 신청번호를 다시 받음

                return LeaveResponse(

                    type="leave_action",

                    action="approve",

                    title="승인할 휴가 선택",

                    count=len(items),

                    items=items,

                    success=False,

                    message=(
                        f"{action.employee_name or action.employee_id}의 "
                        f"승인 대기 휴가가 "
                        f"{len(items)}건 있습니다. "
                        "승인할 신청번호를 지정해주세요."
                    )

                ).model_dump()


            # ------------------------------------------------
            # 이름도 없고 사번도 없는 경우
            # ------------------------------------------------

            return LeaveResponse(

                type="leave_action",

                action="approve",

                title="휴가 승인",

                count=0,

                items=[],

                success=False,

                message=(
                    "승인할 휴가 신청번호가 필요합니다. "
                    "직원 이름 또는 신청번호를 지정해주세요."
                )

            ).model_dump()


        # ====================================================
        # STEP 7-2
        # 신청번호가 확정된 경우 → 실제 승인
        # ====================================================

        print(
            f"[LEAVE APPROVE] "
            f"request_id={request_id}"
        )


        result = approve_leave.invoke({

            "request_id":
                request_id,

            "actor_employee_id":
                actor_employee_id

        })


        print(
            "[LEAVE APPROVE RESULT]"
        )

        print(
            result
        )


        # Tool 결과 검증
        if not isinstance(
            result,
            dict
        ):

            return LeaveResponse(

                type="leave_action",

                action="approve",

                title="휴가 승인",

                count=0,

                items=[],

                success=False,

                request_id=request_id,

                message=(
                    "휴가 승인 결과가 올바르지 않습니다."
                )

            ).model_dump()


        # 최종 결과

        return LeaveResponse(

            type="leave_action",

            action="approve",

            title="휴가 승인",

            count=0,

            items=[],

            success=result.get(
                "success",
                False
            ),

            request_id=request_id,

            message=result.get(
                "message"
            )

        ).model_dump()


    # ========================================================
    # STEP 8
    # 휴가 거절
    # ========================================================

    if action.action == "reject":

        request_id = action.request_id


        if request_id is None:

            return LeaveResponse(

                type="leave_action",

                action="reject",

                title="휴가 거절",

                count=0,

                items=[],

                success=False,

                message=(
                    "거절할 휴가 신청번호가 필요합니다. "
                    "거절할 신청번호를 지정해주세요."
                )

            ).model_dump()


        print(
            f"[LEAVE REJECT] "
            f"request_id={request_id}"
        )


        result = reject_leave.invoke({

            "request_id":
                request_id,

            "actor_employee_id":
                actor_employee_id

        })


        print(
            "[LEAVE REJECT RESULT]"
        )

        print(
            result
        )


        if not isinstance(
            result,
            dict
        ):

            return LeaveResponse(

                type="leave_action",

                action="reject",

                title="휴가 거절",

                count=0,

                items=[],

                success=False,

                request_id=request_id,

                message=(
                    "휴가 거절 결과가 올바르지 않습니다."
                )

            ).model_dump()


        return LeaveResponse(

            type="leave_action",

            action="reject",

            title="휴가 거절",

            count=0,

            items=[],

            success=result.get(
                "success",
                False
            ),

            request_id=request_id,

            message=result.get(
                "message"
            )

        ).model_dump()


    # ========================================================
    # STEP 9
    # Excel 단독 요청
    # ========================================================

    if action.action == "excel":

        print(
            "[LEAVE EXCEL] "
            "Excel 단독 요청"
        )


        # Excel만 요청된 경우에도
        # 먼저 같은 조건으로 휴가를 조회한다.

        result = get_leave_requests.invoke({

            "status":
                action.status,

            "employee_id":
                action.employee_id,

            "start_date":
                action.start_date,

            "end_date":
                action.end_date,

            "actor_employee_id":
                actor_employee_id,

            "scope":
                action.scope

        })


        print(
            "[LEAVE EXCEL QUERY RESULT]"
        )

        print(
            result
        )


        if (
            isinstance(result, dict)
            and "error" in result
        ):

            return LeaveResponse(

                type="leave_action",

                action="query",

                title="엑셀 생성",

                count=0,

                items=[],

                success=False,

                message=result["error"]

            ).model_dump()


        items = convert_leave_items(
            result
        )


        excel_items = [
            item.model_dump()
            for item in items
        ]


        try:

            excel_result = create_leave_excel.invoke({

                "items":
                    excel_items

            })


            print(
                "[LEAVE EXCEL RESULT]"
            )

            print(
                excel_result
            )


            if isinstance(
                excel_result,
                dict
            ):

                return {

                    "type":
                        "leave_list",

                    "action":
                        "excel",

                    "title":
                        "휴가 목록 엑셀",

                    "count":
                        len(items),

                    "items":
                        excel_items,

                    "success":
                        excel_result.get(
                            "success",
                            True
                        ),

                    "message":
                        excel_result.get(
                            "message",
                            "엑셀 파일이 생성되었습니다."
                        ),

                    "file_path":
                        excel_result.get(
                            "file_path"
                        )

                }


            return {

                "type":
                    "leave_list",

                "action":
                    "excel",

                "title":
                    "휴가 목록 엑셀",

                "count":
                    len(items),

                "items":
                    excel_items,

                "success":
                    True,

                "message":
                    "엑셀 파일이 생성되었습니다.",

                "file_path":
                    excel_result

            }


        except Exception as e:

            print(
                "[LEAVE EXCEL ERROR]"
            )

            print(
                e
            )


            return {

                "type":
                    "leave_list",

                "action":
                    "excel",

                "title":
                    "휴가 목록 엑셀",

                "count":
                    len(items),

                "items":
                    excel_items,

                "success":
                    False,

                "message":
                    "엑셀 파일 생성에 실패했습니다."

            }


    # ========================================================
    # STEP 10
    # 예외
    # ========================================================

    return LeaveResponse(

        type="leave_action",

        action="query",

        title="휴가 요청 처리 실패",

        count=0,

        items=[],

        success=False,

        message="처리할 수 없는 휴가 요청입니다."

    ).model_dump()