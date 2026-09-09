import gradio as gr
import json
import os

from llm import answer_llm , normalize_llm
from langchain_core.prompts import ChatPromptTemplate

from router import route_question
from leave_agent import handle_leave
from policy_agent import answer_policy

from conversation_memory import ConversationMemory

from normalize_prompt import normalize_prompt



# =========================================================
# 일반 LLM
# =========================================================

answer_prompt = ChatPromptTemplate.from_messages([
    ("system", "너는 도움이 되는 AI 어시스턴트다."),
    ("human", "{question}")
])

answer_chain = answer_prompt | answer_llm


# =========================================================
# 문서 정규화 LLM
# =========================================================

normalize_chain = normalize_prompt | normalize_llm


# =========================================================
# Conversation Memory
# =========================================================

conversation_memories = {}


def get_memory(employee_id: str):
    if employee_id not in conversation_memories:
        conversation_memories[employee_id] = ConversationMemory()

    return conversation_memories[employee_id]


# =========================================================
# 현재 로그인 사용자
# =========================================================

def get_current_user(request: gr.Request):
    try:
        session = request.request.session
        employee_id = session.get("employee_id")

        print(f"[SESSION] employee_id={employee_id}")

        return employee_id

    except Exception as e:
        print("[SESSION ERROR]")
        print(e)

        return None


# =========================================================
# 기존 Chat 응답
# =========================================================

