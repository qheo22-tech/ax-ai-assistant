from collections import deque


MAX_MESSAGES = 10
MAX_CONTEXT_MESSAGES = 2


class ConversationMemory:

    def __init__(self):
        # 전체 대화 보관
        self.messages = deque(maxlen=MAX_MESSAGES)

        # 마지막 업무 처리 결과
        self.last_result = None

    def add_user(self, message: str):
        self.messages.append({
            "role": "user",
            "content": message
        })

    def add_assistant(self, message: str):
        self.messages.append({
            "role": "assistant",
            "content": message
        })

    def set_last_result(self, result: dict):
        self.last_result = result

    def get_messages(self):
        return list(self.messages)

    def get_recent_messages(self):
        """
        LLM에 전달할 최근 대화만 반환
        """
        return list(self.messages)[-MAX_CONTEXT_MESSAGES:]

    def get_last_result(self):
        return self.last_result