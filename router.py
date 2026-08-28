import logging
import re
import time

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
/no_think
"""
    ),
    (
        "human",
        """
이전 대화:
{history}

현재 질문:
{question}
/no_think
"""
    )
])


# ============================================================
# Router Chain
# ============================================================

router_chain = router_prompt | router_llm


# ============================================================
# Valid labels
# ============================================================

VALID_LABELS = ("leave", "general", "unknown")


# ============================================================
# Route Question
# ============================================================

def route_question(question: str, messages=None):

    # --------------------------------------------------------
    # 1. History 생성
    # --------------------------------------------------------

    history = "없음"

    if messages:

        recent_messages = [
            message
            for message in messages[-6:]
            if message.get("role") in ("user", "assistant")
        ]

        if recent_messages:
            history = "\n".join(
                f"{message['role']}: {message['content']}"
                for message in recent_messages
            )

    print("[ROUTER INPUT]")
    print("question =", repr(question))
    print("history  =", repr(history))


    # --------------------------------------------------------
    # 2. Router LLM 호출
    # --------------------------------------------------------
    #
    # ★ 추가한 핵심 부분
    # ★ 실제 LLM 호출에 걸리는 시간을 측정한다.
    #
    # --------------------------------------------------------

    router_start = time.perf_counter()

    try:
        result = router_chain.invoke({
            "question": question,
            "history": history
        })

    except Exception:
        router_elapsed = time.perf_counter() - router_start
        print(f"[ROUTER LLM ERROR] elapsed={router_elapsed:.3f}s")
        logger.exception("[ROUTER ERROR] LLM 호출 중 예외 발생")
        return "llm_unavailable"

    router_elapsed = time.perf_counter() - router_start
    print(f"[ROUTER LLM TIME] {router_elapsed:.3f}s")

    # ============================================================
    # ★ 디버깅용: 응답 전체 구조 / 길이 / thinking 여부 확인
    # ============================================================

    content = getattr(result, "content", None) or str(result)

    print("[ROUTER CONTENT LENGTH]", len(content))
    print("[ROUTER RAW CONTENT]", repr(content))

    # additional_kwargs에 thinking이 새고 있는지 확인
    additional_kwargs = getattr(result, "additional_kwargs", {}) or {}
    print("[ROUTER ADDITIONAL_KWARGS KEYS]", list(additional_kwargs.keys()))

    for key, value in additional_kwargs.items():
        value_str = str(value)
        print(f"[ROUTER ADDITIONAL_KWARGS] {key} length={len(value_str)}")
        print(f"[ROUTER ADDITIONAL_KWARGS] {key} preview={value_str[:200]!r}")

    # response_metadata도 확인 (eval_count 등 토큰 수 정보)
    response_metadata = getattr(result, "response_metadata", {}) or {}
    print("[ROUTER RESPONSE_METADATA]", response_metadata)

    # usage_metadata가 있으면 실제 생성 토큰 수 확인
    usage_metadata = getattr(result, "usage_metadata", None)
    if usage_metadata:
        print("[ROUTER USAGE_METADATA]", usage_metadata)


    # --------------------------------------------------------
    # 3. 응답 문자열 추출
    # --------------------------------------------------------

    if hasattr(result, "content"):
        content = result.content
    else:
        content = str(result)

    print(
        "[ROUTER RAW CONTENT]",
        repr(content)
    )


    # --------------------------------------------------------
    # 4. 응답 정규화
    # --------------------------------------------------------

    route_text = (content or "").strip().lower()

    if not route_text:

        print(
            "[ROUTER WARNING] "
            "Router가 빈 응답을 반환했습니다."
        )

        return "unknown"


    # --------------------------------------------------------
    # 5. 첫 줄 추출
    # --------------------------------------------------------

    first_line = route_text.splitlines()[0]

    first_line = (
        first_line
        .replace("*", "")
        .replace("`", "")
        .replace("#", "")
        .replace(":", "")
        .replace(".", "")
        .strip()
    )


    print(
        "[ROUTER NORMALIZED]",
        repr(first_line)
    )


    # --------------------------------------------------------
    # 6. 정확히 일치
    # --------------------------------------------------------

    if first_line in VALID_LABELS:
        return first_line


    # --------------------------------------------------------
    # 7. 앞부분이 label인 경우
    #
    # 예:
    # leave 입니다
    # general - 일반 질문
    # --------------------------------------------------------

    for label in VALID_LABELS:

        if first_line.startswith(label):
            return label


    # --------------------------------------------------------
    # 8. 전체 응답에서 label 검색
    # --------------------------------------------------------

    normalized_text = (
        route_text
        .replace("*", "")
        .replace("`", "")
        .replace("#", "")
    )


    for label in VALID_LABELS:

        if re.search(
            rf"분류\s*:?\s*{label}\b",
            normalized_text
        ):
            return label


    # --------------------------------------------------------
    # 9. label 단독 검색
    # --------------------------------------------------------

    for label in VALID_LABELS:

        if re.search(
            rf"\b{label}\b",
            normalized_text
        ):
            return label


    # --------------------------------------------------------
    # 10. 최종 fallback
    # --------------------------------------------------------

    print(
        "[ROUTER WARNING] "
        f"알 수 없는 Router 응답: {repr(route_text)}"
    )

    return "unknown"