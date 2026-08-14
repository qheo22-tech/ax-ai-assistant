import gradio as gr

from llm import answer_llm
from image_tool import generate_image
from langchain_core.prompts import ChatPromptTemplate
from router import route_question
from image_prompt import generate_image_prompt


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
    # 2. Image
    # --------------------------------------------------------

    if route == "image":

        prompt = generate_image_prompt(message)

        result = generate_image.invoke({
            "prompt": prompt
        })

        return gr.ChatMessage( role="assistant", content=gr.Image(value=result) )

    # --------------------------------------------------------
    # 3. RAG
    # --------------------------------------------------------

    if route == "rag":

        # 아직 RAG 구현 전
        return "RAG 요청으로 분류되었습니다."


    # --------------------------------------------------------
    # 4. General
    # --------------------------------------------------------

    response = answer_chain.invoke({
        "question": message
    })

    return response


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