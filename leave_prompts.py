from langchain_core.prompts import ChatPromptTemplate
from llm import answer_llm


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

balance
- 남은 휴가 조회
- 잔여 휴가 조회
- 연차 잔여일수 조회
- 휴가 며칠 남았는지 조회
- 올해 휴가 얼마나 남았는지 조회
- 휴가를 몇 일 사용할 수 있는지 조회
- 사용한 휴가 조회
- 사용 휴가 며칠인지 조회
- 지금까지 사용한 휴가 조회
- 올해 사용한 연차 조회
- 총 휴가 조회
- 올해 총 휴가가 며칠인지 조회

request
- 휴가 신청
- 휴가 내기
- 휴가 신청해줘
- 연차 신청
- 연차 신청해줘
- 휴가를 사용하고 싶다
- 휴가 가고 싶다
- 휴가 가고싶어

approve
- 휴가 신청 승인
- 휴가 승인
- 휴가 승인해줘

reject
- 휴가 신청 거절
- 휴가 거절
- 휴가 거절해줘


============================================================
이전 대화 문맥 처리
============================================================

현재 질문이 이전 대화를 가리키는 표현을 포함하거나,
현재 질문만으로 대상이나 조건이 충분하지 않은 경우
이전 대화를 참고해서 누락된 조건을 보완한다.

예를 들어 다음 표현은 이전 문맥을 참고할 수 있다.

- 그중
- 그것만
- 이것만
- 승인된 것만
- 대기 중인 것만
- 거절된 것만
- 그 사람
- 그 직원
- 그거
- 그 휴가

예:

이전 대화:
user: E001 휴가 목록 보여줘
assistant: E001 휴가 목록을 조회했습니다.

현재 질문:
승인된 것만 보여줘

출력:

{{
    "action": "query",
    "scope": "employee",
    "request_id": null,
    "status": "APPROVED",
    "employee_name": null,
    "employee_id": "E001",
    "start_date": null,
    "end_date": null,
    "balance_type": null
}}


예:

이전 대화:
user: 팀원 휴가 목록 보여줘
assistant: 팀원 휴가 목록을 조회했습니다.

현재 질문:
그중 대기 중인 것만 보여줘

출력:

{{
    "action": "query",
    "scope": "team",
    "request_id": null,
    "status": "PENDING",
    "employee_name": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null,
    "balance_type": null
}}


중요:

현재 질문에서 새로운 조건을 명확하게 지정한 경우
현재 질문의 조건을 우선한다.

현재 질문이 이전 대화와 관계없는 독립적인 요청이라면
이전 대화의 조건을 임의로 가져오지 않는다.

예:

이전 대화:
user: E001 휴가 목록 보여줘

현재 질문:
내 남은 휴가 며칠이야?

이 경우 이전 employee_id인 E001을 가져오지 않는다.

출력:

{{
    "action": "balance",
    "scope": "self",
    "request_id": null,
    "status": null,
    "employee_name": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null,
    "balance_type": "remaining"
}}


============================================================
날짜 문맥 처리 규칙
============================================================

이전 대화에 날짜가 존재하더라도
현재 질문에서 이전 날짜를 명시적으로 참조하지 않으면
그 날짜를 사용하지 않는다.

다음과 같이 이전 날짜를 명시적으로 가리키는 표현이
현재 질문에 있는 경우에만 이전 대화의 날짜를 사용할 수 있다.

- 그 날짜로
- 그날로
- 아까 말한 날짜로
- 방금 말한 날짜로
- 그 기간으로
- 위 날짜로

현재 질문이 단순히

"휴가 신청해줘"
"연차 신청해줘"
"휴가 내줘"
"휴가 가고 싶어"

처럼 독립적인 휴가 신청 요청인 경우,
이전 대화에 날짜가 있더라도 절대로 가져오지 않는다.

이 경우:

start_date = null
end_date = null

이다.


예:

이전 대화:
user: 20260823부터 20260823까지
assistant: 요청을 정확히 이해하지 못했습니다.

현재 질문:
휴가 신청해줘

출력:

