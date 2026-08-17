import json
import re

from langchain_core.prompts import ChatPromptTemplate

from llm import answer_llm

from leave_tools import (
    get_leave_requests,
    approve_leave,
    reject_leave
)

from leave_schema import (
    LeaveAction,
    LeaveItem,
    LeaveResponse
)


# ============================================================
# 1. Leave Action 분석 Prompt
# ============================================================

leave_action_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """
너는 AX Company의 휴가 업무 Agent다.

사용자의 자연어 요청을 분석해서
휴가 업무 종류와 DB 처리에 필요한 조건을 JSON으로 만든다.


============================================================
가능한 ACTION
============================================================

query
- 휴가 목록 조회
- 휴가 신청 목록 조회
- 승인 대기 휴가 조회
- 승인된 휴가 조회
- 거절된 휴가 조회
- 전체 휴가 조회
- 내 휴가 조회
- 팀원 휴가 조회
- 특정 직원 휴가 조회

approve
- 휴가 신청 승인

reject
- 휴가 신청 거절

조회/승인/거절 이외의 질문
- "휴가는 누가 승인해?"
- "휴가 허락은 누가 해줘?"
- "휴가 승인 권한이 누구에게 있어?"
- "관리자가 휴가를 승인해?"

같이 휴가 제도나 승인 권한 자체를 묻는 질문은
query/approve/reject로 분류하지 않는다.


============================================================
SCOPE 규칙
============================================================

조회 요청에는 반드시 scope를 판단한다.

가능한 scope:

self
- 본인 휴가

team
- 본인의 팀/부서 휴가

all
- 전체 직원의 휴가


------------------------------------------------------------
기본값
------------------------------------------------------------

사용자가 단순히

"휴가 목록 보여줘"
"휴가 보여줘"
"휴가 내역 보여줘"
"휴가 목록 조회해줘"

라고 하면 반드시

scope = "self"

이다.

예:

"휴가 목록 보여줘"

→ scope = "self"


------------------------------------------------------------
본인 휴가
------------------------------------------------------------

다음 표현은 scope = "self"

- 내 휴가
- 내 휴가 목록
- 내 휴가 내역
- 내가 신청한 휴가
- 내 신청 내역
- 내 휴가 보여줘

예:

"내 휴가 목록 보여줘"

→ scope = "self"


------------------------------------------------------------
팀원 휴가
------------------------------------------------------------

다음 표현은 scope = "team"

- 팀원 휴가
- 팀원 휴가 목록
- 우리 팀 휴가
- 우리팀 휴가
- 부서 휴가
- 개발팀 휴가
- 팀 휴가

예:

"팀원 휴가 목록 보여줘"

→ scope = "team"


------------------------------------------------------------
전체 휴가
------------------------------------------------------------

다음 표현은 scope = "all"

- 전체 휴가
- 전체 휴가 목록
- 모든 휴가
- 모든 직원 휴가
- 전 직원 휴가

예:

"전체 휴가 목록 보여줘"

→ scope = "all"


중요:

"휴가 목록 보여줘"

는

scope = "self"

이다.

절대로 전체 휴가로 해석하지 않는다.


============================================================
특정 직원 조회
============================================================

사용자가 직원 ID를 명확하게 입력한 경우
employee_id에 넣는다.

예:

"E001 휴가 보여줘"

→ employee_id = "E001"

"E002 신청 목록 보여줘"

→ employee_id = "E002"
→ status = "PENDING"

직원 ID를 추측하지 않는다.

특정 직원 ID가 입력된 경우에도
scope는 별도로 판단한다.

기본적으로 scope = "self"를 사용해도 된다.

실제 조회 가능 여부는 DB Tool에서
로그인 사용자의 권한에 따라 검사한다.

즉,

"E003 휴가 보여줘"

→

{{
    "action": "query",
    "scope": "self",
    "request_id": null,
    "status": null,
    "employee_id": "E003",
    "start_date": null,
    "end_date": null
}}

로 출력한다.

MANAGER가 다른 팀 직원을 조회하는 경우
DB Tool에서 권한을 거부한다.

ADMIN은 특정 직원 조회가 가능하다.


============================================================
STATUS 규칙
============================================================

사용자가 상태를 명확하게 지정하면
반드시 해당 status를 사용한다.


------------------------------------------------------------
PENDING
------------------------------------------------------------

다음 표현은 status = "PENDING"

- 휴가 신청 목록
- 휴가 신청 내역
- 신청된 휴가
- 휴가 대기 목록
- 대기 중인 휴가
- 승인 대기 휴가
- 승인 대기 중인 휴가


------------------------------------------------------------
APPROVED
------------------------------------------------------------

다음 표현은 status = "APPROVED"

- 승인된 휴가
- 승인 완료된 휴가
- 승인된 휴가 목록
- 승인 완료된 휴가 목록


------------------------------------------------------------
REJECTED
------------------------------------------------------------

다음 표현은 status = "REJECTED"

- 거절된 휴가
- 거절된 휴가 목록
- 반려된 휴가
- 반려된 휴가 목록


------------------------------------------------------------
STATUS가 없는 경우
------------------------------------------------------------

상태를 지정하지 않은 경우

status = null

이다.

예:

"휴가 목록 보여줘"

→ scope = "self"
→ status = null

"내 휴가 보여줘"

→ scope = "self"
→ status = null

"전체 휴가 보여줘"

→ scope = "all"
→ status = null

"팀원 휴가 보여줘"

→ scope = "team"
→ status = null


============================================================
STATUS 우선순위
============================================================

1. 승인된 / 승인 완료 → APPROVED
2. 거절된 / 반려된 → REJECTED
3. 신청 / 대기 / 승인 대기 → PENDING
4. 상태 표현 없음 → null


============================================================
직원 ID
============================================================

직원 ID가 명확하게 입력된 경우에만 사용한다.

예:

"E001 휴가 보여줘"

→ employee_id = "E001"

"E002 신청 목록 보여줘"

→ employee_id = "E002"
→ status = "PENDING"

직원 ID를 추측하지 않는다.


============================================================
날짜
============================================================

사용자가 날짜를 명확하게 입력한 경우에만 사용한다.

날짜 형식은 반드시 YYYY-MM-DD를 사용한다.

정확한 날짜 범위로 변환할 수 없는 경우
start_date와 end_date는 null이다.

날짜를 임의로 추측하지 않는다.


============================================================
승인 / 거절
============================================================

사용자가 명확한 신청번호를 말하면
request_id에 넣는다.

예:

"6번 승인해줘"

→

{{
    "action": "approve",
    "scope": "self",
    "request_id": 6,
    "status": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


신청번호를 명확하게 말하지 않은 경우
request_id를 추측하지 않는다.

예:

"휴가 승인해줘"

→

{{
    "action": "approve",
    "scope": "self",
    "request_id": null,
    "status": "PENDING",
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


============================================================
출력 규칙
============================================================

반드시 JSON 하나만 출력한다.

Markdown을 사용하지 않는다.

설명하지 않는다.

주석을 넣지 않는다.

SQL을 생성하지 않는다.


JSON 형식:

{{
    "action": "query",
    "scope": "self",
    "request_id": null,
    "status": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


============================================================
QUERY 예시
============================================================

사용자:
휴가 목록 보여줘

출력:

{{
    "action": "query",
    "scope": "self",
    "request_id": null,
    "status": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


사용자:
내 휴가 목록 보여줘

출력:

{{
    "action": "query",
    "scope": "self",
    "request_id": null,
    "status": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


사용자:
휴가 신청 목록 보여줘

출력:

{{
    "action": "query",
    "scope": "self",
    "request_id": null,
    "status": "PENDING",
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


사용자:
승인된 내 휴가 보여줘

출력:

{{
    "action": "query",
    "scope": "self",
    "request_id": null,
    "status": "APPROVED",
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


사용자:
거절된 내 휴가 보여줘

출력:

{{
    "action": "query",
    "scope": "self",
    "request_id": null,
    "status": "REJECTED",
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


사용자:
팀원 휴가 목록 보여줘

출력:

{{
    "action": "query",
    "scope": "team",
    "request_id": null,
    "status": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


사용자:
팀원 승인 대기 휴가 보여줘

출력:

{{
    "action": "query",
    "scope": "team",
    "request_id": null,
    "status": "PENDING",
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


사용자:
전체 휴가 목록 보여줘

출력:

{{
    "action": "query",
    "scope": "all",
    "request_id": null,
    "status": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


사용자:
전체 승인된 휴가 보여줘

출력:

{{
    "action": "query",
    "scope": "all",
    "request_id": null,
    "status": "APPROVED",
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


사용자:
E001 휴가 목록 보여줘

출력:

{{
    "action": "query",
    "scope": "self",
    "request_id": null,
    "status": null,
    "employee_id": "E001",
    "start_date": null,
    "end_date": null
}}


사용자:
E002 신청 목록 보여줘

출력:

{{
    "action": "query",
    "scope": "self",
    "request_id": null,
    "status": "PENDING",
    "employee_id": "E002",
    "start_date": null,
    "end_date": null
}}


============================================================
APPROVE 예시
============================================================

사용자:
6번 승인해줘

출력:

{{
    "action": "approve",
    "scope": "self",
    "request_id": 6,
    "status": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


============================================================
REJECT 예시
============================================================

사용자:
6번 거절해줘

출력:

{{
    "action": "reject",
    "scope": "self",
    "request_id": 6,
    "status": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}
"""
    ),
    (
        "human",
        "{question}"
    )
])


