"""Context assembly for chat prompts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.chat.domain.chat_message import ChatMessage
from backend.chat.infrastructure.conversation_store import ConversationStore
from backend.core.logging.logger import LoggerFactory
from backend.memory.core.memory_manager import MemoryManager
from backend.multimodal.pipeline.processor import (
    MultimodalPipeline,
    MultimodalPipelineContext,
)
from backend.rag.application.document_service import (
    DocumentIngestionService,
    DocumentRetrievalService,
)
from backend.rag.domain.models import RetrievedChunk


@dataclass(slots=True)
class PromptContext:
    """Structured context passed to the prompt builder."""

    history: list[ChatMessage] = field(default_factory=list)
    memories: list[Any] = field(default_factory=list)
    documents: list[RetrievedChunk] = field(default_factory=list)
    document_citations: list[str] = field(default_factory=list)
    knowledge_context: str = ""
    multimodal_context: str = ""
    current_message: str = ""
    token_budget: int = 2048
    summarization_enabled: bool = False


class ContextBuilder:
    """Build a prompt context from conversation history and memories."""

    def __init__(
        self,
        conversation_store: ConversationStore | None = None,
        memory_manager: MemoryManager | None = None,
        document_retrieval_service: DocumentRetrievalService | None = None,
        document_ingestion_service: DocumentIngestionService | None = None,
        multimodal_pipeline: MultimodalPipeline | None = None,
    ) -> None:
        self.conversation_store = conversation_store or ConversationStore()
        self.memory_manager = memory_manager
        self.document_retrieval_service = document_retrieval_service
        self.document_ingestion_service = document_ingestion_service
        self.multimodal_pipeline = multimodal_pipeline
        self.logger = LoggerFactory.get_logger("ContextBuilder")

    def build_context(
        self,
        user_id: str,
        conversation_id: str,
        current_message: str,
        workspace_id: str | None = None,
        project_id: str | None = None,
        max_history_messages: int | None = None,
        max_memories: int = 5,
        max_documents: int = 5,
    ) -> PromptContext:
        """Assemble recent history, long-term memories, and future budget metadata."""
        conversation = self.conversation_store.get_conversation(conversation_id)
        if conversation is None:
            conversation = self.conversation_store.create_conversation(
                user_id, conversation_id
            )

        history = conversation.get_recent_messages(max_history_messages)

        memories: list[Any] = []
        documents: list[RetrievedChunk] = []
        citations: list[str] = []
        multimodal_context = ""
        knowledge_context = ""
        if self.memory_manager is not None:
            history_snippet = " ".join(message.content for message in history[-3:])
            relevance_query = f"{current_message} {history_snippet}".strip()
            memories = self.memory_manager.retrieve_relevant(
                user_id,
                relevance_query,
                workspace_id=workspace_id,
                project_id=project_id,
                top_n=max_memories,
            )

        history_snippet = " ".join(message.content for message in history[-3:])
        relevance_query = f"{current_message} {history_snippet}".strip()

        if self.document_retrieval_service is not None:
            self.logger.info(
                "build_context() document retrieval input query=%r owner_filter=%s conversation_filter=%s project_filter=%s",
                relevance_query,
                user_id,
                conversation_id,
                f"{workspace_id}:{project_id}",
            )
            documents = self.document_retrieval_service.retrieve(
                query=relevance_query,
                top_k=max_documents,
                owner_id=user_id,
                workspace_id=workspace_id,
                project_id=project_id,
            )
            citations = self.document_retrieval_service.format_citations(documents)
            self.logger.info(
                "build_context() document retrieval output chunk_count=%s similarity_scores=%s owner_filter=%s conversation_filter=%s",
                len(documents),
                [round(document.score, 6) for document in documents[:5]],
                user_id,
                conversation_id,
            )

        if (
            self.multimodal_pipeline is not None
            and self.document_ingestion_service is not None
        ):
            try:
                uploaded_documents = self.document_ingestion_service.list_documents(
                    owner_id=user_id,
                    workspace_id=workspace_id,
                    project_id=project_id,
                )
                pipeline_result = self.multimodal_pipeline.run(
                    MultimodalPipelineContext(
                        conversation=conversation,
                        documents=uploaded_documents,
                    )
                )
                knowledge_context = pipeline_result.knowledge_context
                multimodal_context = pipeline_result.generated_context
                conversation.processing_state["multimodal"] = dict(
                    pipeline_result.metadata
                )
                self.conversation_store.save_conversation(conversation)
            except Exception as exc:  # noqa: BLE001
                self.logger.debug(
                    "build_context() multimodal pipeline skipped: %s", exc
                )

        return PromptContext(
            history=history,
            memories=memories,
            documents=documents,
            document_citations=citations,
            knowledge_context=knowledge_context,
            multimodal_context=multimodal_context,
            current_message=current_message,
            token_budget=2048,
            summarization_enabled=False,
        )

    def build_history_context(
        self,
        conversation_id: str,
        max_history_messages: int | None = None,
    ) -> list[ChatMessage]:
        """Return recent conversation history for a conversation."""
        conversation = self.conversation_store.get_conversation(conversation_id)
        if conversation is None:
            return []
        return conversation.get_recent_messages(max_history_messages)

    def build_memory_context(
        self,
        user_id: str,
        current_message: str,
        max_memories: int = 5,
        workspace_id: str | None = None,
        project_id: str | None = None,
    ) -> list[Any]:
        """Return relevant long-term memories for the current request."""
        if self.memory_manager is None:
            return []
        return self.memory_manager.retrieve_relevant(
            user_id,
            current_message,
            workspace_id=workspace_id,
            project_id=project_id,
            top_n=max_memories,
        )
