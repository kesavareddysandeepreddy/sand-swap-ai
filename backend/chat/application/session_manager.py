"""Session management for chat conversations."""

from __future__ import annotations

from uuid import uuid4

from backend.chat.domain.conversation import Conversation
from backend.chat.infrastructure.conversation_store import ConversationStore


class SessionManager:
    """Manage user-scoped chat sessions and conversation state."""

    def __init__(self, conversation_store: ConversationStore | None = None) -> None:
        self.conversation_store = conversation_store or ConversationStore()
        self._sessions: dict[tuple[str, str], Conversation] = {}

    @staticmethod
    def _scope_conversation_id(user_id: str, conversation_id: str | None) -> str:
        """Create a user-scoped conversation identifier."""
        return (
            f"{user_id}:{conversation_id}"
            if conversation_id is not None
            else str(uuid4())
        )

    def get_or_create_session(
        self,
        user_id: str,
        conversation_id: str | None = None,
    ) -> Conversation:
        """Return an existing session or create a new one for a user."""
        resolved_id = conversation_id or str(uuid4())
        scoped_conversation_id = self._scope_conversation_id(user_id, resolved_id)
        cache_key = (user_id, scoped_conversation_id)

        if cache_key in self._sessions:
            return self._sessions[cache_key]

        conversation = self.conversation_store.get_conversation(scoped_conversation_id)
        if conversation is None:
            conversation = self.conversation_store.create_conversation(
                user_id=user_id,
                conversation_id=scoped_conversation_id,
            )
        elif conversation.user_id != user_id:
            raise ValueError("Conversation does not belong to the requested user.")

        self._sessions[cache_key] = conversation
        return conversation

    def get_session(self, user_id: str, conversation_id: str) -> Conversation | None:
        """Fetch a session if it exists and belongs to the user."""
        scoped_conversation_id = self._scope_conversation_id(user_id, conversation_id)
        conversation = self.conversation_store.get_conversation(scoped_conversation_id)
        if conversation is None or conversation.user_id != user_id:
            return None
        return conversation

    def append_message(
        self, user_id: str, conversation_id: str, role: str, content: str
    ) -> Conversation:
        """Append a message to a session and persist it."""
        conversation = self.get_or_create_session(user_id, conversation_id)
        conversation.add_message(role, content)
        self.conversation_store.save_conversation(conversation)
        return conversation
