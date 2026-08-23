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

# 사용자별 ConversationMemory
#
# employee_id
#     ↓
# ConversationMemory
#
# E001 → Memory
# E002 → Memory
# E003 → Memory
#
# 사용자별로 대화가 섞이지 않도록 분리한다.
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

        # FastAPI / Starlette SessionMiddleware가
        # 저장한 session 접근
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
    # 3. 사용자 질문 Memory 저장
    # --------------------------------------------------------

    memory.add_user(
        message
    )


    print("[MEMORY USER]")

    print(
        memory.get_messages()
    )


    # --------------------------------------------------------
    # 4. Router
    # --------------------------------------------------------

    messages = memory.get_messages()

    route = route_question(
        message,
        messages
    )

    print(
        f"[ROUTER] {message} -> {route}"
    )


    # --------------------------------------------------------
    # 5. Leave Agent
    # --------------------------------------------------------
    if route == "leave":

        print(
            f"[LEAVE ACTOR] "
            f"employee_id={current_user_id}"
        )

        response = handle_leave(
            message,
            current_user_id
        )

        print("[RESPOND RESPONSE]")
        print(response)

        memory.set_last_result(
            response
        )

        print("[MEMORY LAST RESULT]")
        print(
            memory.get_last_result()
        )

        print("[BEFORE FORMAT]")

        formatted = format_leave_response(
            response
        )

        print("[AFTER FORMAT]")
        print(formatted)

        return formatted

    # --------------------------------------------------------
    # 6. Unknown
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
    # 7. General
    # --------------------------------------------------------

    response = answer_chain.invoke({
        "question": message
    })


    # --------------------------------------------------------
    # 일반 답변 Memory 저장
    # --------------------------------------------------------

    if hasattr(response, "content"):

        assistant_message = response.content

    else:

        assistant_message = str(response)


    memory.add_assistant(
        assistant_message
    )


    return assistant_message


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
            f"### {response['title']} ({response['count']}건)"
        )

        if response["count"] == 0:
            lines.append("\n조회된 휴가가 없습니다.")
            return "\n".join(lines)

        lines.append(
            "\n| 신청번호 | 신청자 | 부서 | 기간 | 일수 | 사유 | 상태 |"
        )
        lines.append(
            "|---|---|---|---|---:|---|---|"
        )

        for item in response["items"]:

            lines.append(
                f"| {item['request_id']} "
                f"| {item['name']} ({item['employee_id']}) "
                f"| {item['department']} "
                f"| {item['start_date']} ~ {item['end_date']} "
                f"| {item['leave_days']}일 "
                f"| {item['reason']} "
                f"| {item['status']} |"
            )

        return "\n".join(lines)


    # --------------------------------------------------------
    # 승인 / 거절
    # --------------------------------------------------------

    if response.get("type") == "leave_action":

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