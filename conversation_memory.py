from collections import deque


MAX_TURNS = 10


class ConversationMemory:

    def __init__(self):
        self.messages = deque(maxlen=MAX_TURNS)
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

    def get_last_result(self):
        return self.last_result