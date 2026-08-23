import os


from dotenv import load_dotenv

load_dotenv(".env.local")

from langchain_ollama import ChatOllama

LLM_OLLAMA_BASE_URL = os.getenv(
    "LLM_OLLAMA_BASE_URL",
    "http://ollama-inference-service.ai-service.svc.cluster.local:11434"
)

MODEL_NAME = os.getenv(
    "MODEL_NAME",
    "exaone3.5:7.8b"
)

TEMPERATURE = float(
    os.getenv("TEMPERATURE", "0.3")
)


print("=== LLM CONFIG ===")
print("BASE_URL =", LLM_OLLAMA_BASE_URL)
print("MODEL =", MODEL_NAME)



answer_llm = ChatOllama(
    base_url=LLM_OLLAMA_BASE_URL,
    model=MODEL_NAME,
    temperature=TEMPERATURE,
    streaming=False,
    num_ctx=8192
)

