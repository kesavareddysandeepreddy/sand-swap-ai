"""Dependency providers for the FastAPI runtime."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from fastapi import Depends

from backend.chat.application.chat_service import ChatService
from backend.chat.application.context_builder import ContextBuilder
from backend.chat.application.prompt_builder import PromptBuilder
from backend.chat.application.session_manager import SessionManager
from backend.chat.infrastructure.conversation_store import ConversationStore
from backend.config.config_manager import ConfigManager
from backend.config.settings import Settings
from backend.core.container.container import Container
from backend.core.logging.logger import LoggerFactory
from backend.core.registry import registry
from backend.llm.client import OllamaClient
from backend.memory.core.memory_manager import MemoryManager
from backend.memory.extractors.llm_memory_extractor import LLMMemoryExtractor
from backend.memory.stores.sqlite.sqlite_store import SQLiteMemoryStore
from backend.rag.application.document_service import (
    DocumentIngestionService,
    DocumentRetrievalService,
)
from backend.rag.chunkers.factory import ChunkerFactory
from backend.rag.embeddings.providers import EmbeddingProviderFactory
from backend.rag.infrastructure.sqlite_document_repository import (
    SQLiteDocumentRepository,
)
from backend.rag.parsers.factory import ParserFactory
from backend.rag.retrievers.semantic_retriever import SemanticRetriever
from backend.rag.vectorstores.sqlite_vector_store import SQLiteVectorStore

logger = LoggerFactory.get_logger("RuntimeDependencies")


def _get_memory_db_path() -> str:
    """Return the configured on-disk memory database path."""
    raw_path = os.getenv("MEMORY_DB_PATH", "data/memory/memory.db")
    return str(Path(raw_path).resolve())


def _get_rag_document_db_path() -> str:
    """Return the configured SQLite path for document metadata."""
    explicit = os.getenv("RAG_DOCUMENT_DB_PATH")
    if explicit:
        return str(Path(explicit).resolve())

    base_path = Path(os.getenv("RAG_DB_PATH", "data/documents/rag")).resolve()
    return str(base_path.with_name(f"{base_path.name}_documents.db"))


def _get_rag_vector_db_path() -> str:
    """Return the configured SQLite path for vector index data."""
    explicit = os.getenv("RAG_VECTOR_DB_PATH")
    if explicit:
        return str(Path(explicit).resolve())

    base_path = Path(os.getenv("RAG_DB_PATH", "data/documents/rag")).resolve()
    return str(base_path.with_name(f"{base_path.name}_vectors.db"))


def get_container() -> Container:
    """Return the shared application container."""
    return Container()


def register_runtime_dependencies(container: Container | None = None) -> Container:
    """Register the runtime services used by the API layer."""
    shared_container = container or get_container()

    settings = Settings()
    config_manager = ConfigManager()
    default_model = str(config_manager.get("llm.default_model", "llama3"))

    memory_db_path = _get_memory_db_path()
    rag_document_db_path = _get_rag_document_db_path()
    rag_vector_db_path = _get_rag_vector_db_path()
    logger.info("Runtime memory SQLite path: %s", memory_db_path)
    logger.info("Runtime RAG document SQLite path: %s", rag_document_db_path)
    logger.info("Runtime RAG vector SQLite path: %s", rag_vector_db_path)
    memory_store = SQLiteMemoryStore(db_path=memory_db_path)
    memory_manager = MemoryManager(store=memory_store)
    conversation_store = ConversationStore(db_path=":memory:")
    session_manager = SessionManager(conversation_store=conversation_store)
    document_repository = SQLiteDocumentRepository(db_path=rag_document_db_path)
    vector_store = SQLiteVectorStore(db_path=rag_vector_db_path)
    parser_factory = ParserFactory(
        ocr_provider=str(config_manager.get("rag.ocr_provider", "tesseract"))
    )
    chunker_factory = ChunkerFactory(semantic=True)
    embedding_provider = EmbeddingProviderFactory().create(
        provider=str(config_manager.get("rag.embedding_provider", "mock")),
        config={
            "model": str(config_manager.get("rag.embedding_model", "nomic-embed-text")),
            "base_url": str(
                config_manager.get("rag.ollama_base_url", "http://127.0.0.1:11434")
            ),
            "timeout": int(config_manager.get("rag.embedding_timeout", 120)),
        },
    )
    document_ingestion_service = DocumentIngestionService(
        repository=document_repository,
        parser_factory=parser_factory,
        chunker_factory=chunker_factory,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        storage_dir=str(Path("data/documents").resolve()),
        default_chunk_size=int(config_manager.get("rag.chunk_size", 18)),
        default_overlap=int(config_manager.get("rag.chunk_overlap", 4)),
    )
    semantic_retriever = SemanticRetriever(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )
    document_retrieval_service = DocumentRetrievalService(retriever=semantic_retriever)
    context_builder = ContextBuilder(
        conversation_store=conversation_store,
        memory_manager=memory_manager,
        document_retrieval_service=document_retrieval_service,
    )
    prompt_builder = PromptBuilder()
    ollama_client = OllamaClient(model=default_model)
    memory_extractor = LLMMemoryExtractor(model=default_model, memory=memory_manager)
    chat_service = ChatService(
        session_manager=session_manager,
        context_builder=context_builder,
        prompt_builder=prompt_builder,
        ollama_client=ollama_client,
        memory_manager=memory_manager,
        memory_extractor=memory_extractor,
    )
    logger.info(
        "MemoryManager identity runtime=%s chat_service=%s extractor=%s same_chat=%s same_extractor=%s",
        id(memory_manager),
        id(chat_service.memory_manager),
        id(memory_extractor.memory),
        memory_manager is chat_service.memory_manager,
        memory_manager is memory_extractor.memory,
    )

    shared_container.register("settings", settings)
    shared_container.register("config_manager", config_manager)
    shared_container.register("memory_store", memory_store)
    shared_container.register("memory_manager", memory_manager)
    shared_container.register("conversation_store", conversation_store)
    shared_container.register("session_manager", session_manager)
    shared_container.register("document_repository", document_repository)
    shared_container.register("vector_store", vector_store)
    shared_container.register("parser_factory", parser_factory)
    shared_container.register("chunker_factory", chunker_factory)
    shared_container.register("embedding_provider", embedding_provider)
    shared_container.register("document_ingestion_service", document_ingestion_service)
    shared_container.register("document_retrieval_service", document_retrieval_service)
    shared_container.register("context_builder", context_builder)
    shared_container.register("prompt_builder", prompt_builder)
    shared_container.register("ollama_client", ollama_client)
    shared_container.register("memory_extractor", memory_extractor)
    shared_container.register("chat_service", chat_service)

    registry.register("chat_service", chat_service)
    registry.register("memory_manager", memory_manager)
    registry.register("ollama_client", ollama_client)
    return shared_container


def get_settings() -> Settings:
    """Resolve the configured application settings."""
    container = get_container()
    if container.exists("settings"):
        return container.resolve("settings")
    register_runtime_dependencies(container)
    return container.resolve("settings")


def get_chat_service() -> ChatService:
    """Resolve the shared chat service."""
    container = get_container()
    if container.exists("chat_service"):
        return container.resolve("chat_service")
    register_runtime_dependencies(container)
    return container.resolve("chat_service")


ChatServiceDependency = Annotated[ChatService, Depends(get_chat_service)]


def get_memory_manager() -> MemoryManager:
    """Resolve the shared memory manager."""
    container = get_container()
    if container.exists("memory_manager"):
        return container.resolve("memory_manager")
    register_runtime_dependencies(container)
    return container.resolve("memory_manager")


MemoryManagerDependency = Annotated[MemoryManager, Depends(get_memory_manager)]


def get_document_ingestion_service() -> DocumentIngestionService:
    """Resolve the shared document ingestion service."""
    container = get_container()
    if container.exists("document_ingestion_service"):
        return container.resolve("document_ingestion_service")
    register_runtime_dependencies(container)
    return container.resolve("document_ingestion_service")


def get_document_retrieval_service() -> DocumentRetrievalService:
    """Resolve the shared document retrieval service."""
    container = get_container()
    if container.exists("document_retrieval_service"):
        return container.resolve("document_retrieval_service")
    register_runtime_dependencies(container)
    return container.resolve("document_retrieval_service")
