import gradio as gr

from llm import answer_llm
from langchain_core.prompts import ChatPromptTemplate

from router import route_question
from leave_agent import handle_leave

from conversation_memory import ConversationMemory


# ============================================================
# 일반 답변 Prompt
# ============================================================

answer_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "너는 도움이 되는 AI 어시스턴트다."
    ),
    (
        "human",
        "{question}"
    )
])


# ============================================================
# 일반 답변 Chain
# ============================================================

answer_chain = answer_prompt | answer_llm


# ============================================================
# Conversation Memory
# ============================================================

conversation_memories = {}


def get_memory(employee_id: str):

    if employee_id not in conversation_memories:

        conversation_memories[employee_id] = (
            ConversationMemory()
        )

    return conversation_memories[employee_id]


# ============================================================
# 로그인 사용자 가져오기
# ============================================================

def get_current_user(request: gr.Request):

    try:

        session = request.request.session

        employee_id = session.get("employee_id")

        print(
            f"[SESSION] employee_id={employee_id}"
        )

        return employee_id

    except Exception as e:

        print("[SESSION ERROR]")
        print(e)

        return None


# ============================================================
# Respond
# ============================================================

def respond(
    message,
    history,
    request: gr.Request
):

    # --------------------------------------------------------
    # 1. 로그인 사용자 확인
    # --------------------------------------------------------

    current_user_id = get_current_user(request)

    if not current_user_id:

        return (
            "로그인 정보가 없습니다. "
            "다시 로그인해주세요."
        )


    print(
        f"[CURRENT USER] {current_user_id}"
    )


    # --------------------------------------------------------
    # 2. Conversation Memory 가져오기
    # --------------------------------------------------------

    memory = get_memory(
        current_user_id
    )


    # --------------------------------------------------------
    # 3. 현재 사용자 질문 Memory 저장
    # --------------------------------------------------------

    memory.add_user(
        message
    )

    messages = memory.get_recent_messages()

    previous_messages = messages[:-1]


    print("[MEMORY USER]")
    print(messages)

    print("[PREVIOUS MESSAGES]")
    print(previous_messages)


    # --------------------------------------------------------
    # 4. Router
    # --------------------------------------------------------

    last_result = memory.get_last_result()

    followup_request_id = None
    previous_action = None


    # --------------------------------------------------------
    # 이전 승인/거절 요청에서
    # 신청번호 선택을 기다리는 상태인지 확인
    # --------------------------------------------------------

    if (
        last_result
        and last_result.get("type") == "leave_action"
        and last_result.get("action") in ("approve", "reject")
        and last_result.get("success") is False
        and last_result.get("items")
        and message.strip().isdigit()
    ):

        followup_request_id = int(
            message.strip()
        )

        previous_action = last_result.get(
            "action"
        )

        route = "leave"

        print(
            f"[ROUTER BYPASS] "
            f"{message} -> leave, "
            f"action={previous_action}, "
            f"request_id={followup_request_id}"
        )


    else:

        route = route_question(
            message,
                previous_messages,
        )


    print(
        f"[ROUTER] {message} -> {route}"
    )


    # --------------------------------------------------------
    # 5. LLM 서버 연결 실패
    #
    # Router가 LLM 호출 자체에 실패한 경우
    # unknown과 구분한다.
    # --------------------------------------------------------

    if route == "llm_unavailable":

        response = (
            "현재 AI 서버가 종료되어 있습니다.\n\n"
            "평일 18:00 이후 및 주말에는 GPU 서버를 종료합니다."
        )

        memory.add_assistant(response)

        return response


    # --------------------------------------------------------
    # 6. Leave Agent
    # --------------------------------------------------------

    if route == "leave":

        print(
            f"[LEAVE ACTOR] "
            f"employee_id={current_user_id}"
        )

        response = handle_leave(
            message,
            current_user_id,
            request_id=followup_request_id,
            previous_action=previous_action,
            messages=previous_messages,
            last_result=memory.get_last_result()
        )


        print("[RESPOND RESPONSE]")
        print(response)


        # ----------------------------------------------------
        # 마지막 Leave 결과 저장
        # ----------------------------------------------------

        memory.set_last_result(
            response
        )


        print("[MEMORY LAST RESULT]")
        print(
            memory.get_last_result()
        )


        # ----------------------------------------------------
        # Gradio 출력 형태로 변환
        # ----------------------------------------------------

        print("[BEFORE FORMAT]")

        formatted = format_leave_response(
            response
        )

        print("[AFTER FORMAT]")
        print(formatted)


        # ----------------------------------------------------
        # Leave 응답 Memory 저장
        # ----------------------------------------------------

        memory.add_assistant(
            formatted
        )


        print("[MEMORY AFTER LEAVE]")
        print(
            memory.get_messages()
        )


        return formatted


    # --------------------------------------------------------
    # 7. Unknown
    #
    # LLM은 정상적으로 응답했지만
    # leave / general로 판단하지 못한 경우
    # --------------------------------------------------------

    if route == "unknown":

        response = (
            "요청을 정확히 이해하지 못했습니다. "
            "어떤 업무를 원하시는지 조금 더 구체적으로 "
            "말씀해주세요."
        )


        memory.add_assistant(
            response
        )


        return response


    # --------------------------------------------------------
    # 8. General
    # --------------------------------------------------------

    try:

        response = answer_chain.invoke({
            "question": message
        })

    except Exception as e:

        print("[GENERAL LLM ERROR]")
        print(e)

        response = (
            "AI 서버에 연결할 수 없습니다. "
            "현재 AI 서버가 실행되지 않았거나 "
            "연결할 수 없는 상태입니다. "
            "잠시 후 다시 시도해주세요."
        )

        memory.add_assistant(
            response
        )

        return response


    # --------------------------------------------------------
    # 일반 답변 문자열 추출
    # --------------------------------------------------------

    if hasattr(response, "content"):

        assistant_message = response.content

    else:

        assistant_message = str(response)


    # --------------------------------------------------------
    # 일반 답변 Memory 저장
    # --------------------------------------------------------

    memory.add_assistant(
        assistant_message
    )


    return assistant_message


