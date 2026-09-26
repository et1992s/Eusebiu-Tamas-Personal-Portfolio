import os
import pickle
import threading


class ConversationStore:
    """Manages conversation state for Zebio sessions."""

    def __init__(
        self,
        conversations: dict[str, list[dict[str, str]]] | None = None,
    ):
        self.conversations = conversations if conversations is not None else {}

        self.conversation_locks = {}
        self.conversation_locks_guard = threading.Lock()
        self.persistence_lock = threading.Lock()

    def get_or_create(
        self,
        session_id: str,
        system_prompt: str,
    ) -> list[dict[str, str]]:
        if session_id not in self.conversations:
            self.conversations[session_id] = [
                {
                    "role": "system",
                    "content": system_prompt,
                }
            ]

        return self.conversations[session_id]

    def get_lock(self, session_id: str) -> threading.Lock:
        with self.conversation_locks_guard:
            if session_id not in self.conversation_locks:
                self.conversation_locks[session_id] = threading.Lock()

            return self.conversation_locks[session_id]

    def save(self, persistence_file):
        with self.persistence_lock:
            temp_file = f"{persistence_file}.{threading.get_ident()}.tmp"

            with open(temp_file, "wb") as f:
                pickle.dump(self.conversations, f)

            os.replace(temp_file, persistence_file)

    def load(self, persistence_file):
        if not os.path.exists(persistence_file):
            self.conversations = {}
            return self.conversations

        try:
            with open(persistence_file, "rb") as f:
                self.conversations = pickle.load(f)
        except (EOFError, pickle.UnpicklingError):
            self.conversations = {}

        return self.conversations    