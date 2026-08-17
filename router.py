from langchain_core.prompts import ChatPromptTemplate

from llm import answer_llm


# ============================================================
# Router Prompt
# ============================================================

router_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """
사용자의 요청을 다음 세 가지 중 하나로 분류한다.

leave:
회사 휴가 업무에 관한 요청.

다음과 같은 요청은 leave다.
- 휴가 신청
- 휴가 취소
- 휴가 신청 목록 조회
- 휴가 신청자 조회
- 휴가자 조회
- 휴가 일정 조회
- 휴가 이력 조회
- 휴가 잔여 일수 조회
- 휴가 승인 상태 조회

general:
회사 시스템의 데이터를 조회하거나 변경하지 않는
일반적인 질문과 대화.

unknown:
사용자의 의도를 파악하기 어려워
leave 또는 general로 판단하기 어려운 경우.

중요:
휴가와 관련된 실제 회사 업무를 요청하는 경우
leave로 분류한다.

예시:

"내 휴가 이력 보여줘" → leave
"휴가 신청한 사람 누구야?" → leave
"휴가 신청 목록 보여줘" → leave
"누가 휴가 가?" → leave
"휴가 며칠 남았어?" → leave
"휴가 신청해줘" → leave
"휴가 취소해줘" → leave

"휴가가 뭐야?" → general
"연차가 뭐야?" → general
"휴가는 보통 언제 써?" → general
"안녕" → general

문맥 처리:

현재 질문이 짧거나 이전 대화를 참조하는 표현을 포함하면
이전 대화를 참고해서 분류한다.

예:

이전 대화:
user: 내 휴가 목록 보여줘
assistant: 내 휴가 목록을 조회했습니다.

현재 질문:
그중 승인된 것만 보여줘

→ leave


이전 대화:
user: 내 휴가 목록 보여줘
assistant: 내 휴가 목록을 조회했습니다.

현재 질문:
그중 대기중인 것만 보여줘

→ leave


"그중", "그것만", "이것만", "승인된 것", "대기중인 것",
"거절된 것"처럼 이전 결과를 가리키는 표현은
이전 대화와 연결해서 판단한다.


반드시 다음 중 하나만 출력한다.

leave
general
unknown
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


# ============================================================
# Router Chain
# ============================================================

router_chain = router_prompt | answer_llm


# ============================================================
# Route Question
# ============================================================

def route_question(question: str, messages=None):

    history = ""

    if messages:

        history = "\n".join(
            f"{message['role']}: {message['content']}"
            for message in messages
        )

    result = router_chain.invoke({
        "question": question,
        "history": history
    })

    print(f"[ROUTER HISTORY] {history}")
    print(f"[ROUTER RAW] {repr(result)}")

    route = result.content if hasattr(result, "content") else str(result)

    route = route.strip().lower()

    if route.startswith("leave"):
        return "leave"

    if route.startswith("unknown"):
        return "unknown"

    return "general"