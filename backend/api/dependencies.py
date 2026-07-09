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

logger = LoggerFactory.get_logger("RuntimeDependencies")


def _get_memory_db_path() -> str:
    """Return the configured on-disk memory database path."""
    raw_path = os.getenv("MEMORY_DB_PATH", "data/memory/memory.db")
    return str(Path(raw_path).resolve())


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
    logger.info("Runtime memory SQLite path: %s", memory_db_path)
    memory_store = SQLiteMemoryStore(db_path=memory_db_path)
    memory_manager = MemoryManager(store=memory_store)
    conversation_store = ConversationStore(db_path=":memory:")
    session_manager = SessionManager(conversation_store=conversation_store)
    context_builder = ContextBuilder(
        conversation_store=conversation_store,
        memory_manager=memory_manager,
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
