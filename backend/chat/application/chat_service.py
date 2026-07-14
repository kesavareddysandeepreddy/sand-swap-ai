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
from backend.services.ownership_service import OwnershipService


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
        ownership_service: OwnershipService | None = None,
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
        self.ownership_service = ownership_service
        self.logger = LoggerFactory.get_logger("ChatService")

    def _resolve_default_workspace_for_user(self, user_id: str) -> str:
        """Resolve a user's default workspace id with a legacy-safe fallback."""
        if self.ownership_service is None:
            return "default"
        try:
            projects = self.ownership_service.list_projects_for_user(user_id)
            if not projects:
                return "default"
            default_project = next(
                (
                    project
                    for project in projects
                    if project.name.strip().lower()
                    in {"default", "default workspace", "personal workspace"}
                ),
                None,
            )
            return (default_project or projects[0]).id
        except Exception:  # noqa: BLE001
            return "default"

    def _ensure_conversation_ownership(
        self,
        user_id: str,
        conversation_id: str,
        *,
        workspace_id: str | None,
        project_id: str | None,
    ) -> None:
        """Persist conversation ownership and project association safeguards."""
        if self.ownership_service is None:
            return

        resolved_workspace_id = (
            workspace_id or self._resolve_default_workspace_for_user(user_id)
        )
        resolved_project_id = project_id or "default"
        try:
            self.ownership_service.assign_project_owner(
                project_id=resolved_workspace_id,
                user_id=user_id,
            )
            self.ownership_service.assign_conversation_owner(
                conversation_id=conversation_id,
                user_id=user_id,
                workspace_id=resolved_workspace_id,
                project_id=resolved_project_id,
            )
            return
        except Exception:  # noqa: BLE001
            fallback_workspace_id = "default"
            try:
                self.ownership_service.assign_project_owner(
                    project_id=fallback_workspace_id,
                    user_id=user_id,
                )
                self.ownership_service.assign_conversation_owner(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    workspace_id=fallback_workspace_id,
                    project_id=resolved_project_id,
                )
            except Exception:  # noqa: BLE001
                return

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
        model: str | None = None,
        workspace_id: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        """Process a user message and return the assistant response."""
        self.logger.info(
            "send_message() input user_id=%s conversation_id=%s message=%r",
            user_id,
            conversation_id,
            message,
        )
        existing_conversation = None
        if conversation_id is not None:
            existing_conversation = self.session_manager.get_session(
                user_id,
                conversation_id,
            )
        conversation = self.session_manager.get_or_create_session(
            user_id, conversation_id
        )
        if existing_conversation is None:
            self._ensure_conversation_ownership(
                user_id,
                conversation.id,
                workspace_id=workspace_id,
                project_id=project_id,
            )
        conversation.add_message("user", message)
        self.session_manager.conversation_store.save_conversation(conversation)

        context = self.context_builder.build_context(
            user_id=user_id,
            conversation_id=conversation.id,
            current_message=message,
            workspace_id=workspace_id,
            project_id=project_id,
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
            model=(model.strip() if model else None),
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
        asyncio.create_task(
            self._extract_memories_after_response(
                user_id,
                message,
                workspace_id=workspace_id,
                project_id=project_id,
            )
        )
        return response_payload

    async def get_history(
        self, user_id: str, conversation_id: str
    ) -> list[ChatMessage]:
        """Return the stored history for a conversation."""
        conversation = self.session_manager.get_session(user_id, conversation_id)
        if conversation is None:
            return []
        return conversation.messages

    @staticmethod
    def _conversation_title(conversation: Conversation) -> str:
        """Derive a stable UI title from the first user message."""
        first_user = next(
            (message for message in conversation.messages if message.role == "user"),
            None,
        )
        seed = (
            first_user.content.strip()
            if first_user is not None
            else (
                conversation.messages[0].content.strip()
                if conversation.messages
                else ""
            )
        )
        if not seed:
            return "New conversation"
        return f"{seed[:36]}..." if len(seed) > 36 else seed

    async def list_conversations(
        self,
        *,
        user_id: str,
        workspace_id: str | None = None,
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return persisted conversations visible to the scoped user context."""
        conversations = self.session_manager.conversation_store.list_conversations(
            user_id
        )
        visible: list[dict[str, Any]] = []

        for conversation in conversations:
            if self.ownership_service is not None:
                owner = self.ownership_service.get_conversation_owner(conversation.id)
                if owner is None or owner.user_id != user_id:
                    continue
                if workspace_id is not None and owner.workspace_id != workspace_id:
                    continue
                if project_id is not None and owner.project_id != project_id:
                    continue

            visible.append(
                {
                    "id": conversation.id,
                    "title": self._conversation_title(conversation),
                    "updated_at": conversation.updated_at.isoformat(),
                    "messages": [
                        message.to_dict() for message in conversation.messages
                    ],
                }
            )

        visible.sort(key=lambda item: item["updated_at"], reverse=True)
        return visible

    async def get_conversation(
        self, user_id: str, conversation_id: str
    ) -> Conversation | None:
        """Return the conversation if it belongs to the user."""
        return self.session_manager.get_session(user_id, conversation_id)

    async def _extract_memories_after_response(
        self,
        user_id: str,
        message: str,
        *,
        workspace_id: str | None = None,
        project_id: str | None = None,
    ) -> None:
        """Extract long-term memories after the response is returned."""
        try:
            extracted = await asyncio.to_thread(
                self.memory_extractor.process,
                user_id,
                message,
                workspace_id=workspace_id,
                project_id=project_id,
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