{{
    "action": "request",
    "scope": "self",
    "request_id": null,
    "status": null,
    "employee_name": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null,
    "balance_type": null
}}


반면 현재 질문이 이전 날짜를 명시적으로 참조하면
이전 날짜를 사용할 수 있다.

예:

이전 대화:
user: 20260823부터 20260823까지

현재 질문:
그 날짜로 휴가 신청해줘

출력:

{{
    "action": "request",
    "scope": "self",
    "request_id": null,
    "status": null,
    "employee_name": null,
    "employee_id": null,
    "start_date": "2026-08-23",
    "end_date": "2026-08-23",
    "balance_type": null
}}


============================================================
ACTION 분류 핵심 규칙
============================================================

가장 먼저 사용자가 "무엇을 하려고 하는지" 판단한다.

[request]
새로운 휴가를 신청해달라는 요청이다.

- 휴가 신청해줘
- 연차 신청해줘
- 휴가 내줘
- 휴가 신청하고 싶어
- 연차 내고 싶어
- 휴가 가고 싶어

→ action = "request"


[query]
이미 존재하는 휴가 또는 휴가 신청 내역을
보여달라거나 조회해달라는 요청이다.

- 휴가 보여줘
- 휴가 목록 보여줘
- 휴가 내역 보여줘
- 신청휴가 보여줘
- 신청한 휴가 보여줘
- 내가 신청한 휴가 보여줘
- 휴가 신청 목록 보여줘
- 휴가 신청 내역 보여줘

→ action = "query"


[매우 중요]

"신청"이라는 단어만 보고 request로 판단하지 않는다.

조회 표현이 있으면 query이다.

"보여줘"
"조회해줘"
"목록 보여줘"
"내역 보여줘"
"알려줘"

→ query


새로운 신청을 요구하는 표현이면 request이다.

"신청해줘"
"신청하고 싶어"
"내줘"

→ request


예:

"신청휴가 보여줘"
→ query

"휴가 신청 목록 보여줘"
→ query

"휴가 신청해줘"
→ request


query에서 사용자가
"신청휴가", "신청한 휴가", "휴가 신청 목록"이라고 하면
status = "PENDING"으로 한다.

request의 status는 항상 null이다.


============================================================
BALANCE 분류
============================================================

사용자가 휴가 일수를 묻는 경우

action = "balance"

이다.

balance_type으로 어떤 휴가 일수를 묻는지 구분한다.


============================================================
BALANCE TYPE
============================================================

balance_type은 다음 중 하나를 사용한다.

remaining

- 남은 휴가
- 잔여 휴가
- 잔여 연차
- 휴가 며칠 남았어
- 몇 일 남았어
- 내가 쓸 수 있는 휴가
- 앞으로 사용할 수 있는 휴가


used

- 사용한 휴가
- 사용 휴가
- 사용 휴가 며칠이야
- 내가 사용한 휴가
- 지금까지 사용한 휴가
- 올해 사용한 휴가
- 사용한 연차
- 연차 몇 일 사용했어


total

- 총 휴가
- 올해 총 휴가
- 연차가 총 몇 일이야
- 전체 휴가 일수
- 부여된 휴가 일수


판단할 수 없는 경우 기본값은

balance_type = "remaining"

이다.


============================================================
BALANCE 예시
============================================================

사용자:
"내 남은 휴가 며칠이야"

출력:

{{
    "action": "balance",
    "scope": "self",
    "request_id": null,
    "status": null,
    "employee_name": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null,
    "balance_type": "remaining"
}}


사용자:
"휴가 며칠 남았어"

출력:

{{
    "action": "balance",
    "scope": "self",
    "request_id": null,
    "status": null,
    "employee_name": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null,
    "balance_type": "remaining"
}}


사용자:
"사용휴가 며칠이야"

출력:

{{
    "action": "balance",
    "scope": "self",
    "request_id": null,
    "status": null,
    "employee_name": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null,
    "balance_type": "used"
}}


사용자:
"내가 사용한 휴가 며칠이야"

출력:

{{
    "action": "balance",
    "scope": "self",
    "request_id": null,
    "status": null,
    "employee_name": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null,
    "balance_type": "used"
}}


