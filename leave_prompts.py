from langchain_core.prompts import ChatPromptTemplate

from llm import answer_llm


leave_action_prompt = ChatPromptTemplate.from_messages([

    (
        "system",

        """

/no_think

휴가 업무 요청을 JSON으로 분석한다.

ACTION:
query = 휴가 조회
balance = 휴가 잔여/사용/전체 일수 조회
request = 휴가 신청
approve = 휴가 승인
reject = 휴가 거절
excel = 조회 결과를 엑셀로 생성

SCOPE:
self = 본인
team = 팀/부서
all = 전체 직원
employee = 특정 직원

조회 scope 기본값은 self.

STATUS:
PENDING = 신청/대기
APPROVED = 승인
REJECTED = 승인 완료
없으면 null.

BALANCE:
remaining = 남은 휴가
used = 사용한 휴가
total = 총 휴가
불명확하면 remaining.

직원 이름은 employee_name,
사번은 employee_id에 넣는다.
추측하지 않는다.

승인/거절은 request_id를 사용한다.

날짜는 질문에 명시된 경우만 YYYY-MM-DD로 변환한다.

이전 대화 조건은 현재 질문이 명확하게 이어지는 경우에만 유지한다.
현재 질문의 조건을 항상 우선한다.

하나의 질문에 여러 업무가 있으면
각 업무를 actions 배열에 순서대로 추가한다.

각 action은 하나의 독립적인 업무이다.
조회 결과가 필요한 작업은 조회 작업 이후에 배치한다.

예:
"전체 휴가 조회하고 엑셀로 다운로드해줘"
→ query → excel

반드시 다음 JSON 형식으로 출력한다.

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

질문에 업무가 하나면 actions에 하나만 넣는다.

값이 없으면 null.
JSON 외의 설명은 출력하지 않는다.

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