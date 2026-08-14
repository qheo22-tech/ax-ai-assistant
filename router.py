from langchain_core.prompts import ChatPromptTemplate
from llm import answer_llm


# ============================================================
# Router Prompt
# ============================================================

router_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """
너는 AX Company AI 업무 시스템의 요청 의도를 분류하는 Router다.

사용자의 요청을 반드시 다음 세 가지 중 하나로 분류한다.

leave
employee
general


[leave]

휴가와 관련된 요청.

예:
- 내 휴가가 며칠 남았어?
- 휴가 이력 보여줘
- 내가 신청한 휴가 알려줘
- 8월 20일부터 22일까지 휴가 신청해줘
- 휴가 신청해줘
- 휴가 신청 취소해줘
- 내 휴가 상태가 어떻게 됐어?


[employee]

직원 및 인사 정보와 관련된 요청.

예:
- 내 부서가 어디야?
- 내 직급 알려줘
- 내 이메일 알려줘
- E001 직원 정보 알려줘
- 직원 정보를 조회해줘
- 우리 회사 직원 정보가 어떻게 돼?


[general]

그 외 모든 요청.

예:
- 안녕
- 오늘 뭐해?
- Python이 뭐야?
- Kubernetes가 뭐야?
- FastAPI가 뭐야?
- LangChain이 뭐야?


[중요]

휴가와 관련된 요청은 leave로 분류한다.

직원 개인정보, 부서, 직급, 이메일 등
인사 정보와 관련된 요청은 employee로 분류한다.

그 외 요청은 general로 분류한다.


반드시 다음 세 단어 중 하나만 출력한다.

leave
employee
general

다른 설명은 절대 출력하지 않는다.
"""
    ),
    (
        "human",
        "{question}"
    )
])


# ============================================================
# Router Chain
# ============================================================

router_chain = router_prompt | answer_llm


# ============================================================
# Route Question
# ============================================================

def route_question(question):

    result = router_chain.invoke({
        "question": question
    })

    print(f"[ROUTER RAW] {repr(result)}")

    route = result.strip().lower()

    if route.startswith("leave"):
        return "leave"

    if route.startswith("employee"):
        return "employee"

    return "general"