def respond(message, history, request: gr.Request):

    current_user_id = get_current_user(request)

    if not current_user_id:
        return "로그인 정보가 없습니다. 다시 로그인해주세요."

    print(f"[CURRENT USER] {current_user_id}")

    memory = get_memory(current_user_id)

    memory.add_user(message)

    messages = memory.get_recent_messages()

    previous_messages = messages[:-1]

    print("[MEMORY USER]")
    print(messages)

    print("[PREVIOUS MESSAGES]")
    print(previous_messages)

    last_result = memory.get_last_result()

    followup_request_id = None
    previous_action = None

    # =====================================================
    # 숫자 입력에 대한 승인/거절 후속 처리
    # =====================================================

    if (
        last_result
        and last_result.get("type") == "leave_action"
        and last_result.get("action") in ("approve", "reject")
        and last_result.get("success") is False
        and last_result.get("items")
        and message.strip().isdigit()
    ):

        followup_request_id = int(message.strip())

        previous_action = last_result.get("action")

        route = "leave"

        print(
            f"[ROUTER BYPASS] {message} -> leave, "
            f"action={previous_action}, "
            f"request_id={followup_request_id}"
        )

    else:

        route = route_question(
            message,
            previous_messages
        )

    print(f"[ROUTER] {message} -> {route}")

    # =====================================================
    # AI 서버 종료
    # =====================================================

    if route == "llm_unavailable":

        response = (
            "현재 AI 서버가 종료되어 있습니다.\n\n"
            "평일 18:00 이후 및 주말에는 GPU 서버를 종료합니다."
        )

        memory.add_assistant(response)

        return response

    # =====================================================
    # 휴가 Agent
    # =====================================================

    if route == "leave":

        print(
            f"[LEAVE ACTOR] employee_id={current_user_id}"
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

        memory.set_last_result(response)

        print("[MEMORY LAST RESULT]")
        print(memory.get_last_result())

        print("[BEFORE FORMAT]")

        formatted = format_leave_response(response)

        print("[AFTER FORMAT]")
        print(formatted)

        memory.add_assistant(formatted)

        print("[MEMORY AFTER LEAVE]")
        print(memory.get_messages())

        return formatted

    # =====================================================
    # 휴가 정책 RAG
    # =====================================================

    if route == "policy":
        response = answer_policy(message)

        memory.add_assistant(response)

        return response
    
    # =====================================================
    # 이해하지 못한 요청
    # =====================================================

    if route == "unknown":

        response = (
            "요청을 정확히 이해하지 못했습니다. "
            "어떤 업무를 원하시는지 조금 더 구체적으로 말씀해주세요."
        )

        memory.add_assistant(response)

        return response

    # =====================================================
    # 업무 범위 밖 요청
    # =====================================================

    if route == "general":

        response = (
            "업무 지원 범위를 벗어난 질문입니다. "
            "휴가 업무 또는 노무관리 관련 질문을 입력해주세요."
        )

        memory.add_assistant(response)

        return response



    # =====================================================
    # 일반 LLM
    # =====================================================

    try:

        response = answer_chain.invoke({
            "question": message
        })

    except Exception as e:

        print("[GENERAL LLM ERROR]")
        print(e)

        response = (
            "AI 서버에 연결할 수 없습니다. "
            "현재 AI 서버가 실행되지 않았거나 연결할 수 없는 상태입니다. "
            "잠시 후 다시 시도해주세요."
        )

        memory.add_assistant(response)

        return response

    if hasattr(response, "content"):
        assistant_message = response.content
    else:
        assistant_message = str(response)

    memory.add_assistant(assistant_message)

    return assistant_message


# =========================================================
# 문서 정규화 - JSON 결과 파싱
# =========================================================

def parse_normalize_result(content):

    content = content.strip()

    # ```json 제거
    if content.startswith("```json"):
        content = content[7:]

    # ``` 제거
    elif content.startswith("```"):
        content = content[3:]

    # 마지막 ``` 제거
    if content.endswith("```"):
        content = content[:-3]

    content = content.strip()

    return json.loads(content)


# =========================================================
# 문서 정규화
# =========================================================

def normalize_uploaded_file(file):

    if file is None:
        return "파일을 먼저 업로드해주세요."

    try:

        file_path = file

        print("=" * 80)
        print("[NORMALIZE START]")
        print(f"[FILE] {file_path}")
        print("=" * 80)

        # =================================================
        # JSON 파일 읽기
        # =================================================

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as f:

            pages = json.load(f)

        # =================================================
        # JSON 구조 확인
        # =================================================

        if not isinstance(pages, list):

            return (
                "JSON 형식이 올바르지 않습니다.\n\n"
                "페이지 배열 형태의 JSON이어야 합니다."
            )

        print(
            f"[NORMALIZE] 전체 페이지: {len(pages)}"
        )

        normalized_pages = []

        # =================================================
        # 페이지별 정규화
        #
        # 현재는 chunking 하지 않음.
        # 페이지 하나당 LLM 한 번 호출.
        # =================================================

        for index, page in enumerate(pages):

            page_number = page.get("page")

            print(
                f"[NORMALIZE] "
                f"{index + 1}/{len(pages)} "
                f"page={page_number}"
            )

            text = page.get("text", "")

            if text is None:
                text = ""

            input_json = json.dumps(
                [page],
                ensure_ascii=False
            )

            response = normalize_chain.invoke({
                "text": input_json
            })

            if hasattr(response, "content"):
                content = response.content
            else:
                content = str(response)

            print("[NORMALIZE RAW RESPONSE]")
            print(content)

            result = parse_normalize_result(content)

            if isinstance(result, list):
                normalized_pages.extend(result)

            elif isinstance(result, dict):
                normalized_pages.append(result)

            else:
                raise ValueError(
                    f"정규화 결과 형식 오류: "
                    f"page={page_number}"
                )

        # =================================================
        # 페이지 순서 정렬
        # =================================================

        normalized_pages.sort(
            key=lambda x: x.get("page", 0)
        )

        print("=" * 80)
        print("[NORMALIZE COMPLETE]")
        print(
            f"정규화 페이지 수: "
            f"{len(normalized_pages)}"
        )
        print("=" * 80)

        # =================================================
        # 최종 JSON
        # =================================================

        result_json = json.dumps(
            normalized_pages,
            ensure_ascii=False,
            indent=2
        )

        return result_json

    except json.JSONDecodeError as e:

        print("[NORMALIZE JSON ERROR]")
        print(e)

        return (
            "LLM이 올바른 JSON을 반환하지 않았습니다.\n\n"
            f"{e}"
        )

    except Exception as e:

        print("=" * 80)
        print("[NORMALIZE ERROR]")
        print(e)
        print("=" * 80)

        return (
            "문서 정규화 중 오류가 발생했습니다.\n\n"
            f"{type(e).__name__}: {e}"
        )


# =========================================================
# 휴가 상태
# =========================================================

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


# =========================================================
# 휴가 응답 포맷
# =========================================================

def format_leave_response(response):

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
            "\n| 신청번호 | 신청자 | 부서 | 기간 | 일수 | 사유 | 상태 |"
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
                f"| {item['name']} ({item['employee_id']}) "
                f"| {item['department']} "
                f"| {item['start_date']} ~ {item['end_date']} "
                f"| {item['leave_days']}일 "
                f"| {item['reason']} "
                f"| {status_display} |"
            )

        if (
            response.get("action") == "excel"
            and response.get("success") is True
            and response.get("filename")
        ):

            filename = response["filename"]

            lines.append("")

            lines.append(
                f"[엑셀 파일 다운로드](/download/{filename})"
            )

            print(
                f"[EXCEL DOWNLOAD LINK] "
                f"/download/{filename}"
            )

        return "\n".join(lines)

    # =====================================================
    # 휴가 승인 / 거절
    # =====================================================

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
                "\n| 신청번호 | 신청자 | 부서 | 기간 | 일수 | 사유 | 상태 |"
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
                    f"| {item['name']} ({item['employee_id']}) "
                    f"| {item['department']} "
                    f"| {item['start_date']} ~ {item['end_date']} "
                    f"| {item['leave_days']}일 "
                    f"| {item['reason']} "
                    f"| {status_display} |"
                )

            return "\n".join(lines)

        return response.get(
            "message",
            "휴가 업무가 처리되었습니다."
        )

    return "휴가 요청을 처리할 수 없습니다."


