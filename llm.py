from llama_cpp import Llama
from langchain_core.language_models.llms import LLM
from typing import Optional, List


MODEL_PATH = r"D:\models\llm-models\EXAONE-3.5-7.8B-Instruct-Q6_K.gguf"


# ============================================================
# EXAONE 모델 로드
# ============================================================

llm = Llama(
    model_path=MODEL_PATH,

    # GPU 사용
    n_gpu_layers=-1,

    # Context
    n_ctx=4096,

    # CPU threads
    n_threads=8,

    verbose=False,
)


# ============================================================
# LangChain Wrapper
# ============================================================

class EXAONELLM(LLM):

    @property
    def _llm_type(self) -> str:
        return "exaone-gguf"

    @property
    def _identifying_params(self):
        return {
            "model": MODEL_PATH
        }

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager=None,
        **kwargs
    ) -> str:

        result = llm.create_chat_completion(
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=512,
            temperature=0.3,
            stop=stop,
        )

        return result["choices"][0]["message"]["content"]


answer_llm = EXAONELLM()