사용자:
"올해 총 휴가가 며칠이야"

출력:

{{
    "action": "balance",
    "scope": "self",
    "request_id": null,
    "status": null,
    "employee_name": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null,
    "balance_type": "total"
}}


============================================================
휴가 제도 질문
============================================================

다음과 같이 휴가 제도나 승인 권한 자체를 묻는 질문은
query/request/approve/reject/balance로 분류하지 않는다.

- 휴가는 누가 승인해?
- 휴가 허락은 누가 해줘?
- 휴가 승인 권한이 누구에게 있어?
- 관리자가 휴가를 승인해?


============================================================
SCOPE 규칙
============================================================

조회 요청에는 scope를 판단한다.

가능한 scope:

self
- 본인 휴가

team
- 본인의 팀/부서 휴가

all
- 전체 직원의 휴가

employee
- 특정 직원 휴가


============================================================
기본값
============================================================

사용자가 단순히

"휴가 목록 보여줘"
"휴가 보여줘"
"휴가 내역 보여줘"
"휴가 목록 조회해줘"

라고 하면

scope = "self"

이다.

절대로 all로 해석하지 않는다.


============================================================
본인 휴가
============================================================

다음 표현은 scope = "self"

- 내 휴가
- 내 휴가 목록
- 내 휴가 내역
- 내가 신청한 휴가
- 내 신청 내역
- 내 휴가 보여줘


============================================================
팀원 휴가
============================================================

다음 표현은 scope = "team"

- 팀원 휴가
- 팀원 휴가 목록
- 우리 팀 휴가
- 우리팀 휴가
- 부서 휴가
- 개발팀 휴가
- 팀 휴가


============================================================
전체 휴가
============================================================

다음 표현은 scope = "all"

- 전체 휴가
- 전체 휴가 목록
- 모든 휴가
- 모든 직원 휴가
- 전 직원 휴가


============================================================
특정 직원
============================================================

사용자가 직원 ID를 명확하게 입력한 경우
employee_id에 넣는다.

예:

"E001 휴가 보여줘"

employee_id = "E001"
scope = "employee"

"E002 신청 목록 보여줘"

employee_id = "E002"
scope = "employee"
status = "PENDING"

직원 ID를 추측하지 않는다.


============================================================
STATUS 규칙
============================================================
action = "query"일 때만 status를 설정한다.

PENDING:
- 신청휴가
- 신청한 휴가
- 휴가 신청 목록
- 휴가 신청 내역
- 대기 중인 휴가
- 승인 대기 휴가

APPROVED:
- 승인된 휴가
- 승인 완료된 휴가

REJECTED:
- 거절된 휴가
- 반려된 휴가

상태 표현이 없으면:
status = null

action = "request"이면:
status = null

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

직원 ID를 추측하지 않는다.


============================================================
날짜
============================================================

사용자가 날짜를 명확하게 입력한 경우에만 사용한다.

날짜 형식은 반드시 YYYY-MM-DD를 사용한다.

예:

"2026-08-25부터 2026-08-26일까지 휴가 신청해줘"

start_date = "2026-08-25"
end_date = "2026-08-26"

정확한 날짜 범위로 변환할 수 없는 경우
start_date와 end_date는 null이다.

날짜를 임의로 추측하지 않는다.


============================================================
휴가 신청
============================================================

사용자가 휴가 신청을 요청하면

action = "request"

이다.

날짜가 없는 경우에도 action은 request이다.

balance_type은 휴가 신청에서는 항상 null이다.

예:

"휴가 신청해줘"

결과:

{{
    "action": "request",
    "scope": "self",
    "request_id": null,
    "status": null,
    "employee_name": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null,
    "balance_type": null
}}


예:

"휴가 가고 싶어"

결과:

{{
    "action": "request",
    "scope": "self",
    "request_id": null,
    "status": null,
    "employee_name": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null,
    "balance_type": null
}}


예:

"2026-08-25부터 2026-08-26일까지 휴가 신청해줘"

결과:

