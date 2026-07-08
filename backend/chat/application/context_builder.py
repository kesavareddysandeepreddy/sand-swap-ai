"""Context assembly for chat prompts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from backend.chat.domain.chat_message import ChatMessage
from backend.chat.infrastructure.conversation_store import ConversationStore
from backend.memory.core.memory_manager import MemoryManager


@dataclass(slots=True)
class PromptContext:
    """Structured context passed to the prompt builder."""

    history: list[ChatMessage] = field(default_factory=list)
    memories: list[Any] = field(default_factory=list)
    current_message: str = ""
    token_budget: int = 2048
    summarization_enabled: bool = False


class ContextBuilder:
    """Build a prompt context from conversation history and memories."""

    def __init__(
        self,
        conversation_store: ConversationStore | None = None,
        memory_manager: MemoryManager | None = None,
    ) -> None:
        self.conversation_store = conversation_store or ConversationStore()
        self.memory_manager = memory_manager

    def build_context(
        self,
        user_id: str,
        conversation_id: str,
        current_message: str,
        max_history_messages: int = 8,
        max_memories: int = 5,
    ) -> PromptContext:
        """Assemble recent history, long-term memories, and future budget metadata."""
        conversation = self.conversation_store.get_conversation(conversation_id)
        if conversation is None:
            conversation = self.conversation_store.create_conversation(
                user_id, conversation_id
            )

        history = conversation.get_recent_messages(max_history_messages)

        memories: list[Any] = []
        if self.memory_manager is not None:
            search_terms: list[str] = []
            for term in [current_message, *[message.content for message in history]]:
                if not term:
                    continue
                tokens = re.findall(r"[A-Za-z0-9]+", term.lower())
                search_terms.extend(token for token in tokens if len(token) > 2)

            seen: set[str] = set()
            for term in search_terms:
                if not term or term in seen:
                    continue
                seen.add(term)
                matches = self.memory_manager.search(user_id, term)
                if matches:
                    memories.extend(matches)
                    if len(memories) >= max_memories:
                        break
            memories = memories[:max_memories]

        return PromptContext(
            history=history,
            memories=memories,
            current_message=current_message,
            token_budget=2048,
            summarization_enabled=False,
        )

    def build_history_context(
        self, conversation_id: str, max_history_messages: int = 8
    ) -> list[ChatMessage]:
        """Return recent conversation history for a conversation."""
        conversation = self.conversation_store.get_conversation(conversation_id)
        if conversation is None:
            return []
        return conversation.get_recent_messages(max_history_messages)

    def build_memory_context(
        self, user_id: str, current_message: str, max_memories: int = 5
    ) -> list[Any]:
        """Return relevant long-term memories for the current request."""
        if self.memory_manager is None:
            return []
        return self.memory_manager.search(user_id, current_message)[:max_memories]