# =========================================================
# CSS
# =========================================================

css = """
.gradio-container {
    max-width: 1600px !important;
    margin: auto;
}

.chatbot {
    min-height: 700px !important;
}
"""

# =========================================================
# UI
# =========================================================

with gr.Blocks(css=css) as demo:

    # =====================================================
    # AI Assistant 소개
    # =====================================================

    gr.Markdown("""
# AI Assistant

**AX Company AI Assistant**

사내 휴가 업무 처리와 휴가 정책 질의를 지원하는 AI Agent입니다.

Tool Calling 기반으로 휴가 조회·신청·승인·거절 및 Excel 생성을 수행하고,
RAG를 통해 정책 문서를 검색하여 근거 기반 답변을 제공합니다.

※ 휴가 승인 및 거절은 관리자만 가능합니다.
""")

    # =====================================================
    # 사용 예시
    # =====================================================

    gr.Markdown("### 사용 예시")

    with gr.Row():

        with gr.Column():
            gr.Markdown("""
#### 🛠 휴가 업무 · Agent / Tool Calling

- 남은 휴가가 며칠이야?
- 신청휴가 보여줘
- 휴가 신청 해줘
- 승인된 휴가만 보여줘
- 우리팀 휴가목록 보여줘 (팀장)
- 전체 휴가 목록 보여줘 (관리자)
- 신청휴가로 엑셀 만들어줘
""")

        with gr.Column():
            gr.Markdown("""
#### 📚 휴가 정책 문의 · RAG

- 1년 미만 근로자는 연차가 몇 개 발생하나요?
- 연차유급휴가는 어떻게 부여하나요?
- 연차 사용촉진제도는 무엇인가요?
- 육아휴직 기간도 연차 산정 시 출근한 것으로 보나요?
""")
            

    # =====================================================
    # 기존 채팅
    # =====================================================

    chat = gr.ChatInterface(
        fn=respond,
        textbox=gr.Textbox(
            placeholder="휴가 관련 질문을 입력해주세요.",
            container=False
        )
    )

    # =====================================================
    # 문서 정규화
    # =====================================================

    gr.Markdown("---")

#      gr.Markdown("""
# ## 문서 정규화

# PDF/JSON 추출 과정에서 발생한 불필요한 줄바꿈을 정규화합니다.
# """)

#     with gr.Row():

#         normalize_file = gr.File(
#             label="문서 업로드",
#             file_types=[".json"],
#             type="filepath"
#         )

#         normalize_button = gr.Button(
#             "정규화 실행",
#             variant="primary"
#         )

#     normalize_output = gr.Code(
#         label="정규화 결과",
#         language="json",
#         lines=25
#     )

#     # =====================================================
#     # 정규화 버튼 이벤트
#     # =====================================================

#     normalize_button.click(
#         fn=normalize_uploaded_file,
#         inputs=normalize_file,
#         outputs=normalize_output
#     )