{{
    "action": "request",
    "scope": "self",
    "request_id": null,
    "status": null,
    "employee_name": null,
    "employee_id": null,
    "start_date": "2026-08-25",
    "end_date": "2026-08-26",
    "balance_type": null
}}


============================================================
승인
============================================================

승인은 최종적으로 신청번호(request_id)를 기준으로 처리한다.

사용자가 신청번호를 명확하게 말하면
request_id에 넣는다.

예:

"20번 휴가 승인해줘"

결과:

{{
    "action": "approve",
    "scope": "self",
    "request_id": 20,
    "status": null,
    "employee_name": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null,
    "balance_type": null
}}


사용자가 신청번호 대신 직원 이름을 말한 경우에는
employee_name에 이름을 넣는다.

예:

"서준호 휴가 승인해줘"

결과:

{{
    "action": "approve",
    "scope": "employee",
    "request_id": null,
    "status": "PENDING",
    "employee_name": "서준호",
    "employee_id": null,
    "start_date": null,
    "end_date": null,
    "balance_type": null
}}


중요:

직원 이름을 직원 ID로 추측하지 않는다.

예를 들어

"서준호 휴가 승인해줘"

라고 했을 때

employee_id = "E002"

처럼 임의로 변환하지 않는다.

employee_name에 "서준호"를 그대로 넣는다.

Agent가 DB를 조회하여 실제 employee_id를 확인한다.


============================================================
거절
============================================================

예:

"6번 거절해줘"

결과:

{{
    "action": "reject",
    "scope": "self",
    "request_id": 6,
    "status": null,
    "employee_name": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null,
    "balance_type": null
}}


============================================================
QUERY 예시
============================================================

사용자:
"휴가 목록 보여줘"

출력:

{{
    "action": "query",
    "scope": "self",
    "request_id": null,
    "status": null,
    "employee_name": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null,
    "balance_type": null
}}


사용자:
"휴가 신청 목록 보여줘"

출력:

{{
    "action": "query",
    "scope": "self",
    "request_id": null,
    "status": "PENDING",
    "employee_name": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null,
    "balance_type": null
}}


사용자:
"승인된 내 휴가 보여줘"

출력:

{{
    "action": "query",
    "scope": "self",
    "request_id": null,
    "status": "APPROVED",
    "employee_name": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null,
    "balance_type": null
}}


사용자:
"거절된 내 휴가 보여줘"

출력:

{{
    "action": "query",
    "scope": "self",
    "request_id": null,
    "status": "REJECTED",
    "employee_name": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null,
    "balance_type": null
}}


사용자:
"팀원 휴가 목록 보여줘"

출력:

{{
    "action": "query",
    "scope": "team",
    "request_id": null,
    "status": null,
    "employee_name": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null,
    "balance_type": null
}}


사용자:
"팀원 승인 대기 휴가 보여줘"

출력:

{{
    "action": "query",
    "scope": "team",
    "request_id": null,
    "status": "PENDING",
    "employee_name": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null,
    "balance_type": null
}}


사용자:
"전체 휴가 목록 보여줘"

출력:

{{
    "action": "query",
    "scope": "all",
    "request_id": null,
    "status": null,
    "employee_name": null,
    "employee_id": null,
    "start_date": null,
    "end_date": null,
    "balance_type": null
}}


사용자:
"E001 휴가 목록 보여줘"

출력:

{{
    "action": "query",
    "scope": "employee",
    "request_id": null,
    "status": null,
    "employee_name": null,
    "employee_id": "E001",
    "start_date": null,
    "end_date": null,
    "balance_type": null
}}


============================================================
출력 규칙
============================================================

반드시 JSON 하나만 출력한다.

Markdown을 사용하지 않는다.

설명하지 않는다.

주석을 넣지 않는다.

SQL을 생성하지 않는다.

JSON 이외의 문장을 출력하지 않는다.

반드시 다음 필드만 사용한다.

action
scope
request_id
status
employee_name
employee_id
start_date
end_date
balance_type
"""
    ),
    (
        "human",
        """
이전 대화:
{history}

현재 질문:
{question}
"""
    )
])



leave_action_chain = leave_action_prompt | answer_llm