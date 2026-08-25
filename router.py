import logging
import re

from langchain_core.prompts import ChatPromptTemplate

from llm import router_llm

logger = logging.getLogger(__name__)


# ============================================================
# Router Prompt
# ============================================================

router_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """
사용자의 현재 질문을 다음 중 하나로 분류한다.

leave
general
unknown

[leave]
회사 휴가 시스템의 실제 데이터를 조회하거나 변경하는 요청.

예:
내 휴가 보여줘
내 승인된 휴가 보여줘
내 남은 휴가 며칠이야?
휴가 신청해줘
휴가 취소해줘
휴가 신청 목록 보여줘
전체 휴가 목록 보여줘
누가 휴가 가?
김철수 휴가 보여줘
23번 승인해줘
대기중인 휴가 보여줘
거절된 휴가 보여줘


[general]
휴가에 대한 일반적인 설명이나 지식 질문.
회사 시스템의 실제 데이터를 조회하거나 변경하지 않는 질문.

예:
휴가가 뭐야?
휴가가 왜 필요한 거야?
휴가의 장점은 뭐야?
휴가는 왜 써?
휴가는 보통 언제 써?
연차가 뭐야?
연차와 휴가의 차이는 뭐야?
안녕


[unknown]
질문의 의도를 판단하기 어렵거나,
leave와 general 요청이 한 질문에 함께 있는 경우.

예:
휴가가 뭔지 설명해주고 내 휴가도 보여줘
휴가가 왜 필요한지 설명하고 내 남은 휴가도 알려줘


[중요 규칙]

1. 현재 질문을 가장 중요하게 판단한다.

2. "휴가"라는 단어가 있다고 무조건 leave가 아니다.

3. 회사 시스템의 실제 데이터를 조회하거나 변경하면 leave다.

4. 일반적인 설명, 정의, 이유, 장점, 지식 질문이면 general이다.

5. 현재 질문이 "그중", "그것", "이것", "방금 것",
   "위에 것", "그 사람", "그 직원"처럼
   앞의 대화를 가리키는 경우에만 이전 대화를 참고한다.

예:

이전 대화:
user: 내 휴가 목록 보여줘
assistant: 휴가 목록입니다.

현재 질문:
그중 승인된 것만 보여줘

→ leave


이전 대화:
user: 내 승인된 휴가 보여줘
assistant: 승인된 휴가 목록입니다.

현재 질문:
휴가가 왜 필요한 거야?

→ general


[출력 규칙]

반드시 다음 중 하나만 출력한다.

leave
general
unknown

설명하지 않는다.
다른 문자를 출력하지 않는다.
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
#
# temperature=0으로 모델이 매번 다른 답을 내는 것을 줄인다.
# max_tokens는 벤더마다 파라미터 이름이 다르므로
# (OpenAI 계열: max_tokens / Ollama 계열: num_predict)
# 여기서는 임의로 강제하지 않는다. answer_llm 생성 시점에
# 이미 짧게 설정되어 있는 것이 가장 안전하다.
#
# bind()는 정의 시점에는 에러 없이 통과하고, 실제 invoke
# 시점에 벤더가 모르는 파라미터라며 실패할 수 있으므로
# 여기서 미리 검증하지 않고, answer_llm을 그대로 사용한다.
# ============================================================

router_chain = router_prompt | router_llm


# ============================================================
# 유효한 라벨 목록 (순서 = fallback 탐색 우선순위)
# ============================================================

VALID_LABELS = ("leave", "general", "unknown")


# ============================================================
# Route Question
# ============================================================

def route_question(question: str, messages=None):

    # --------------------------------------------------------
    # 1. 이전 대화 생성
    #
    # Router는 전체 대화를 무제한으로 볼 필요가 없다.
    # 최근 대화만 사용하고, user/assistant 메시지만 남긴다.
    # --------------------------------------------------------

    history = "없음"

    if messages:

        # 최근 6개 메시지 중 user/assistant만 사용
        recent_messages = [
            message for message in messages[-6:]
            if message.get("role") in ("user", "assistant")
        ]

        if recent_messages:
            history = "\n".join(
                f"{message['role']}: {message['content']}"
                for message in recent_messages
            )


    # --------------------------------------------------------
    # 2. Router LLM 호출
    #
    # 벤더/모델 설정 문제 등으로 호출 자체가 실패해도
    # 상위 로직이 죽지 않도록 unknown으로 안전하게 fallback한다.
    # --------------------------------------------------------

    try:
        result = router_chain.invoke({
            "question": question,
            "history": history
        })
    except Exception:
        logger.exception("[ROUTER ERROR] LLM 호출 중 예외 발생")
        return "llm_unavailable"


    # --------------------------------------------------------
    # 3. 디버깅 로그
    # --------------------------------------------------------

    logger.debug("[ROUTER QUESTION] %s", question)
    logger.debug("[ROUTER HISTORY] %s", history)
    logger.debug("[ROUTER RAW] %r", result)


    # --------------------------------------------------------
    # 4. LLM 응답 문자열 추출
    # --------------------------------------------------------

    if hasattr(result, "content"):
        route_text = result.content
    else:
        route_text = str(result)


    # --------------------------------------------------------
    # 5. 응답 정규화
    # --------------------------------------------------------

    route_text = (route_text or "").strip().lower()

    # 빈 응답 방어
    if not route_text:
        logger.warning("[ROUTER WARNING] Router가 빈 응답을 반환했습니다.")
        return "unknown"


    # 첫 줄만 사용
    first_line = route_text.splitlines()[0]

    # 마크다운 및 불필요한 문자 제거
    first_line = (
        first_line
        .replace("*", "")
        .replace("`", "")
        .replace("#", "")
        .replace(":", "")
        .replace(".", "")
        .strip()
    )

    logger.debug(
        "[ROUTER NORMALIZED] raw=%r, first_line=%r",
        route_text, first_line,
    )


    # --------------------------------------------------------
    # 6. 정상 Route 판별 (정확히 일치)
    # --------------------------------------------------------

    if first_line in VALID_LABELS:
        return first_line


    # --------------------------------------------------------
    # 7. 모델이 부가 설명을 붙인 경우
    #
    # 예:
    # leave 입니다.
    # general - 일반 질문
    # --------------------------------------------------------

    for label in VALID_LABELS:
        if first_line.startswith(label):
            return label


    # --------------------------------------------------------
    # 8. 전체 응답에서 "분류: xxx" 형식 검색
    # --------------------------------------------------------

    normalized_text = (
        route_text
        .replace("*", "")
        .replace("`", "")
        .replace("#", "")
    )

    for label in VALID_LABELS:
        if re.search(rf"분류\s*:?\s*{label}\b", normalized_text):
            return label


    # --------------------------------------------------------
    # 9. "분류:" 형식 없이도 전체 텍스트에서 단어 단위로 검색
    #
    # 세 라벨 모두 서로의 부분 문자열이 아니므로
    # 단어 경계(\b) 기준 검색만으로 충분히 안전하다.
    # --------------------------------------------------------

    for label in VALID_LABELS:
        if re.search(rf"\b{label}\b", normalized_text):
            return label


    # --------------------------------------------------------
    # 10. 안전한 fallback
    # --------------------------------------------------------

    logger.warning("[ROUTER WARNING] 알 수 없는 Router 응답: %r", route_text)

    return "unknown"