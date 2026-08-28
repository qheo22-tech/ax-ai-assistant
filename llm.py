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

ROUTER_NUM_PREDICT = int(
    os.getenv("ROUTER_NUM_PREDICT", "32")
)

ANSWER_NUM_PREDICT = int(
    os.getenv("ANSWER_NUM_PREDICT", "512")
)


print("=== LLM CONFIG ===")
print("BASE_URL =", LLM_OLLAMA_BASE_URL)
print("MODEL =", MODEL_NAME)
print("ROUTER_NUM_PREDICT =", ROUTER_NUM_PREDICT)
print("ANSWER_NUM_PREDICT =", ANSWER_NUM_PREDICT)


router_llm = ChatOllama(
    base_url=LLM_OLLAMA_BASE_URL,
    model=MODEL_NAME,
    temperature=0,
    streaming=False,
    num_ctx=4096,
    think=False,
    num_predict=ROUTER_NUM_PREDICT,
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
    num_predict=ANSWER_NUM_PREDICT,
    keep_alive=-1,
)