import os

from dotenv import load_dotenv
from langchain_ollama import ChatOllama

load_dotenv(".env.local2")

LLM_OLLAMA_BASE_URL = os.getenv(
    "LLM_OLLAMA_BASE_URL",
    "http://ollama-inference-service.ai-service.svc.cluster.local:11434"
)

MODEL_NAME = os.getenv(
    "MODEL_NAME",
    "qwen3-14b"
)

TEMPERATURE = float(
    os.getenv("TEMPERATURE", "0")
)


print("=== LLM CONFIG ===")
print("BASE_URL =", LLM_OLLAMA_BASE_URL)
print("MODEL =", MODEL_NAME)


router_llm = ChatOllama(
    base_url=LLM_OLLAMA_BASE_URL,
    model=MODEL_NAME,
    temperature=0,
    streaming=False,
    num_ctx=4096,
    think=False,
    num_predict=32,
    keep_alive=-1,
)

# 실제 업무 분석용
answer_llm = ChatOllama(
    base_url=LLM_OLLAMA_BASE_URL,
    model=MODEL_NAME,
    temperature=0,
    streaming=False,
    num_ctx=4096,
    think=False,
    num_predict=128,
    keep_alive=-1,
)