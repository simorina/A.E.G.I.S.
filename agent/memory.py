from collections import deque
from typing import Deque, Dict, List, Tuple

Turn = Tuple[str, str]


class ConversationMemory:
    """Store in-memory della cronologia per sessione, con cap sugli ultimi turni."""

    def __init__(self, max_turns: int = 6):
        self._max_messages = max(1, max_turns) * 2
        self._store: Dict[str, Deque[Turn]] = {}

    def append(self, session_id: str, role: str, content: str) -> None:
        buf = self._store.get(session_id)
        if buf is None:
            buf = deque(maxlen=self._max_messages)
            self._store[session_id] = buf
        buf.append((role, content))

    def get(self, session_id: str) -> List[Turn]:
        return list(self._store.get(session_id, []))

    def clear(self, session_id: str) -> None:
        self._store.pop(session_id, None)