leave_action_chain = leave_action_prompt | answer_llm


# ============================================================
# 2. JSON Parser
# ============================================================

def parse_action_result(result) -> dict:

    if hasattr(result, "content"):
        result = result.content

    result = str(result).strip()

    result = re.sub(
        r"```json\s*",
        "",
        result,
        flags=re.IGNORECASE
    )

    result = re.sub(
        r"```",
        "",
        result
    ).strip()

    match = re.search(
        r"\{.*\}",
        result,
        re.DOTALL
    )

    if not match:
        raise ValueError(
            f"JSON 결과를 찾을 수 없습니다: {result}"
        )

    json_text = match.group(0)

    json_text = re.sub(
        r",?\s*//.*",
        "",
        json_text
    )

    json_text = re.sub(
        r",?\s*<!--.*?-->",
        "",
        json_text,
        flags=re.DOTALL
    )

    return json.loads(json_text)


# ============================================================
# 3. Action 검증
# ============================================================

def validate_action(data: dict) -> LeaveAction:

    action = data.get("action")

    if action not in {
        "query",
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
        "all"
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
    # Date
    # --------------------------------------------------------

    start_date = data.get("start_date")

    if start_date:

        start_date = str(start_date)

        if not re.match(
            r"^\d{4}-\d{2}-\d{2}$",
            start_date
        ):
            start_date = None


    end_date = data.get("end_date")

    if end_date:

        end_date = str(end_date)

        if not re.match(
            r"^\d{4}-\d{2}-\d{2}$",
            end_date
        ):
            end_date = None


    return LeaveAction(

        action=action,

        scope=scope,

        request_id=request_id,

        status=status,

        employee_id=employee_id,

        start_date=start_date,

        end_date=end_date
    )


# ============================================================
# 4. DB 결과 → LeaveItem
# ============================================================

def convert_leave_items(
    result
) -> list[LeaveItem]:

    items = []

    if not result:
        return items


    for row in result:

        items.append(

            LeaveItem(

                request_id=int(
                    row["request_id"]
                ),

                employee_id=str(
                    row["employee_id"]
                ),

                name=str(
                    row["name"]
                ),

                department=str(
                    row["department"]
                ),

                position=str(
                    row["position"]
                ),

                start_date=str(
                    row["start_date"]
                ),

                end_date=str(
                    row["end_date"]
                ),

                leave_days=int(
                    row["leave_days"]
                ),

                reason=str(
                    row["reason"] or ""
                ),

                status=str(
                    row["status"]
                )
            )
        )

    return items


# ============================================================
# 5. Leave Agent
# ============================================================

def handle_leave(
    question: str,
    actor_employee_id: str
):

    # ========================================================
    # STEP 1
    # 자연어 → JSON
    # ========================================================

    raw_result = leave_action_chain.invoke({

        "question": question

    })


    print("[LEAVE ACTION RAW]")

    print(repr(raw_result))


    # ========================================================
    # STEP 2
    # JSON 파싱
    # ========================================================

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

        action = validate_action(
            action_data
        )

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


    print("[LEAVE ACTION]")

    print(
        action.model_dump()
    )


    # ========================================================
    # STEP 4
    # 휴가 조회
    # ========================================================

    if action.action == "query":

        # ----------------------------------------------------
        # 조회 대상
        #
        # 중요:
        # employee_id를 여기서 None으로 초기화하지 않는다.
        #
        # 특정 직원 ID가 있으면 그대로 Tool에 전달한다.
        # 없으면 None으로 전달한다.
        # ----------------------------------------------------

        employee_id = action.employee_id


        print("[LEAVE QUERY]")

        print(
            f"scope={action.scope}, "
            f"employee_id={employee_id}, "
            f"status={action.status}, "
            f"actor={actor_employee_id}"
        )


        # ----------------------------------------------------
        # DB Tool
        # ----------------------------------------------------

        result = get_leave_requests.invoke({

            "status": action.status,

            "employee_id": employee_id,

            "start_date": action.start_date,

            "end_date": action.end_date,

            "actor_employee_id": actor_employee_id,

            "scope": action.scope

        })


        print("[LEAVE TOOL RESULT]")

        print(result)


        # ----------------------------------------------------
        # DB Tool 오류 처리
        # ----------------------------------------------------

        if isinstance(result, dict) and "error" in result:

            return LeaveResponse(

                type="leave_action",

                action="query",

                title="휴가 조회",

                count=0,

                items=[],

                success=False,

                message=result["error"]

            ).model_dump()


        # ----------------------------------------------------
        # DB 결과 → Schema
        # ----------------------------------------------------

        items = convert_leave_items(
            result
        )


        # ----------------------------------------------------
        # 제목
        # ----------------------------------------------------

        # 특정 직원 조회
        if action.employee_id:

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


        # ----------------------------------------------------
        # Response
        # ----------------------------------------------------

        response = LeaveResponse(

            type="leave_list",

            action="query",

            title=title,

            count=len(items),

            items=items,

            success=True

        )


        print("[LEAVE AGENT]")

        print(
            response.model_dump()
        )


        return response.model_dump()


    # ========================================================
    # STEP 5
    # 승인
    # ========================================================

    if action.action == "approve":

        request_id = action.request_id


        # ----------------------------------------------------
        # 신청번호 없는 경우
        # ----------------------------------------------------

        if request_id is None:

            if action.employee_id:

                result = get_leave_requests.invoke({

                    "status": "PENDING",

                    "employee_id":
                        action.employee_id,

                    "start_date":
                        action.start_date,

                    "end_date":
                        action.end_date,

                    "actor_employee_id":
                        actor_employee_id,

                    "scope":
                        "team"

                })


                # 오류 처리
                if isinstance(result, dict) and "error" in result:

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


                return LeaveResponse(

                    type="leave_action",

                    action="approve",

                    title="승인할 휴가 선택",

                    count=len(items),

                    items=items,

                    success=False,

                    message=(

                        f"{action.employee_id}의 "
                        f"승인 대기 휴가가 "
                        f"{len(items)}건 있습니다. "

                        "신청번호를 지정해주세요."

                    )

                ).model_dump()


            return LeaveResponse(

                type="leave_action",

                action="approve",

                title="휴가 승인",

                count=0,

                items=[],

                success=False,

                message=(

                    "승인할 휴가 신청번호가 필요합니다. "

                    "승인 대기 휴가 목록을 먼저 조회한 후 "

                    "신청번호를 지정해주세요."

                )

            ).model_dump()


        # ----------------------------------------------------
        # 실제 승인
        # ----------------------------------------------------

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


        print("[LEAVE APPROVE RESULT]")

        print(result)


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
    # STEP 6
    # 거절
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

                    "거절할 휴가 "
                    "신청번호가 필요합니다. "

                    "거절할 신청번호를 "
                    "지정해주세요."

                )

            ).model_dump()


        # ----------------------------------------------------
        # 실제 거절
        # ----------------------------------------------------

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


        print("[LEAVE REJECT RESULT]")

        print(result)


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
    # STEP 7
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