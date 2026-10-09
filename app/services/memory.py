"""Lightweight in-process conversation memory (no vector DB). Lost on restart; single-process only."""

from collections import OrderedDict, deque

from app.llm.base import ChatMessage


class ConversationMemory:
    def __init__(self, max_messages: int = 10, max_conversations: int = 1000):
        self.max_messages = max_messages
        self.max_conversations = max_conversations
        self._store: OrderedDict[str, deque[ChatMessage]] = OrderedDict()

    def history(self, conversation_id: str) -> list[ChatMessage]:
        return list(self._store.get(conversation_id, ()))

    def append_turn(self, conversation_id: str, user_message: str, assistant_message: str) -> None:
        if self.max_messages == 0:
            return
        messages = self._store.setdefault(conversation_id, deque(maxlen=self.max_messages))
        messages.append(ChatMessage(role="user", content=user_message))
        messages.append(ChatMessage(role="assistant", content=assistant_message))
        self._store.move_to_end(conversation_id)
        while len(self._store) > self.max_conversations:
            self._store.popitem(last=False)

    def clear(self, conversation_id: str) -> bool:
        return self._store.pop(conversation_id, None) is not None
