import gradio as gr

from llm import answer_llm
from langchain_core.prompts import ChatPromptTemplate

from router import route_question
from leave_agent import handle_leave


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
# Respond
# ============================================================

def respond(message, history):

    # --------------------------------------------------------
    # 1. Router
    # --------------------------------------------------------

    route = route_question(message)

    print(f"[ROUTER] {message} -> {route}")


    # --------------------------------------------------------
    # 2. Leave Agent
    # --------------------------------------------------------

    if route == "leave":

        response = handle_leave(message)

        print(f"[LEAVE AGENT] {response}")

        return format_leave_response(response)


    # --------------------------------------------------------
    # 3. Unknown
    # --------------------------------------------------------

    if route == "unknown":

        return "요청을 정확히 이해하지 못했습니다. 어떤 업무를 원하시는지 조금 더 구체적으로 말씀해주세요."


    # --------------------------------------------------------
    # 4. General
    # --------------------------------------------------------

    response = answer_chain.invoke({
        "question": message
    })

    return response


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

        for item in response["items"]:

            lines.append(
                f"""
            **휴가 신청번호: {item['request_id']}**
            - 신청자: {item['name']} ({item['employee_id']})
            - 부서: {item['department']}
            - 기간: {item['start_date']} ~ {item['end_date']}
            - 휴가 일수: {item['leave_days']}일
            - 사유: {item['reason']}
            - 상태: {item['status']}
            """
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


    return "휴가 요청을 처리할 수 없습니다."


# ============================================================
# Gradio
# ============================================================

demo = gr.ChatInterface(
    fn=respond,
    title="AI Assistant"
)


# ============================================================
# 실행
# ============================================================

if __name__ == "__main__":
    demo.launch()