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
너는 AX Company 관리자용 휴가 업무 Agent다.

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

approve
- 휴가 신청 승인

reject
- 휴가 신청 거절


============================================================
STATUS 규칙
============================================================

가장 중요한 규칙이다.

사용자가 다음과 같이 "신청" 또는 "대기" 상태의
휴가를 요청하면 status는 반드시 "PENDING"이다.

- 휴가 신청 목록
- 휴가 신청 내역
- 신청된 휴가
- 휴가 대기 목록
- 대기 중인 휴가
- 승인 대기 휴가
- 승인 대기 중인 휴가

예:

"휴가 신청 목록 보여줘"

→ status = "PENDING"


"휴가 대기 목록 보여줘"

→ status = "PENDING"


"신청된 휴가 보여줘"

→ status = "PENDING"


중요:
"휴가 신청 목록"은 전체 휴가 목록이 아니다.

"휴가 신청 목록"은 승인 대기(PENDING) 휴가 목록이다.


============================================================
APPROVED 규칙
============================================================

다음 표현은 status = "APPROVED"이다.

- 승인된 휴가
- 승인 완료된 휴가
- 승인된 휴가 목록
- 승인 완료된 휴가 목록


============================================================
REJECTED 규칙
============================================================

다음 표현은 status = "REJECTED"이다.

- 거절된 휴가
- 거절된 휴가 목록
- 반려된 휴가
- 반려된 휴가 목록


============================================================
전체 조회 규칙
============================================================

다음과 같이 사용자가 "전체" 또는 "모든" 휴가를
명확하게 요청한 경우에만 status = null이다.

- 전체 휴가
- 전체 휴가 목록
- 모든 휴가
- 모든 휴가 목록

예:

"전체 휴가 목록 보여줘"

→ status = null


"모든 휴가 보여줘"

→ status = null


중요:

"전체 휴가 목록"과 "휴가 신청 목록"은 서로 다르다.

전체 휴가 목록
→ status = null

휴가 신청 목록
→ status = "PENDING"


"전체 신청 내역"이라는 표현은 사용하지 않는다.
사용자가 전체를 의미하면 "전체 휴가 목록"으로 해석하고,
신청을 의미하면 "휴가 신청 목록"으로 해석한다.


============================================================
STATUS 우선순위
============================================================

사용자 요청에 상태를 나타내는 표현이 있다면
반드시 해당 상태를 사용한다.

1. 승인된 / 승인 완료 → APPROVED
2. 거절된 / 반려된 → REJECTED
3. 신청 / 대기 / 승인 대기 → PENDING
4. 전체 / 모든 → null


============================================================
직원 ID
============================================================

사용자가 직원 ID를 명확하게 입력한 경우에만 사용한다.

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

예:

"2026년 8월 휴가 보여줘"

정확한 날짜 범위로 변환할 수 없는 경우
start_date와 end_date는 null로 둔다.

날짜를 임의로 추측하지 않는다.


============================================================
승인 / 거절 규칙
============================================================

사용자가 명확한 신청번호를 말하면 request_id에 넣는다.

예:

"6번 승인해줘"

→

