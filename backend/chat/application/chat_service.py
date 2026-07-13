"""Application service for conversational chat."""

from __future__ import annotations

import asyncio
from typing import Any

import requests

from backend.chat.application.context_builder import ContextBuilder
from backend.chat.application.prompt_builder import PromptBuilder
from backend.chat.application.session_manager import SessionManager
from backend.chat.domain.chat_message import ChatMessage
from backend.chat.domain.conversation import Conversation
from backend.core.container.container import Container
from backend.core.interfaces.base_service import BaseService
from backend.core.logging.logger import LoggerFactory
from backend.llm.client import OllamaClient
from backend.memory.core.memory_manager import MemoryManager
from backend.memory.extractors.llm_memory_extractor import LLMMemoryExtractor


class ChatService(BaseService):
    """Coordinate the chat workflow from session to response."""

    def __init__(
        self,
        session_manager: SessionManager | None = None,
        context_builder: ContextBuilder | None = None,
        prompt_builder: PromptBuilder | None = None,
        ollama_client: OllamaClient | None = None,
        memory_manager: MemoryManager | None = None,
        memory_extractor: LLMMemoryExtractor | None = None,
    ) -> None:
        self.session_manager = session_manager or SessionManager()
        self.context_builder = context_builder or ContextBuilder(
            conversation_store=self.session_manager.conversation_store,
            memory_manager=memory_manager,
        )
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.ollama_client = ollama_client or OllamaClient()
        self.memory_manager = memory_manager or MemoryManager()
        self.memory_extractor = memory_extractor or LLMMemoryExtractor()
        self.logger = LoggerFactory.get_logger("ChatService")

    @property
    def name(self) -> str:
        """Return the service name."""
        return "chat_service"

    async def initialize(self) -> None:
        """Initialize chat service dependencies."""
        self.logger.info("Chat service initialized")

    async def shutdown(self) -> None:
        """Clean up chat service resources."""
        self.logger.info("Chat service shutdown")

    async def send_message(
        self,
        user_id: str,
        message: str,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        """Process a user message and return the assistant response."""
        self.logger.info(
            "send_message() input user_id=%s conversation_id=%s message=%r",
            user_id,
            conversation_id,
            message,
        )
        conversation = self.session_manager.get_or_create_session(
            user_id, conversation_id
        )
        conversation.add_message("user", message)
        self.session_manager.conversation_store.save_conversation(conversation)

        context = self.context_builder.build_context(
            user_id=user_id,
            conversation_id=conversation.id,
            current_message=message,
        )
        self.logger.info(
            "send_message() context output history_count=%s memory_count=%s document_count=%s conversation_id=%s",
            len(context.history),
            len(context.memories),
            len(context.documents),
            conversation.id,
        )
        prompt = self.prompt_builder.build_prompt(context)

        response_text = await asyncio.to_thread(
            self.ollama_client.generate,
            prompt=prompt,
            system=self.prompt_builder.build_system_prompt(),
            temperature=0.2,
        )

        assistant_message = conversation.add_message("assistant", response_text)
        self.session_manager.conversation_store.save_conversation(conversation)

        response_payload = {
            "conversation_id": conversation.id,
            "response": response_text,
            "message_id": assistant_message.id,
        }

        self.logger.info("Starting memory extraction")
        asyncio.create_task(self._extract_memories_after_response(user_id, message))
        return response_payload

    async def get_history(
        self, user_id: str, conversation_id: str
    ) -> list[ChatMessage]:
        """Return the stored history for a conversation."""
        conversation = self.session_manager.get_session(user_id, conversation_id)
        if conversation is None:
            return []
        return conversation.messages

    async def get_conversation(
        self, user_id: str, conversation_id: str
    ) -> Conversation | None:
        """Return the conversation if it belongs to the user."""
        return self.session_manager.get_session(user_id, conversation_id)

    async def _extract_memories_after_response(
        self, user_id: str, message: str
    ) -> None:
        """Extract long-term memories after the response is returned."""
        try:
            extracted = await asyncio.to_thread(
                self.memory_extractor.process,
                user_id,
                message,
            )
            self.logger.info(
                "Memory extraction task completed with %d memories",
                len(extracted),
            )
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            self.logger.exception("Memory extraction failed: %s", exc)


def build_chat_service(container: Container | None = None) -> ChatService:
    """Create or resolve a chat service from the shared container."""
    shared_container = container or Container()
    if not shared_container.exists("chat_service"):
        service = ChatService()
        shared_container.register("chat_service", service)
    return shared_container.resolve("chat_service")