# ============================================================
# 상태값 한글 표시
# ============================================================

def get_status_display(status):

    status_labels = {
        "PENDING": "대기",
        "APPROVED": "승인",
        "REJECTED": "거절"
    }

    label = status_labels.get(
        status,
        status
    )

    return f"{status} ({label})"


# ============================================================
# Leave Response → Gradio 출력
# ============================================================

def format_leave_response(response):

    # --------------------------------------------------------
    # 휴가 목록 조회
    # --------------------------------------------------------

    if response.get("type") == "leave_list":

        lines = []

        lines.append(
            f"### {response['title']} "
            f"({response['count']}건)"
        )


        if response["count"] == 0:

            lines.append(
                "\n조회된 휴가가 없습니다."
            )

            return "\n".join(lines)


        lines.append(
            "\n"
            "| 신청번호 | 신청자 | 부서 | 기간 | "
            "일수 | 사유 | 상태 |"
        )


        lines.append(
            "|---|---|---|---|---:|---|---|"
        )


        for item in response["items"]:

            status_display = get_status_display(
                item["status"]
            )

            lines.append(
                f"| {item['request_id']} "
                f"| {item['name']} "
                f"({item['employee_id']}) "
                f"| {item['department']} "
                f"| {item['start_date']} ~ "
                f"{item['end_date']} "
                f"| {item['leave_days']}일 "
                f"| {item['reason']} "
                f"| {status_display} |"
            )


        return "\n".join(lines)


    # --------------------------------------------------------
    # 승인 / 거절 / 신청 / 잔여일수 등
    # --------------------------------------------------------

    if response.get("type") == "leave_action":

        if response.get("items"):

            lines = []

            lines.append(
                response.get(
                    "message",
                    "처리할 항목을 선택해주세요."
                )
            )


            lines.append(
                "\n"
                "| 신청번호 | 신청자 | 부서 | 기간 | "
                "일수 | 사유 | 상태 |"
            )


            lines.append(
                "|---|---|---|---|---:|---|---|"
            )


            for item in response["items"]:

                status_display = get_status_display(
                    item["status"]
                )

                lines.append(
                    f"| {item['request_id']} "
                    f"| {item['name']} "
                    f"({item['employee_id']}) "
                    f"| {item['department']} "
                    f"| {item['start_date']} ~ "
                    f"{item['end_date']} "
                    f"| {item['leave_days']}일 "
                    f"| {item['reason']} "
                    f"| {status_display} |"
                )


            return "\n".join(lines)


        return response.get(
            "message",
            "휴가 업무가 처리되었습니다."
        )


    # --------------------------------------------------------
    # 기타
    # --------------------------------------------------------

    return "휴가 요청을 처리할 수 없습니다."


# ============================================================
# Gradio
# ============================================================

css = """
.gradio-container {
    max-width: 1600px !important;
    margin: auto;
}

.chatbot {
    min-height: 700px !important;
}
"""


demo = gr.ChatInterface(
    fn=respond,
    title="AI Assistant",
    description="""
**AX Company AI Assistant**

사내 휴가 관련 업무를 지원하는 AI Agent입니다.

### 사용 예시
- 남은 휴가가 며칠이야?
- 신청휴가 보여줘
- 승인된 휴가만 보여줘
- 거절된 휴가만 보여줘
- 전체 휴가 목록 보여줘
- 휴가 신청 해줘
""",
    textbox=gr.Textbox(
        placeholder="휴가 관련 질문을 입력해주세요.",
        container=False
    )
)