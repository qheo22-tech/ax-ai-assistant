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
policy
general
unknown

[leave]
회사 휴가 시스템의 실제 데이터를 조회하거나 변경하는 요청.
특정 직원의 휴가 신청 가능 여부를 확인하는 요청도 포함한다.

예:
내 휴가 보여줘
내 남은 연차 며칠이야?
휴가 신청해줘
휴가 취소해줘
23번 승인해줘
내일 연차 신청 가능해?

[policy]
회사 노무관리 제도나 규정에 관한 일반적인 질문.
휴가, 연차, 휴직, 퇴직금, 임금, 근로시간 등
노무관리 문서에서 근거를 찾아 답할 수 있는 질문을 포함한다.
특정 직원의 실제 데이터를 조회하거나 변경하지 않는다.

예:
연차는 어떻게 부여해?
1년 미만 근로자는 연차가 몇 개 생겨?
연차는 언제까지 사용할 수 있어?
육아휴직 기간도 출근으로 인정돼?
퇴직금 미지급 시 제재가 있나요?
퇴직금은 언제까지 지급해야 하나요?
퇴직금을 월급에 포함해서 지급해도 되나요?
평균임금 계산 시 식대도 포함되나요?

[general]
회사 휴가 업무 또는 노무관리 정책과 관계없는 질문.

예:
안녕
파이썬이 뭐야?
점심 뭐 먹을까?

[unknown]
질문의 의미를 판단하기 어려운 경우.

중요:
- 실제 직원 데이터 조회/변경 → leave
- 특정 직원의 신청 가능 여부 판단 → leave
- 노무관리 규정이나 제도 자체 질문 → policy
- 실제 데이터와 규정 질문이 함께 있으면 leave
- 회사 업무 범위와 관계없는 질문 → general
- 현재 질문을 가장 우선하여 분류한다.
- 이전 대화는 현재 질문에 "그거", "아까", "그 경우"처럼
  문맥을 가리키는 표현이 있을 때만 참고한다.

반드시 다음 중 하나만 출력한다.

leave
policy
general
unknown

다른 설명은 출력하지 않는다.
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

VALID_LABELS = ("leave", "policy", "general", "unknown")


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