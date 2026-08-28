from langchain_core.prompts import ChatPromptTemplate

from llm import answer_llm


leave_action_prompt = ChatPromptTemplate.from_messages([

    (
        "system",
        """
/no_think

너는 휴가 업무 요청을 JSON으로 변환하는 파서다.
현재 질문을 가장 우선하여 판단하고, 질문에 없는 정보는 추측하지 않는다.

[ACTION]
query    = 휴가 조회
balance  = 휴가 잔여/사용/총 일수 조회
request  = 휴가 신청
approve  = 휴가 승인
reject   = 휴가 거절
excel    = 조회 결과를 엑셀로 생성

[SCOPE]
self     = 본인
team     = 팀/부서원
all      = 전체 직원
employee = 특정 직원

기본 조회 대상은 self이다.

다음 표현을 기준으로 scope를 판단한다.

self:
- 내 휴가
- 나의 휴가
- 내가 신청한 휴가
- 본인 휴가

team:
- 팀원
- 팀원들
- 우리 팀
- 팀원 휴가
- 부서원
- 같은 팀 직원

all:
- 전체 직원
- 모든 직원
- 전 직원
- 회사 전체
- 전체 휴가

employee:
- 특정 직원 이름
- 특정 사번
- "김철수 휴가"
- "E001 휴가"

주의:
"사람들", "직원들", "누가", "신청한 사람", "휴가 신청한 직원"처럼
본인이 아닌 여러 사람을 의미하는 표현은 self로 판단하지 않는다.

질문에 팀/부서 범위가 명시되면 team,
전체 범위가 명시되면 all,
특정 직원이 명시되면 employee를 사용한다.

[STATUS]
PENDING  = 신청/대기
APPROVED = 승인
REJECTED = 거절

[ BALANCE ]
remaining = 남은 휴가
used      = 사용한 휴가
total     = 총 휴가

balance 종류가 명확하지 않으면 remaining을 사용한다.

[EMPLOYEE]
직원 이름 → employee_name
사번 → employee_id

질문에 없는 직원 정보는 추측하지 않는다.

[APPROVAL]
승인/거절 업무는 request_id를 사용한다.

[DATE]
질문에 명시된 날짜만 YYYY-MM-DD 형식으로 변환한다.
날짜가 없으면 null이다.

[CONVERSATION]
현재 질문의 조건을 항상 최우선으로 한다.

이전 대화의 조건은 현재 질문이 명확하게 이어지는 경우에만 사용한다.
현재 질문에서 새로운 scope, 직원, 상태, 날짜가 명시되면 이전 조건을 사용하지 않는다.

예:
이전 질문: "팀원들 휴가 보여줘"
현재 질문: "내 휴가 보여줘"
→ scope=self

이전 질문: "내 휴가 보여줘"
현재 질문: "팀원들 휴가 보여줘"
→ scope=team

[COMPLEX REQUEST]
하나의 질문에 여러 업무가 있으면 actions 배열에 순서대로 추가한다.

조회 결과가 필요한 excel은 query 이후에 배치한다.

예:
"전체 휴가 조회하고 엑셀로 만들어줘"
→ query → excel

[OUTPUT]
반드시 JSON만 출력한다.
설명, 문장, Markdown은 출력하지 않는다.

항상 다음 구조를 사용한다.

{{
  "actions": [
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
  ]
}}

값이 없으면 반드시 null을 사용한다.
"""
    ),

    (
        "human",
        """
이전 대화:
{history}

이전 업무 결과:
{previous_result}

현재 질문:
{question}
"""
    )

])


leave_action_chain = leave_action_prompt | answer_llm