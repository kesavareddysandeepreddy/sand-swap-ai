"""Application service for conversational chat."""

from __future__ import annotations

import asyncio
import re
from typing import Any

import requests

from backend.agents.context import AgentExecutionContext
from backend.agents.runtime import AgentRuntime
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
        agent_runtime: AgentRuntime | None = None,
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
        self.agent_runtime = agent_runtime
        self.logger = LoggerFactory.get_logger("ChatService")

    @staticmethod
    def _slugify_key_component(value: str) -> str:
        """Convert free-form text into a safe key fragment."""
        normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
        return normalized.strip("_") or "value"

    def _persist_fast_profile_memories(
        self,
        *,
        user_id: str,
        message: str,
        workspace_id: str | None,
        project_id: str | None,
    ) -> int:
        """Persist obvious profile memories with low-cost regex rules.

        This keeps first-pass profile facts available for subsequent
        conversations without waiting on a full LLM extraction step.
        """
        text = message.strip()
        if not text:
            return 0

        extracted: list[tuple[str, str, str]] = []
        for segment in re.split(r"(?<=[.!?])\s+", text):
            candidate = segment.strip()
            if not candidate:
                continue

            name_match = re.match(
                r"^my name is\s+(.+?)[.!?]?$", candidate, re.IGNORECASE
            )
            if name_match:
                extracted.append(
                    ("name", name_match.group(1).strip().lower(), "identity")
                )
                continue

            occupation_match = re.match(
                r"^(?:i am a|i am an|i work as)\s+(.+?)[.!?]?$",
                candidate,
                re.IGNORECASE,
            )
            if occupation_match:
                occupation = occupation_match.group(1).strip()
                extracted.append(("occupation", occupation, "work"))
                extracted.append(("role", occupation, "identity"))
                continue

            preferred_match = re.match(
                r"^i prefer\s+(.+?)[.!?]?$", candidate, re.IGNORECASE
            )
            if preferred_match:
                extracted.append(
                    (
                        "preferred_language",
                        preferred_match.group(1).strip(),
                        "preference",
                    )
                )
                continue

            favorite_match = re.match(
                r"^my favorite\s+(.+?)\s+is\s+(.+?)[.!?]?$",
                candidate,
                re.IGNORECASE,
            )
            if favorite_match:
                subject = self._slugify_key_component(favorite_match.group(1))
                value = favorite_match.group(2).strip()
                extracted.append((f"favorite_{subject}", value, "preference"))

        saved_count = 0
        for key, value, category in extracted:
            stored = self.memory_manager.remember(
                user_id=user_id,
                memory_type="fact",
                key=key,
                value=value,
                category=category,
                importance=0.9,
                confidence=0.9,
                project_id=project_id,
                metadata={"workspace_id": workspace_id},
            )
            if stored is not None:
                saved_count += 1

        return saved_count

    def _schedule_memory_extraction(
        self,
        *,
        user_id: str,
        message: str,
        workspace_id: str | None,
        project_id: str | None,
    ) -> None:
        """Run full memory extraction without blocking the response path."""
        task = asyncio.create_task(
            self._extract_memories_after_response(
                user_id,
                message,
                workspace_id=workspace_id,
                project_id=project_id,
            )
        )

        def _on_done(completed: asyncio.Task[None]) -> None:
            try:
                completed.result()
            except Exception:  # noqa: BLE001
                self.logger.exception("Deferred memory extraction task failed")

        task.add_done_callback(_on_done)

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
        restored = self.session_manager.restore_sessions_from_store()
        for conversation in restored:
            workspace_id = "default"
            project_id = "default"
            if self.ownership_service is not None:
                owner = self.ownership_service.get_conversation_owner(conversation.id)
                if owner is not None:
                    workspace_id = owner.workspace_id
                    project_id = owner.project_id
            self.logger.debug(
                "RESTORE_CONVERSATIONS conversation_id=%s user_id=%s workspace_id=%s project_id=%s database_result=%s cache_result=%s",
                conversation.id,
                conversation.user_id,
                workspace_id,
                project_id,
                "db_loaded",
                "cache_restored",
            )
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
        self.logger.debug(
            "CHAT_DEBUG_REQUEST question=%r workspace_id=%s owner_id=%s project_id=%s conversation_id=%s",
            message,
            workspace_id,
            user_id,
            project_id,
            conversation_id,
        )
        existing_conversation = None
        if conversation_id is not None:
            existing_conversation, database_result, cache_result = (
                self.session_manager.get_session_with_meta(
                    user_id,
                    conversation_id,
                )
            )
            self.logger.debug(
                "LOAD_CONVERSATION conversation_id=%s user_id=%s workspace_id=%s project_id=%s database_result=%s cache_result=%s",
                self.session_manager._scope_conversation_id(user_id, conversation_id),
                user_id,
                workspace_id or "default",
                project_id or "default",
                database_result,
                cache_result,
            )
        conversation, create_database_result, create_cache_result, created = (
            self.session_manager.get_or_create_session_with_meta(
                user_id, conversation_id
            )
        )
        if created:
            self.logger.debug(
                "CREATE_CONVERSATION conversation_id=%s user_id=%s workspace_id=%s project_id=%s database_result=%s cache_result=%s",
                conversation.id,
                user_id,
                workspace_id or "default",
                project_id or "default",
                create_database_result,
                create_cache_result,
            )
        if existing_conversation is None:
            self._ensure_conversation_ownership(
                user_id,
                conversation.id,
                workspace_id=workspace_id,
                project_id=project_id,
            )
        conversation.add_message("user", message)
        _, save_cache_result = self.session_manager.persist_session(conversation)
        self.logger.debug(
            "SAVE_CONVERSATION conversation_id=%s user_id=%s workspace_id=%s project_id=%s database_result=%s cache_result=%s",
            conversation.id,
            user_id,
            workspace_id or "default",
            project_id or "default",
            "db_saved",
            save_cache_result,
        )

        fast_memories_saved = self._persist_fast_profile_memories(
            user_id=user_id,
            message=message,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        if fast_memories_saved:
            self.logger.debug(
                "CHAT_DEBUG_FAST_MEMORY_CAPTURE saved=%s user_id=%s conversation_id=%s",
                fast_memories_saved,
                user_id,
                conversation.id,
            )

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
        self.logger.debug(
            "CHAT_DEBUG_RETRIEVAL workspace_id=%s owner_id=%s knowledge_sources_searched=documents+github "
            "documents_retrieved=%s chunks_retrieved=%s similarity_scores=%s applied_filters=%s",
            workspace_id,
            user_id,
            len({chunk.document_name for chunk in context.documents}),
            len(context.documents),
            [round(chunk.score, 6) for chunk in context.documents[:10]],
            {
                "workspace_id": workspace_id,
                "project_id": project_id,
                "owner_id": user_id,
            },
        )
        prompt = self.prompt_builder.build_prompt(context)
        prompt_injected = bool(context.documents)
        context_length = sum(len(chunk.text) for chunk in context.documents)
        self.logger.info(
            "PROMPT_CONTEXT_INJECTED chunks=%s injected=%s citations=%s prompt_chars=%s",
            len(context.documents),
            prompt_injected,
            len(context.document_citations),
            len(prompt),
        )
        self.logger.debug(
            "CHAT_DEBUG_PROMPT_CONTEXT context_chars=%s prompt_chars=%s memories=%s history_turns=%s",
            context_length,
            len(prompt),
            len(context.memories),
            len(context.history),
        )
        if prompt_injected:
            self.logger.info(
                "PROMPT_CONTEXT_DOCUMENTS %s",
                [chunk.document_name for chunk in context.documents],
            )
            self.logger.info(
                "PROMPT_CONTEXT_CHUNK_IDS %s",
                [chunk.chunk_id for chunk in context.documents],
            )
            self.logger.info(
                "PROMPT_CONTEXT_SIMILARITY_SCORES %s",
                [round(chunk.score, 6) for chunk in context.documents],
            )
        self.logger.info(
            "PROMPT_CONTEXT_LENGTH context_chars=%s prompt_chars=%s",
            context_length,
            len(prompt),
        )

        normalized_model = model.strip() if model else None
        system_prompt = self.prompt_builder.build_system_prompt()
        self.logger.info("LLM_SYSTEM_PROMPT %r", system_prompt)
        self.logger.info("LLM_INPUT %r", prompt)

        if self.agent_runtime is not None:
            execution_context = AgentExecutionContext(
                conversation=conversation,
                workspace_id=workspace_id,
                project_id=project_id,
                knowledge_object_ids=list(conversation.knowledge_object_ids),
                knowledge_context=getattr(context, "knowledge_context", ""),
                memory_context=list(context.memories),
                rag_context=list(context.documents),
                vision_context=getattr(context, "multimodal_context", ""),
                user_prompt=message,
                prompt=prompt,
                system_prompt=system_prompt,
                model=normalized_model,
                metadata={"temperature": 0.2, "owner_id": user_id},
            )
            self.logger.info(
                "AGENT_RUNTIME_REQUEST query=%r owner_id=%s workspace_id=%s project_id=%s chunks_retrieved=%s chunks_in_prompt=%s",
                message,
                user_id,
                workspace_id,
                project_id,
                len(context.documents),
                len(context.documents),
            )
            runtime_result = await asyncio.to_thread(
                self.agent_runtime.execute,
                execution_context,
            )
            response_text = runtime_result.response_text
        else:
            self.logger.info(
                "LLM_REQUEST query=%r owner_id=%s workspace_id=%s project_id=%s chunks_retrieved=%s chunks_in_prompt=%s",
                message,
                user_id,
                workspace_id,
                project_id,
                len(context.documents),
                len(context.documents),
            )
            import time as _time

            _llm_start = _time.monotonic()
            response_text = await asyncio.to_thread(
                self.ollama_client.generate,
                prompt=prompt,
                model=normalized_model,
                system=system_prompt,
                temperature=0.2,
            )
            _llm_elapsed_ms = int((_time.monotonic() - _llm_start) * 1000)
            self.logger.debug(
                "CHAT_DEBUG_LLM_TIMING response_ms=%s model=%s",
                _llm_elapsed_ms,
                normalized_model or "default",
            )

        response_text = self._append_references_if_any(
            self._clean_inline_retrieval_artifacts(response_text),
            context.documents,
        )

        self.logger.info("LLM_OUTPUT %r", response_text)
        self.logger.debug(
            "CHAT_DEBUG_LLM_RESPONSE response_chars=%s",
            len(response_text),
        )

        assistant_message = conversation.add_message("assistant", response_text)
        _, save_cache_result = self.session_manager.persist_session(conversation)
        self.logger.debug(
            "SAVE_CONVERSATION conversation_id=%s user_id=%s workspace_id=%s project_id=%s database_result=%s cache_result=%s",
            conversation.id,
            user_id,
            workspace_id or "default",
            project_id or "default",
            "db_saved",
            save_cache_result,
        )

        response_payload = {
            "conversation_id": conversation.id,
            "response": response_text,
            "message_id": assistant_message.id,
        }

        self.logger.info("Starting deferred memory extraction")
        self._schedule_memory_extraction(
            user_id=user_id,
            message=message,
            workspace_id=workspace_id,
            project_id=project_id,
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

    @staticmethod
    def _clean_inline_retrieval_artifacts(text: str) -> str:
        """Remove inline retrieval metadata fragments from model output."""
        cleaned = text
        cleaned = re.sub(
            r"\[[^\]]+\]\[page=[^\]]*\]\[section=[^\]]*\]\[chunk=[^\]]*\]",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\[chunk=[^\]]*\]", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\[page=[^\]]*\]", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\[section=[^\]]*\]", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(
            r"^\s*(according to|based on)\s+(the\s+)?(provided\s+documents|retrieved\s+documents|retrieved\s+context)\s*,?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    @staticmethod
    def _append_references_if_any(answer_text: str, documents: list[Any]) -> str:
        """Append a clean deduplicated references section when RAG context exists."""
        if not documents:
            return answer_text

        ordered_names: list[str] = []
        seen_names: set[str] = set()
        first_section_by_name: dict[str, str] = {}

        for chunk in documents:
            document_name = str(getattr(chunk, "document_name", "")).strip()
            if not document_name:
                continue
            if document_name not in seen_names:
                seen_names.add(document_name)
                ordered_names.append(document_name)

            section = str(getattr(chunk, "metadata", {}).get("section", "")).strip()
            if (
                section
                and section != "-"
                and document_name not in first_section_by_name
            ):
                first_section_by_name[document_name] = section

        if not ordered_names:
            return answer_text

        reference_lines: list[str] = []
        for name in ordered_names:
            section = first_section_by_name.get(name, "")
            if section:
                reference_lines.append(f"• {name} ({section})")
            else:
                reference_lines.append(f"• {name}")

        return f"{answer_text}\n\n---\nReferences\n{'\n'.join(reference_lines)}"

    async def list_conversations(
        self,
        *,
        user_id: str,
        workspace_id: str | None = None,
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return persisted conversations visible to the scoped user context."""
        visible: list[dict[str, Any]] = []

        if self.ownership_service is None:
            conversations = self.session_manager.conversation_store.list_conversations(
                user_id
            )
            for conversation in conversations:
                self.logger.info(
                    "LIST_TRACE conversation_id=%s source=%s owner_id=%s workspace_id=%s project_id=%s",
                    conversation.id,
                    "conversation_db",
                    user_id,
                    workspace_id or "default",
                    project_id or "default",
                )
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

        owner_rows = self.ownership_service.list_conversation_owners(user_id)
        for owner in owner_rows:
            if workspace_id is not None and owner.workspace_id != workspace_id:
                continue
            if project_id is not None and owner.project_id != project_id:
                continue

            source = "ownership_repo"
            conversation = self.session_manager.conversation_store.get_conversation(
                owner.conversation_id
            )
            if conversation is not None:
                source = "conversation_db"
            else:
                cached = self.session_manager._sessions.get(
                    (user_id, owner.conversation_id)
                )
                if cached is not None:
                    source = "cache"
                    conversation = cached

            if conversation is None:
                try:
                    self.ownership_service.unassign_conversation_owner(
                        owner.conversation_id
                    )
                except Exception:  # noqa: BLE001
                    pass
                continue
            if conversation.user_id != user_id:
                continue

            self.logger.info(
                "LIST_TRACE conversation_id=%s source=%s owner_id=%s workspace_id=%s project_id=%s",
                conversation.id,
                source,
                owner.user_id,
                owner.workspace_id,
                owner.project_id,
            )

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

    async def delete_conversation(
        self,
        *,
        user_id: str,
        conversation_id: str,
        workspace_id: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, bool]:
        """Delete a conversation permanently from storage and runtime cache."""
        scoped_conversation_id = self.session_manager._scope_conversation_id(
            user_id,
            conversation_id,
        )
        legacy_conversation_id = self.session_manager._legacy_conversation_id(
            user_id,
            conversation_id,
        )
        owner_candidate_ids = [scoped_conversation_id]
        if legacy_conversation_id and legacy_conversation_id != scoped_conversation_id:
            owner_candidate_ids.append(legacy_conversation_id)
        trace_reference_ids = [conversation_id, scoped_conversation_id]
        if legacy_conversation_id not in trace_reference_ids:
            trace_reference_ids.append(legacy_conversation_id)

        rows_before_delete = (
            self.session_manager.conversation_store.find_rows_referencing(
                trace_reference_ids,
                user_id=user_id,
            )
        )
        self.logger.info(
            "DELETE_TRACE_STEP3 before_delete reference_ids=%s matching_rows=%s",
            trace_reference_ids,
            rows_before_delete,
        )
        owner = None
        if self.ownership_service is not None:
            owner = self.ownership_service.get_conversation_owner(
                scoped_conversation_id
            )
            if owner is None and legacy_conversation_id != scoped_conversation_id:
                owner = self.ownership_service.get_conversation_owner(
                    legacy_conversation_id
                )
            if owner is not None and owner.user_id != user_id:
                raise ValueError("Conversation not found")
            if (
                owner is not None
                and workspace_id is not None
                and owner.workspace_id != workspace_id
            ):
                raise ValueError("Conversation not found")
            if (
                owner is not None
                and project_id is not None
                and owner.project_id != project_id
            ):
                raise ValueError("Conversation not found")

        self.logger.info(
            "DELETE_TRACE_STEP4 execute_delete reference_ids=%s",
            trace_reference_ids,
        )
        database_deleted, cache_deleted = self.session_manager.delete_session(
            user_id,
            conversation_id,
        )

        rows_after_delete = (
            self.session_manager.conversation_store.find_rows_referencing(
                trace_reference_ids,
                user_id=user_id,
            )
        )
        self.logger.info(
            "DELETE_TRACE_STEP5 after_delete reference_ids=%s remaining_rows=%s",
            trace_reference_ids,
            rows_after_delete,
        )

        owner_deleted = False
        if self.ownership_service is not None:
            for owner_candidate_id in owner_candidate_ids:
                try:
                    owner_deleted = (
                        self.ownership_service.unassign_conversation_owner(
                            owner_candidate_id
                        )
                        or owner_deleted
                    )
                except Exception:  # noqa: BLE001
                    continue

        # Conversation-specific memory links are not tracked in current memory schema.
        memory_deleted = False
        database_result = "db_deleted" if database_deleted else "db_not_found"
        cache_result = "cache_deleted" if cache_deleted else "cache_not_found"
        self.logger.info(
            "DELETE_TRACE conversation_id=%s deleted_from_cache=%s deleted_from_conversation_db=%s deleted_from_owner_table=%s",
            conversation_id,
            cache_deleted,
            database_deleted,
            owner_deleted,
        )
        self.logger.debug(
            "DELETE_CONVERSATION conversation_id=%s user_id=%s workspace_id=%s project_id=%s database_result=%s cache_result=%s database_deleted=%s cache_deleted=%s memory_deleted=%s owner_deleted=%s",
            scoped_conversation_id,
            user_id,
            workspace_id or "default",
            project_id or "default",
            database_result,
            cache_result,
            database_deleted,
            cache_deleted,
            memory_deleted,
            owner_deleted,
        )

        visible_after_delete = await self.list_conversations(
            user_id=user_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        visible_ids_after_delete = [item["id"] for item in visible_after_delete]
        matching_visible_ids_after_delete = [
            visible_id
            for visible_id in visible_ids_after_delete
            if visible_id in trace_reference_ids
        ]
        self.logger.info(
            "DELETE_TRACE_STEP6 list_after_delete all_ids=%s matching_ids=%s",
            visible_ids_after_delete,
            matching_visible_ids_after_delete,
        )
        self.logger.info(
            "DELETE_TRACE_STEP7 compare before_rows=%s after_rows=%s list_matching_ids=%s",
            [row["id"] for row in rows_before_delete],
            [row["id"] for row in rows_after_delete],
            matching_visible_ids_after_delete,
        )

        return {
            "deleted": database_deleted,
            "database_deleted": database_deleted,
            "cache_deleted": cache_deleted,
            "memory_deleted": memory_deleted,
        }

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
            self.logger.debug(
                "CHAT_DEBUG_MEMORY_EXTRACTED count=%s keys=%s",
                len(extracted),
                [getattr(m, "key", None) for m in extracted],
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
