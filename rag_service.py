import os
import requests
import psycopg2
import numpy as np

from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector

load_dotenv(".env.local2")


# ============================================================
# RAG Configuration
# ============================================================

EMBED_OLLAMA_BASE_URL = os.getenv(
    "EMBED_OLLAMA_BASE_URL",
    "http://127.0.0.1:11435"
)

EMBED_MODEL_NAME = os.getenv(
    "EMBED_MODEL_NAME",
    "bge-m3"
)

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "ax_company"),
    "user": os.getenv("DB_USER", "axuser"),
    "password": os.getenv("DB_PASSWORD", "axpassword"),
}

TOP_K = int(os.getenv("RAG_TOP_K", "5"))
EMBED_DIM = int(os.getenv("RAG_EMBED_DIM", "1024"))


# ============================================================
# Query Embedding
# ============================================================

def embed_query(question: str):

    response = requests.post(
        f"{EMBED_OLLAMA_BASE_URL}/api/embed",
        json={
            "model": EMBED_MODEL_NAME,
            "input": question,
            "keep_alive": -1,
        },
        timeout=60,
    )

    response.raise_for_status()

    data = response.json()

    embeddings = data.get("embeddings")

    if not embeddings:
        raise ValueError(
            "임베딩 모델에서 embeddings 값을 반환하지 않았습니다."
        )

    embedding = embeddings[0]

    if len(embedding) != EMBED_DIM:
        raise ValueError(
            f"임베딩 차원이 다릅니다. "
            f"expected={EMBED_DIM}, actual={len(embedding)}"
        )

    return np.asarray(
        embedding,
        dtype=np.float32
    )


# ============================================================
# Policy Search
# ============================================================

def search_policy(
    question: str,
    top_k: int = TOP_K
):

    query_vector = embed_query(question)

    conn = psycopg2.connect(
        **DB_CONFIG
    )

    register_vector(conn)

    try:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    chunk_id,
                    page,
                    part,
                    text,
                    1 - (embedding <=> %s) AS similarity
                FROM document_chunks
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> %s
                LIMIT %s
                """,
                (
                    query_vector,
                    query_vector,
                    top_k,
                ),
            )

            rows = cursor.fetchall()

    finally:
        conn.close()


    results = []

    for (
        chunk_id,
        page,
        part,
        text,
        similarity
    ) in rows:

        results.append({
            "chunk_id": chunk_id,
            "page": page,
            "part": part,
            "text": text,
            "similarity": float(similarity),
        })

    return results


# ============================================================
# Context Builder
# ============================================================

def build_policy_context(results):

    contexts = []

    for result in results:

        context = f"""
[출처]
페이지: {result['page']}
청크: {result['chunk_id']}

{result['text']}
""".strip()

        contexts.append(context)

    return "\n\n---\n\n".join(contexts)


# ============================================================
# Debug / Test
# ============================================================

if __name__ == "__main__":

    question = "연차유급휴가는 어떻게 부여하나요?"

    print()
    print("=== RAG TEST ===")
    print("QUESTION =", question)
    print("OLLAMA =", EMBED_OLLAMA_BASE_URL)
    print("EMBED MODEL =", EMBED_MODEL_NAME)
    print()

    results = search_policy(question)

    for index, result in enumerate(
        results,
        start=1
    ):

        print(
            f"[{index}] "
            f"page={result['page']} "
            f"chunk={result['chunk_id']} "
            f"similarity={result['similarity']:.4f}"
        )

        print(result["text"])
        print()
        print("-" * 80)
        print()
