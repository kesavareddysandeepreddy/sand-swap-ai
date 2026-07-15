"""Dependency providers for the FastAPI runtime."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.agents.base import GeneralChatAgent
from backend.agents.execution import AgentExecutor
from backend.agents.planner import PlannerAgent
from backend.agents.registry import AgentRegistry
from backend.agents.runtime import AgentRuntime
from backend.agents.tool_router import ToolRouter
from backend.auth import (
    AuthService,
    CurrentUser,
    PasswordHasher,
    TokenError,
    TokenService,
)
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
from backend.knowledge.knowledge_context import KnowledgeContextBuilder
from backend.knowledge.knowledge_index import KnowledgeIndex
from backend.knowledge.knowledge_registry import KnowledgeRegistry
from backend.knowledge.knowledge_repository import InMemoryKnowledgeRepository
from backend.knowledge.knowledge_service import KnowledgeService
from backend.llm.client import OllamaClient
from backend.mcp.capabilities import CapabilityDiscovery
from backend.mcp.client import MCPClient
from backend.mcp.discovery import MCPDiscoveryService
from backend.mcp.registry import MCPRegistry
from backend.mcp.session import MCPSessionManager
from backend.memory.core.memory_manager import MemoryManager
from backend.memory.extractors.llm_memory_extractor import LLMMemoryExtractor
from backend.memory.stores.sqlite.sqlite_store import SQLiteMemoryStore
from backend.multimodal.attachment_router import AttachmentRouter
from backend.multimodal.image_cache import InMemoryImageCache
from backend.multimodal.multimodal_context import AttachmentContextBuilder
from backend.multimodal.pipeline.processor import MultimodalPipeline
from backend.multimodal.pipeline.stages.attachment_stage import AttachmentStage
from backend.multimodal.pipeline.stages.context_stage import ContextStage
from backend.multimodal.pipeline.stages.vision_stage import VisionStage
from backend.multimodal.providers.ollama_vision_provider import OllamaVisionProvider
from backend.multimodal.providers.registry import ProviderRegistry
from backend.persistence.sqlite_enterprise_repositories import (
    SQLiteAgentOwnerRepository,
    SQLiteConversationOwnerRepository,
    SQLiteDocumentOwnerRepository,
    SQLiteMemoryOwnerRepository,
    SQLiteProjectRepository,
    SQLiteUserRepository,
    SQLiteWorkspaceProjectRepository,
)
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
from backend.services.ownership_service import OwnershipService
from backend.services.user_service import UserService
from backend.workflows.engine import WorkflowEngine
from backend.workflows.executor import WorkflowExecutor
from backend.workflows.queue import InMemoryWorkflowQueue
from backend.workflows.registry import WorkflowRegistry

logger = LoggerFactory.get_logger("RuntimeDependencies")
http_bearer = HTTPBearer(auto_error=False)


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


def get_token_service() -> TokenService:
    """Resolve the shared JWT token service."""
    container = get_container()
    if container.exists("token_service"):
        return container.resolve("token_service")

    token_service = TokenService()
    container.register("token_service", token_service)
    return token_service


def _get_enterprise_db_path() -> str:
    """Return the configured SQLite path for enterprise auth data."""
    raw_path = os.getenv("ENTERPRISE_DB_PATH", "data/enterprise/enterprise.db")
    return str(Path(raw_path).resolve())


class _InMemoryUserRepository:
    """Minimal user repository used for auth API integration."""

    def __init__(self) -> None:
        self._by_id: dict[str, object] = {}
        self._by_email: dict[str, object] = {}

    def get_by_id(self, user_id: str):
        return self._by_id.get(user_id)

    def get_by_email(self, email: str):
        return self._by_email.get(email)

    def save(self, user):
        self._by_id[user.id] = user
        self._by_email[user.email] = user
        return user

    def create(self, user):
        return self.save(user)


def get_auth_service(
    token_service: Annotated[TokenService, Depends(get_token_service)],
) -> AuthService:
    """Resolve the shared authentication service."""
    container = get_container()
    if container.exists("auth_service"):
        return container.resolve("auth_service")

    enterprise_db_path = _get_enterprise_db_path()
    user_repository = SQLiteUserRepository(db_path=enterprise_db_path)
    project_repository = SQLiteProjectRepository(db_path=enterprise_db_path)
    user_service = UserService(
        user_repository=user_repository,
        project_repository=project_repository,
    )
    password_hasher = PasswordHasher()
    auth_service = AuthService(
        user_service=user_service,
        password_hasher=password_hasher,
        token_service=token_service,
    )

    container.register("enterprise_user_repository", user_repository)
    container.register("enterprise_project_repository", project_repository)
    container.register("user_service", user_service)
    container.register("password_hasher", password_hasher)
    container.register("auth_service", auth_service)
    return auth_service


def get_ownership_service() -> OwnershipService:
    """Resolve the shared ownership service for enterprise context resolution."""
    container = get_container()
    if container.exists("ownership_service"):
        return container.resolve("ownership_service")

    enterprise_db_path = _get_enterprise_db_path()
    user_repository = SQLiteUserRepository(db_path=enterprise_db_path)
    project_repository = SQLiteProjectRepository(db_path=enterprise_db_path)
    user_service = UserService(
        user_repository=user_repository,
        project_repository=project_repository,
    )
    ownership_service = OwnershipService(
        user_service=user_service,
        project_repository=project_repository,
        workspace_project_repository=SQLiteWorkspaceProjectRepository(
            db_path=enterprise_db_path
        ),
        document_owner_repository=SQLiteDocumentOwnerRepository(
            db_path=enterprise_db_path
        ),
        conversation_owner_repository=SQLiteConversationOwnerRepository(
            db_path=enterprise_db_path
        ),
        memory_owner_repository=SQLiteMemoryOwnerRepository(db_path=enterprise_db_path),
        agent_owner_repository=SQLiteAgentOwnerRepository(db_path=enterprise_db_path),
    )
    container.register("ownership_service", ownership_service)
    return ownership_service


def get_request_ownership_context(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ownership_service: Annotated[OwnershipService, Depends(get_ownership_service)],
) -> dict[str, str]:
    """Resolve request ownership context with anonymous compatibility."""
    state_context = getattr(request.state, "ownership_context", None)
    if isinstance(state_context, dict):
        user_id = state_context.get("user_id")
        workspace_id = state_context.get("workspace_id")
        project_id = state_context.get("project_id")
        if (
            isinstance(user_id, str)
            and isinstance(workspace_id, str)
            and isinstance(project_id, str)
        ):
            return {
                "user_id": user_id,
                "workspace_id": workspace_id,
                "project_id": project_id,
            }

    if current_user.is_authenticated and current_user.user_id is not None:
        requested_workspace_id = request.headers.get("X-Workspace-Id")
        if requested_workspace_id is not None:
            requested_workspace_id = requested_workspace_id.strip() or None
        requested_project_id = request.headers.get("X-Project-Id")
        if requested_project_id is not None:
            requested_project_id = requested_project_id.strip() or None
        try:
            return ownership_service.resolve_request_context(
                user_id=current_user.user_id,
                requested_workspace_id=requested_workspace_id,
                requested_project_id=requested_project_id,
            )
        except Exception:  # noqa: BLE001
            return {
                "user_id": current_user.user_id,
                "workspace_id": "default",
                "project_id": "default",
            }
    return {
        "user_id": "anonymous",
        "workspace_id": "default",
        "project_id": "default",
    }


def _resolve_bearer_token(
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    """Extract a bearer token from optional auth credentials."""
    if credentials is None:
        return None
    if credentials.scheme.lower() != "bearer":
        return None
    token = credentials.credentials.strip()
    return token or None


def get_current_user(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(http_bearer),
    ],
    token_service: Annotated[TokenService, Depends(get_token_service)],
) -> CurrentUser:
    """Resolve the current request user from a JWT bearer token.

    Invalid or missing credentials fall back to an anonymous context to preserve
    current API compatibility.
    """
    state_user = getattr(request.state, "current_user", None)
    if isinstance(state_user, CurrentUser):
        return state_user

    token = _resolve_bearer_token(credentials)
    if token is None:
        return CurrentUser.anonymous()

    try:
        claims = token_service.verify_access_token(token)
    except TokenError as exc:
        logger.info("Falling back to anonymous request context: %s", exc)
        return CurrentUser.anonymous(auth_error=str(exc))

    return CurrentUser.authenticated(claims)


def get_authenticated_user(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """Resolve only authenticated users for protected auth endpoints."""
    if current_user.is_authenticated:
        return current_user
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


def require_authenticated_user(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """Helper dependency for protected endpoints requiring login."""
    return get_authenticated_user(current_user)


def token_validation_middleware_user(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(http_bearer),
    ],
    token_service: Annotated[TokenService, Depends(get_token_service)],
) -> CurrentUser:
    """Middleware-oriented token resolver that preserves anonymous fallback."""
    return get_current_user(request, credentials, token_service)


def register_runtime_dependencies(container: Container | None = None) -> Container:
    """Register the runtime services used by the API layer."""
    shared_container = container or get_container()

    settings = Settings()
    config_manager = ConfigManager()
    token_service = TokenService()
    default_model = str(config_manager.get("llm.default_model", "llama3"))
    enterprise_db_path = _get_enterprise_db_path()

    enterprise_user_repository = SQLiteUserRepository(db_path=enterprise_db_path)
    enterprise_project_repository = SQLiteProjectRepository(db_path=enterprise_db_path)
    enterprise_document_owner_repository = SQLiteDocumentOwnerRepository(
        db_path=enterprise_db_path
    )
    enterprise_conversation_owner_repository = SQLiteConversationOwnerRepository(
        db_path=enterprise_db_path
    )
    enterprise_memory_owner_repository = SQLiteMemoryOwnerRepository(
        db_path=enterprise_db_path
    )
    enterprise_agent_owner_repository = SQLiteAgentOwnerRepository(
        db_path=enterprise_db_path
    )
    enterprise_workspace_project_repository = SQLiteWorkspaceProjectRepository(
        db_path=enterprise_db_path
    )
    user_service = UserService(
        user_repository=enterprise_user_repository,
        project_repository=enterprise_project_repository,
    )
    password_hasher = PasswordHasher()
    auth_service = AuthService(
        user_service=user_service,
        password_hasher=password_hasher,
        token_service=token_service,
    )
    ownership_service = OwnershipService(
        user_service=user_service,
        project_repository=enterprise_project_repository,
        workspace_project_repository=enterprise_workspace_project_repository,
        document_owner_repository=enterprise_document_owner_repository,
        conversation_owner_repository=enterprise_conversation_owner_repository,
        memory_owner_repository=enterprise_memory_owner_repository,
        agent_owner_repository=enterprise_agent_owner_repository,
    )

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
    knowledge_repository = InMemoryKnowledgeRepository()
    knowledge_registry = KnowledgeRegistry()
    knowledge_index = KnowledgeIndex()
    knowledge_context_builder = KnowledgeContextBuilder()
    knowledge_service = KnowledgeService(
        repository=knowledge_repository,
        registry=knowledge_registry,
        index=knowledge_index,
        context_builder=knowledge_context_builder,
    )
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
        ownership_service=ownership_service,
        knowledge_service=knowledge_service,
        default_chunk_size=int(config_manager.get("rag.chunk_size", 18)),
        default_overlap=int(config_manager.get("rag.chunk_overlap", 4)),
    )
    semantic_retriever = SemanticRetriever(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )
    document_retrieval_service = DocumentRetrievalService(retriever=semantic_retriever)
    ollama_client = OllamaClient(model=default_model)
    multimodal_supported_types = config_manager.get("multimodal.supported_types", [])
    if not isinstance(multimodal_supported_types, list):
        multimodal_supported_types = []
    attachment_router = AttachmentRouter()
    provider_registry = ProviderRegistry(
        vision_provider_name=str(config_manager.get("multimodal.vision_provider", "")),
        ocr_provider_name=str(config_manager.get("multimodal.ocr_provider", "")),
    )
    image_cache = InMemoryImageCache(
        enabled=bool(config_manager.get("multimodal.cache_enabled", True)),
        max_image_size=int(config_manager.get("multimodal.max_image_size", 10_485_760)),
    )
    ollama_vision_provider = OllamaVisionProvider(
        ollama_client=ollama_client,
        image_cache=image_cache,
        preferred_model=str(config_manager.get("multimodal.vision_provider", "")),
    )
    provider_registry.register_provider("ollama_vision", ollama_vision_provider)
    if ollama_vision_provider.is_available():
        provider_registry.set_active_provider("vision", "ollama_vision")
    elif str(config_manager.get("multimodal.vision_provider", "")).strip() in {
        "",
        "none",
        "auto",
    }:
        provider_registry.set_active_provider("vision", "")
    logger.info(
        "Multimodal vision provider status=%s model=%s",
        ollama_vision_provider.health().get("status", "unavailable"),
        ollama_vision_provider.health().get("model_name"),
    )
    attachment_context_builder = AttachmentContextBuilder(
        attachment_router=attachment_router,
        provider_registry=provider_registry,
        image_cache=image_cache,
        supported_types=[
            str(item) for item in multimodal_supported_types if isinstance(item, str)
        ],
    )
    multimodal_pipeline = MultimodalPipeline(
        stages=[
            AttachmentStage(
                attachment_router=attachment_router,
                knowledge_service=knowledge_service,
            ),
            VisionStage(
                provider_registry=provider_registry,
                knowledge_service=knowledge_service,
            ),
            ContextStage(
                knowledge_service=knowledge_service,
                knowledge_context_builder=knowledge_context_builder,
            ),
        ]
    )
    tool_router = ToolRouter()
    tool_router.register_tool("KnowledgeService", knowledge_service)
    tool_router.register_tool("VisionProvider", ollama_vision_provider)
    tool_router.register_tool("Memory", memory_manager)
    tool_router.register_tool("RAG", document_retrieval_service)

    mcp_registry = MCPRegistry()
    mcp_registry.register_default_servers()
    mcp_capability_discovery = CapabilityDiscovery()
    mcp_discovery_service = MCPDiscoveryService(
        capability_discovery=mcp_capability_discovery
    )
    mcp_session_manager = MCPSessionManager()
    mcp_client = MCPClient(
        registry=mcp_registry,
        capability_discovery=mcp_capability_discovery,
        session_manager=mcp_session_manager,
    )
    for server in mcp_registry.list_servers():
        mcp_discovery_service.discover_from_metadata(server)
    tool_router.register_tool("MCP", mcp_client)

    planner_agent = PlannerAgent()
    agent_registry = AgentRegistry()
    general_chat_agent = GeneralChatAgent(ollama_client=ollama_client)
    agent_registry.register(general_chat_agent)
    workflow_registry = WorkflowRegistry()
    workflow_queue = InMemoryWorkflowQueue()
    workflow_executor = WorkflowExecutor()
    workflow_engine = WorkflowEngine(
        registry=workflow_registry,
        executor=workflow_executor,
        queue=workflow_queue,
    )
    agent_executor = AgentExecutor(workflow_engine=workflow_engine)
    agent_runtime = AgentRuntime(
        registry=agent_registry,
        planner=planner_agent,
        tool_router=tool_router,
        executor=agent_executor,
    )

    context_builder = ContextBuilder(
        conversation_store=conversation_store,
        memory_manager=memory_manager,
        document_retrieval_service=document_retrieval_service,
        document_ingestion_service=document_ingestion_service,
        multimodal_pipeline=multimodal_pipeline,
    )
    prompt_builder = PromptBuilder()
    memory_extractor = LLMMemoryExtractor(model=default_model, memory=memory_manager)
    chat_service = ChatService(
        session_manager=session_manager,
        context_builder=context_builder,
        prompt_builder=prompt_builder,
        ollama_client=ollama_client,
        memory_manager=memory_manager,
        memory_extractor=memory_extractor,
        ownership_service=ownership_service,
        agent_runtime=agent_runtime,
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
    shared_container.register("token_service", token_service)
    shared_container.register("enterprise_user_repository", enterprise_user_repository)
    shared_container.register(
        "enterprise_project_repository", enterprise_project_repository
    )
    shared_container.register(
        "enterprise_document_owner_repository",
        enterprise_document_owner_repository,
    )
    shared_container.register(
        "enterprise_conversation_owner_repository",
        enterprise_conversation_owner_repository,
    )
    shared_container.register(
        "enterprise_memory_owner_repository",
        enterprise_memory_owner_repository,
    )
    shared_container.register(
        "enterprise_agent_owner_repository",
        enterprise_agent_owner_repository,
    )
    shared_container.register(
        "enterprise_workspace_project_repository",
        enterprise_workspace_project_repository,
    )
    shared_container.register("user_service", user_service)
    shared_container.register("password_hasher", password_hasher)
    shared_container.register("auth_service", auth_service)
    shared_container.register("ownership_service", ownership_service)
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
    shared_container.register("attachment_router", attachment_router)
    shared_container.register("multimodal_provider_registry", provider_registry)
    shared_container.register("attachment_context_builder", attachment_context_builder)
    shared_container.register("multimodal_pipeline", multimodal_pipeline)
    shared_container.register("image_cache", image_cache)
    shared_container.register("knowledge_repository", knowledge_repository)
    shared_container.register("knowledge_registry", knowledge_registry)
    shared_container.register("knowledge_index", knowledge_index)
    shared_container.register("knowledge_context_builder", knowledge_context_builder)
    shared_container.register("knowledge_service", knowledge_service)
    shared_container.register("tool_router", tool_router)
    shared_container.register("planner_agent", planner_agent)
    shared_container.register("agent_registry", agent_registry)
    shared_container.register("general_chat_agent", general_chat_agent)
    shared_container.register("workflow_registry", workflow_registry)
    shared_container.register("workflow_queue", workflow_queue)
    shared_container.register("workflow_executor", workflow_executor)
    shared_container.register("workflow_engine", workflow_engine)
    shared_container.register("mcp_registry", mcp_registry)
    shared_container.register("mcp_capability_discovery", mcp_capability_discovery)
    shared_container.register("mcp_discovery_service", mcp_discovery_service)
    shared_container.register("mcp_session_manager", mcp_session_manager)
    shared_container.register("mcp_client", mcp_client)
    shared_container.register("agent_runtime", agent_runtime)

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


CurrentUserDependency = Annotated[CurrentUser, Depends(get_current_user)]
AuthenticatedUserDependency = CurrentUserDependency
AuthServiceDependency = Annotated[AuthService, Depends(get_auth_service)]
RequiredCurrentUserDependency = Annotated[
    CurrentUser,
    Depends(get_authenticated_user),
]
ProtectedEndpointDependency = Annotated[
    CurrentUser,
    Depends(require_authenticated_user),
]
OwnershipContextDependency = Annotated[
    dict[str, str],
    Depends(get_request_ownership_context),
]


def generate_user_id() -> str:
    """Create a user identifier for auth registration."""
    return str(uuid4())


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
