"""Session management for chat conversations."""

from __future__ import annotations

from uuid import uuid4

from backend.chat.domain.conversation import Conversation
from backend.chat.infrastructure.conversation_store import ConversationStore
from backend.core.logging.logger import LoggerFactory


class SessionManager:
    """Manage user-scoped chat sessions and conversation state."""

    def __init__(self, conversation_store: ConversationStore | None = None) -> None:
        self.conversation_store = conversation_store or ConversationStore()
        self._sessions: dict[tuple[str, str], Conversation] = {}
        self.logger = LoggerFactory.get_logger("SessionManager")

    @staticmethod
    def _scope_conversation_id(user_id: str, conversation_id: str | None) -> str:
        """Create a user-scoped conversation identifier."""
        if conversation_id is not None and conversation_id.startswith(f"{user_id}:"):
            return conversation_id
        return (
            f"{user_id}:{conversation_id}"
            if conversation_id is not None
            else str(uuid4())
        )

    @staticmethod
    def _legacy_conversation_id(user_id: str, conversation_id: str) -> str:
        """Return the unscoped legacy identifier for a scoped conversation id."""
        prefix = f"{user_id}:"
        return (
            conversation_id[len(prefix) :]
            if conversation_id.startswith(prefix)
            else conversation_id
        )

    def get_or_create_session(
        self,
        user_id: str,
        conversation_id: str | None = None,
    ) -> Conversation:
        """Return an existing session or create a new one for a user."""
        conversation, _, _, _ = self.get_or_create_session_with_meta(
            user_id,
            conversation_id,
        )
        return conversation

    def get_or_create_session_with_meta(
        self,
        user_id: str,
        conversation_id: str | None = None,
    ) -> tuple[Conversation, str, str, bool]:
        """Return a session and operation metadata.

        Returns:
            (conversation, database_result, cache_result, created)
        """
        resolved_id = conversation_id or str(uuid4())
        scoped_conversation_id = self._scope_conversation_id(user_id, resolved_id)
        cache_key = (user_id, scoped_conversation_id)
        cache_result = "cache_hit" if cache_key in self._sessions else "cache_miss"

        conversation = self.conversation_store.get_conversation(scoped_conversation_id)
        database_result = "db_loaded"
        created = False
        if conversation is None:
            conversation = self.conversation_store.create_conversation(
                user_id=user_id,
                conversation_id=scoped_conversation_id,
            )
            database_result = "db_created"
            created = True
        elif conversation.user_id != user_id:
            raise ValueError("Conversation does not belong to the requested user.")

        self._sessions[cache_key] = conversation
        return conversation, database_result, cache_result, created

    def get_session(self, user_id: str, conversation_id: str) -> Conversation | None:
        """Fetch a session if it exists and belongs to the user."""
        conversation, _, _ = self.get_session_with_meta(user_id, conversation_id)
        return conversation

    def get_session_with_meta(
        self,
        user_id: str,
        conversation_id: str,
    ) -> tuple[Conversation | None, str, str]:
        """Fetch a session with database and cache result metadata."""
        scoped_conversation_id = self._scope_conversation_id(user_id, conversation_id)
        cache_key = (user_id, scoped_conversation_id)
        cache_result = "cache_hit" if cache_key in self._sessions else "cache_miss"
        conversation = self.conversation_store.get_conversation(scoped_conversation_id)
        if conversation is None:
            return None, "db_not_found", cache_result
        if conversation.user_id != user_id:
            return None, "db_owner_mismatch", cache_result

        self._sessions[cache_key] = conversation
        return conversation, "db_loaded", cache_result

    def persist_session(
        self,
        conversation: Conversation,
    ) -> tuple[bool, str]:
        """Persist a conversation and update runtime cache."""
        self.conversation_store.save_conversation(conversation)
        self._sessions[(conversation.user_id, conversation.id)] = conversation
        return True, "cache_updated"

    def append_message(
        self, user_id: str, conversation_id: str, role: str, content: str
    ) -> Conversation:
        """Append a message to a session and persist it."""
        conversation = self.get_or_create_session(user_id, conversation_id)
        conversation.add_message(role, content)
        self.persist_session(conversation)
        return conversation

    def restore_sessions_from_store(self) -> list[Conversation]:
        """Restore runtime cache from the persistent repository."""
        restored: list[Conversation] = []
        for conversation in self.conversation_store.list_conversations():
            self._sessions[(conversation.user_id, conversation.id)] = conversation
            restored.append(conversation)
        self.logger.debug("RESTORE_CONVERSATIONS restored_count=%s", len(restored))
        return restored

    def delete_session(self, user_id: str, conversation_id: str) -> tuple[bool, bool]:
        """Delete a conversation from runtime cache and persistent storage."""
        scoped_conversation_id = self._scope_conversation_id(user_id, conversation_id)
        legacy_conversation_id = self._legacy_conversation_id(
            user_id,
            conversation_id,
        )
        candidate_ids = [scoped_conversation_id]
        if legacy_conversation_id and legacy_conversation_id != scoped_conversation_id:
            candidate_ids.append(legacy_conversation_id)

        cache_deleted = False

        for candidate_id in candidate_ids:
            cache_key = (user_id, candidate_id)
            if cache_key in self._sessions:
                del self._sessions[cache_key]
                cache_deleted = True

        # Remove any stale cache aliases that point at either candidate id.
        stale_keys = [
            key
            for key, conversation in self._sessions.items()
            if key[0] == user_id and conversation.id in candidate_ids
        ]
        for key in stale_keys:
            del self._sessions[key]
            cache_deleted = True

        database_deleted = False
        for candidate_id in candidate_ids:
            database_deleted = (
                self.conversation_store.delete_conversation(candidate_id)
                or database_deleted
            )
        return database_deleted, cache_deleted
