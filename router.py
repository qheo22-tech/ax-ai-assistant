import re


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
- 휴가 승인
- 휴가 거절
- 휴가 반려
- 전체 휴가 목록 조회
- 승인된 휴가 조회
- 대기 중인 휴가 조회
- 거절된 휴가 조회

general:
회사 시스템의 데이터를 조회하거나 변경하지 않는
일반적인 질문과 대화.

unknown:
사용자의 의도를 파악하기 어려워
leave 또는 general로 판단하기 어려운 경우.

중요:
휴가와 관련된 실제 회사 업무를 요청하는 경우
반드시 leave로 분류한다.

예시:

"내 휴가 이력 보여줘" → leave
"휴가 신청한 사람 누구야?" → leave
"휴가 신청 목록 보여줘" → leave
"전체 휴가신청목록 보여줘" → leave
"전체 휴가 목록 보여줘" → leave
"누가 휴가 가?" → leave
"휴가 며칠 남았어?" → leave
"휴가 신청해줘" → leave
"휴가 취소해줘" → leave
"7번 승인해줘" → leave
"승인목록 보여줘" → leave
"대기중인 휴가 보여줘" → leave
"거절된 휴가 보여줘" → leave

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
"거절된 것", "전체목록", "승인목록"처럼
이전 결과를 가리키는 표현은
이전 대화와 연결해서 판단한다.


매우 중요:
설명이나 이유를 절대 출력하지 않는다.
마크다운을 사용하지 않는다.
반드시 아래 세 단어 중 하나만 출력한다.

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

    # --------------------------------------------------------
    # 1. 이전 대화 문자열 생성
    # --------------------------------------------------------

    history = ""

    if messages:
        history = "\n".join(
            f"{message['role']}: {message['content']}"
            for message in messages
        )


    # --------------------------------------------------------
    # 2. Router LLM 호출
    # --------------------------------------------------------

    result = router_chain.invoke({
        "question": question,
        "history": history
    })


    # --------------------------------------------------------
    # 3. 디버깅 로그
    # --------------------------------------------------------

    print(f"[ROUTER HISTORY] {history}")
    print(f"[ROUTER RAW] {repr(result)}")


    # --------------------------------------------------------
    # 4. LLM 응답 문자열 추출
    # --------------------------------------------------------

    if hasattr(result, "content"):
        route_text = result.content
    else:
        route_text = str(result)


    # --------------------------------------------------------
    # 5. 응답 정규화
    #
    # 예:
    #
    # **leave**
    # 설명...
    #
    # ↓
    #
    # leave
    # --------------------------------------------------------

    route_text = route_text.strip().lower()

    # 첫 줄만 사용
    first_line = route_text.splitlines()[0]

    # 모델이 붙일 수 있는 마크다운 제거
    first_line = (
        first_line
        .replace("*", "")
        .replace("`", "")
        .replace("#", "")
        .replace(":", "")
        .strip()
    )


    print(
        f"[ROUTER NORMALIZED] "
        f"raw={route_text!r}, "
        f"first_line={first_line!r}"
    )


    # --------------------------------------------------------
    # 6. 최종 Route 판별
    # --------------------------------------------------------

    if first_line == "leave":
        return "leave"

    if first_line == "general":
        return "general"

    if first_line == "unknown":
        return "unknown"


    # --------------------------------------------------------
    # 7. 모델이 이상한 형식으로 응답한 경우 보정
    #
    # 예:
    # "leave 입니다."
    # "leave - 휴가 업무"
    # --------------------------------------------------------

    if first_line.startswith("leave"):
        return "leave"

    if first_line.startswith("general"):
        return "general"

    if first_line.startswith("unknown"):
        return "unknown"

    normalized_text = (
        route_text
        .replace("*", "")
        .replace("`", "")
        .replace("#", "")
    )

    if re.search(r"분류\s*:\s*leave\b", normalized_text):
        return "leave"

    if re.search(r"분류\s*:\s*general\b", normalized_text):
        return "general"

    if re.search(r"분류\s*:\s*unknown\b", normalized_text):
        return "unknown"


    # --------------------------------------------------------
    # 8. 안전한 fallback
    #
    # 잘못된 응답을 general로 보내면
    # 휴가 요청이 일반 LLM으로 빠질 수 있으므로
    # unknown으로 처리한다.
    # --------------------------------------------------------

    print(
        f"[ROUTER WARNING] "
        f"알 수 없는 Router 응답: {route_text!r}"
    )

    return "unknown"