{{
    "action": "approve",
    "request_id": 6,
    "status": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


"신청번호 6번 승인해줘"

→

{{
    "action": "approve",
    "request_id": 6,
    "status": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


"6번 휴가 거절해줘"

→

{{
    "action": "reject",
    "request_id": 6,
    "status": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


============================================================
중요: 신청번호 추측 금지
============================================================

사용자가 신청번호를 명확하게 말하지 않은 경우
request_id를 절대로 추측하지 않는다.

예:

"이영희 휴가 승인해줘"

이 경우 특정 신청번호를 임의로 선택하지 않는다.

다음과 같이 반환한다.

{{
    "action": "approve",
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
휴가 신청 목록 보여줘

출력:

{{
    "action": "query",
    "request_id": null,
    "status": "PENDING",
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


사용자:
휴가 대기 목록 보여줘

출력:

{{
    "action": "query",
    "request_id": null,
    "status": "PENDING",
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


사용자:
신청된 휴가 보여줘

출력:

{{
    "action": "query",
    "request_id": null,
    "status": "PENDING",
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


사용자:
전체 휴가 보여줘

출력:

{{
    "action": "query",
    "request_id": null,
    "status": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


사용자:
전체 휴가 목록 보여줘

출력:

{{
    "action": "query",
    "request_id": null,
    "status": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


사용자:
모든 휴가 보여줘

출력:

{{
    "action": "query",
    "request_id": null,
    "status": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


사용자:
승인된 휴가 보여줘

출력:

{{
    "action": "query",
    "request_id": null,
    "status": "APPROVED",
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


사용자:
반려된 휴가 보여줘

출력:

{{
    "action": "query",
    "request_id": null,
    "status": "REJECTED",
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


사용자:
E001 휴가 신청 목록 보여줘

출력:

{{
    "action": "query",
    "request_id": null,
    "status": "PENDING",
    "employee_id": "E001",
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
    "request_id": 6,
    "status": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


사용자:
신청번호 6번 승인해줘

출력:

{{
    "action": "approve",
    "request_id": 6,
    "status": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null
}}


사용자:
이영희 휴가 승인해줘

출력:

{{
    "action": "approve",
    "request_id": null,
    "status": "PENDING",
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

    # LLM 결과가 객체인 경우 문자열로 변환
    if hasattr(result, "content"):
        result = result.content

    result = str(result).strip()

    # ```json 제거
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

    # JSON 추출
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

    # 혹시 LLM이 주석을 넣은 경우 제거
    json_text = re.sub(
        r",?\s*//.*",
        "",
        json_text
    )

    # HTML 주석 제거
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
        request_id=request_id,
        status=status,
        employee_id=employee_id,
        start_date=start_date,
        end_date=end_date
    )


# ============================================================
# 4. DB 결과 → LeaveItem
# ============================================================

def convert_leave_items(result) -> list[LeaveItem]:

    items = []

    if not result:
        return items

    for row in result:

        items.append(
            LeaveItem(
                request_id=int(row["request_id"]),
                employee_id=str(row["employee_id"]),
                name=str(row["name"]),
                department=str(row["department"]),
                start_date=str(row["start_date"]),
                end_date=str(row["end_date"]),
                leave_days=int(row["leave_days"]),
                reason=str(row["reason"] or ""),
                status=str(row["status"])
            )
        )

    return items


# ============================================================
# 5. Leave Agent
# ============================================================

def handle_leave(question: str):

    # ========================================================
    # STEP 1
    # 자연어 → JSON Action
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
            message="휴가 요청을 정확하게 분석하지 못했습니다."
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
            message="휴가 요청의 조건을 확인하지 못했습니다."
        ).model_dump()


    print("[LEAVE ACTION]")
    print(action.model_dump())


    # ========================================================
    # STEP 4
    # 휴가 조회
    # ========================================================

    if action.action == "query":

        result = get_leave_requests.invoke({

            "status": action.status,

            "employee_id": action.employee_id,

            "start_date": action.start_date,

            "end_date": action.end_date
        })

        print("[LEAVE TOOL RESULT]")
        print(result)


        # ----------------------------------------------------
        # DB 결과 → Schema
        # ----------------------------------------------------

        items = convert_leave_items(
            result
        )


        # ----------------------------------------------------
        # 제목
        # ----------------------------------------------------

        if action.status == "PENDING":

            title = "승인 대기 휴가 목록"

        elif action.status == "APPROVED":

            title = "승인된 휴가 목록"

        elif action.status == "REJECTED":

            title = "거절된 휴가 목록"

        else:

            title = "전체 휴가 목록"


        # ----------------------------------------------------
        # 응답
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
        print(response.model_dump())

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

            # 직원 ID가 있는 경우
            # 해당 직원의 승인 대기 휴가를 조회한다.
            if action.employee_id:

                result = get_leave_requests.invoke({

                    "status": "PENDING",

                    "employee_id": action.employee_id,

                    "start_date": action.start_date,

                    "end_date": action.end_date
                })

                items = convert_leave_items(result)

                return LeaveResponse(

                    type="leave_action",

                    action="approve",

                    title="승인할 휴가 선택",

                    count=len(items),

                    items=items,

                    success=False,

                    message=(
                        f"{action.employee_id}의 승인 대기 휴가가 "
                        f"{len(items)}건 있습니다. "
                        "신청번호를 지정해주세요."
                    )

                ).model_dump()


            # ------------------------------------------------
            # 이름만 들어온 경우
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
                    "승인 대기 휴가 목록을 먼저 조회한 후 "
                    "신청번호를 지정해주세요."
                )

            ).model_dump()


        # ----------------------------------------------------
        # 실제 승인 Tool 호출
        # ----------------------------------------------------

        print(
            f"[LEAVE APPROVE] request_id={request_id}"
        )

        result = approve_leave.invoke({
            "request_id": request_id
        })

        print("[LEAVE APPROVE RESULT]")
        print(result)


        # ----------------------------------------------------
        # Tool 결과 처리
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # 신청번호 없는 경우
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # 실제 거절 Tool 호출
        # ----------------------------------------------------

        print(
            f"[LEAVE REJECT] request_id={request_id}"
        )

        result = reject_leave.invoke({
            "request_id": request_id
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