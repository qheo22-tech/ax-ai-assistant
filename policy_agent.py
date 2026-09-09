from llm import answer_llm
from policy_prompt import policy_prompt
from rag_service import search_policy, build_policy_context


policy_chain = policy_prompt | answer_llm


def answer_policy(question: str):

    results = search_policy(question)

    if not results:
        return "관련된 휴가 정책 문서를 찾지 못했습니다."

    context = build_policy_context(results)

    print("[POLICY RAG RESULTS]")

    for result in results:
        print(
            f"page={result['page']} "
            f"chunk={result['chunk_id']} "
            f"similarity={result['similarity']:.4f}"
        )

    print("[POLICY LLM START]")

    response = policy_chain.invoke({
        "question": question,
        "context": context,
    })

    print("[POLICY LLM END]")
    print("[POLICY RESPONSE RAW]", response)

    return response.content