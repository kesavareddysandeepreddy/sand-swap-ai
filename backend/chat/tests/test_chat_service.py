from __future__ import annotations

import asyncio
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator
from unittest.mock import patch

import pytest

from backend.chat.application.chat_service import ChatService
from backend.chat.application.context_builder import ContextBuilder
from backend.chat.application.prompt_builder import PromptBuilder
from backend.chat.application.session_manager import SessionManager
from backend.chat.infrastructure.conversation_store import ConversationStore
from backend.llm.client import OllamaClient
from backend.memory.core.memory_manager import MemoryManager
from backend.memory.stores.sqlite.sqlite_store import SQLiteMemoryStore
from backend.rag.application.document_service import DocumentRetrievalService
from backend.rag.domain.models import RetrievedChunk


@pytest.fixture
def temp_workspace() -> Iterator[str]:
    with TemporaryDirectory() as tmp_dir:
        yield tmp_dir


def test_session_manager_isolates_users_and_conversations(temp_workspace: str) -> None:
    store = ConversationStore(db_path=str(Path(temp_workspace) / "conversations.db"))
    session_manager = SessionManager(conversation_store=store)

    alice_one = session_manager.get_or_create_session("alice", "conv-1")
    alice_two = session_manager.get_or_create_session("alice", "conv-2")
    bob_one = session_manager.get_or_create_session("bob", "conv-1")

    assert alice_one.user_id == "alice"
    assert alice_two.user_id == "alice"
    assert bob_one.user_id == "bob"
    assert alice_one.id != alice_two.id
    assert bob_one.id != alice_one.id

    store.close()


def test_context_builder_uses_history_and_memories(temp_workspace: str) -> None:
    conversation_store = ConversationStore(
        db_path=str(Path(temp_workspace) / "conversations.db")
    )
    memory_store = SQLiteMemoryStore(db_path=str(Path(temp_workspace) / "memories.db"))
    memory_manager = MemoryManager(store=memory_store)
    session_manager = SessionManager(conversation_store=conversation_store)

    conversation = session_manager.get_or_create_session("user-1", "conv-1")
    conversation.add_message("user", "My favorite color is blue")
    conversation_store.save_conversation(conversation)

    memory_manager.remember("user-1", "preference", "favorite_color", "blue")

    context_builder = ContextBuilder(
        conversation_store=conversation_store,
        memory_manager=memory_manager,
    )
    context = context_builder.build_context(
        user_id="user-1",
        conversation_id=conversation.id,
        current_message="What color do I like?",
    )

    assert context.current_message == "What color do I like?"
    assert any(
        message.content == "My favorite color is blue" for message in context.history
    )
    assert any(memory.key == "favorite_color" for memory in context.memories)

    memory_store.close()
    conversation_store.close()


def test_context_builder_filters_documents_by_owner(temp_workspace: str) -> None:
    conversation_store = ConversationStore(
        db_path=str(Path(temp_workspace) / "conversations.db")
    )
    session_manager = SessionManager(conversation_store=conversation_store)

    class FakeDocumentRetrievalService(DocumentRetrievalService):
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def retrieve(
            self,
            query: str,
            *,
            top_k: int = 5,
            owner_id: str | None = None,
            workspace_id: str | None = None,
            project_id: str | None = None,
            document_id: str | None = None,
            file_type: str | None = None,
            category: str | None = None,
            metadata_filter: dict[str, object] | None = None,
        ) -> list[RetrievedChunk]:
            self.calls.append(
                {
                    "query": query,
                    "top_k": top_k,
                    "owner_id": owner_id,
                    "workspace_id": workspace_id,
                    "project_id": project_id,
                    "document_id": document_id,
                    "file_type": file_type,
                    "category": category,
                    "metadata_filter": metadata_filter,
                }
            )
            return []

        def format_citations(self, chunks: list[RetrievedChunk]) -> list[str]:
            return []

    retrieval_service = FakeDocumentRetrievalService()
    conversation = session_manager.get_or_create_session("owner-1", "conv-1")
    conversation.add_message("user", "show me the runbook")
    conversation_store.save_conversation(conversation)

    context_builder = ContextBuilder(
        conversation_store=conversation_store,
        document_retrieval_service=retrieval_service,
    )

    context_builder.build_context(
        user_id="owner-1",
        conversation_id=conversation.id,
        current_message="deployment guide",
    )

    assert retrieval_service.calls == [
        {
            "query": "deployment guide show me the runbook",
            "top_k": 5,
            "owner_id": "owner-1",
            "workspace_id": None,
            "project_id": None,
            "document_id": None,
            "file_type": None,
            "category": None,
            "metadata_filter": None,
        }
    ]

    conversation_store.close()


def test_prompt_builder_assembles_prompt() -> None:
    prompt_builder = PromptBuilder()

    class Message:
        def __init__(self, role: str, content: str) -> None:
            self.role = role
            self.content = content

    class Memory:
        def __init__(self, key: str, value: str) -> None:
            self.key = key
            self.value = value

    class PromptContext:
        def __init__(self) -> None:
            self.history = [Message("user", "Hi")]
            self.memories = [Memory("name", "Ada")]
            self.current_message = "Hello"

    prompt = prompt_builder.build_prompt(PromptContext())

    assert "Hello" in prompt
    assert "Ada" in prompt


@pytest.mark.asyncio
async def test_chat_service_returns_response_and_extracts_memories_afterward(
    temp_workspace: str,
) -> None:
    conversation_store = ConversationStore(
        db_path=str(Path(temp_workspace) / "conversations.db")
    )
    session_manager = SessionManager(conversation_store=conversation_store)
    context_builder = ContextBuilder(conversation_store=conversation_store)
    prompt_builder = PromptBuilder()

    memory_store = SQLiteMemoryStore(db_path=str(Path(temp_workspace) / "memories.db"))
    memory_manager = MemoryManager(store=memory_store)

    ollama_client = OllamaClient(model="test-model")

    class FakeExtractor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def process(
            self,
            user_id: str,
            message: str,
            *,
            workspace_id: str | None = None,
            project_id: str | None = None,
        ) -> list[object]:
            self.calls.append((user_id, message))
            return []

    extractor = FakeExtractor()

    with patch.object(
        ollama_client, "generate", return_value="Hello there"
    ) as mocked_generate:
        chat_service = ChatService(
            session_manager=session_manager,
            context_builder=context_builder,
            prompt_builder=prompt_builder,
            ollama_client=ollama_client,
            memory_manager=memory_manager,
            memory_extractor=extractor,
        )

        result = await chat_service.send_message(
            "user-1", "Hello", conversation_id="conv-1"
        )
        await asyncio.sleep(0.05)

    assert result["response"] == "Hello there"
    assert mocked_generate.called
    assert extractor.calls == [("user-1", "Hello")]

    memory_store.close()
    conversation_store.close()


@pytest.mark.asyncio
async def test_chat_service_injects_history_and_memory_into_prompt(
    temp_workspace: str,
) -> None:
    conversation_store = ConversationStore(
        db_path=str(Path(temp_workspace) / "conversations.db")
    )
    memory_store = SQLiteMemoryStore(db_path=str(Path(temp_workspace) / "memories.db"))
    memory_manager = MemoryManager(store=memory_store)
    session_manager = SessionManager(conversation_store=conversation_store)
    context_builder = ContextBuilder(
        conversation_store=conversation_store,
        memory_manager=memory_manager,
    )
    prompt_builder = PromptBuilder()
    ollama_client = OllamaClient(model="test-model")

    memory_manager.remember("user-1", "profile", "name", "Sandeep")

    prompts: list[str] = []

    def fake_generate(*, prompt: str, **_: object) -> str:
        prompts.append(prompt)
        return "Your name is Sandeep."

    class NoopExtractor:
        def process(
            self,
            user_id: str,
            message: str,
            *,
            workspace_id: str | None = None,
            project_id: str | None = None,
        ) -> list[object]:
            return []

    try:
        with patch.object(ollama_client, "generate", side_effect=fake_generate):
            chat_service = ChatService(
                session_manager=session_manager,
                context_builder=context_builder,
                prompt_builder=prompt_builder,
                ollama_client=ollama_client,
                memory_manager=memory_manager,
                memory_extractor=NoopExtractor(),
            )

            first = await chat_service.send_message("user-1", "My name is Sandeep.")
            persisted_after_first = conversation_store.get_conversation(
                first["conversation_id"]
            )
            assert persisted_after_first is not None
            assert len(persisted_after_first.messages) == 2

            second = await chat_service.send_message(
                "user-1",
                "What is my name?",
                conversation_id=first["conversation_id"],
            )

        assert first["conversation_id"].startswith("user-1:")
        assert second["conversation_id"] == first["conversation_id"]
        assert second["response"] == "Your name is Sandeep."
        assert len(prompts) == 2
        assert "Conversation history:" in prompts[1]
        assert "user: My name is Sandeep." in prompts[1]
        assert "Known user facts:" in prompts[1]
        assert "name: Sandeep" in prompts[1]
        assert prompts[1].index("Known user facts:") < prompts[1].index(
            "Conversation history:"
        )
    finally:
        memory_store.close()
        conversation_store.close()


@pytest.mark.asyncio
async def test_chat_service_appends_deduped_references_without_internal_metadata(
    temp_workspace: str,
) -> None:
    conversation_store = ConversationStore(
        db_path=str(Path(temp_workspace) / "conversations.db")
    )
    session_manager = SessionManager(conversation_store=conversation_store)
    prompt_builder = PromptBuilder()
    ollama_client = OllamaClient(model="test-model")

    class FakeContextBuilder:
        def __init__(self, store: ConversationStore) -> None:
            self.conversation_store = store

        def build_context(self, **_: object) -> object:
            chunks = [
                RetrievedChunk(
                    chunk_id="chunk-1",
                    document_id="doc-1",
                    document_name="README.md",
                    text="Architecture details",
                    score=0.9,
                    metadata={"section": "Architecture", "page": "-"},
                ),
                RetrievedChunk(
                    chunk_id="chunk-2",
                    document_id="doc-1",
                    document_name="README.md",
                    text="More architecture details",
                    score=0.88,
                    metadata={"section": "Architecture", "page": "-"},
                ),
                RetrievedChunk(
                    chunk_id="chunk-3",
                    document_id="doc-2",
                    document_name="SYSTEM_ARCHITECTURE.md",
                    text="System overview",
                    score=0.85,
                    metadata={"section": "", "page": "-"},
                ),
            ]

            class _Context:
                def __init__(self, documents: list[RetrievedChunk]) -> None:
                    self.history: list[object] = []
                    self.memories: list[object] = []
                    self.current_message = "What is the architecture?"
                    self.documents = documents
                    self.document_citations: list[str] = []

            return _Context(chunks)

    class NoopExtractor:
        def process(
            self,
            user_id: str,
            message: str,
            *,
            workspace_id: str | None = None,
            project_id: str | None = None,
        ) -> list[object]:
            return []

    llm_output = (
        "According to the provided documents, the system is layered. "
        "[README.md][page=-][section=Architecture][chunk=chunk-1]"
    )

    with patch.object(ollama_client, "generate", return_value=llm_output):
        chat_service = ChatService(
            session_manager=session_manager,
            context_builder=FakeContextBuilder(conversation_store),
            prompt_builder=prompt_builder,
            ollama_client=ollama_client,
            memory_extractor=NoopExtractor(),
        )

        result = await chat_service.send_message("user-1", "What is the architecture?")

    response = result["response"]
    assert "chunk=" not in response
    assert "[page=" not in response
    assert "[section=" not in response
    assert "According to the provided documents" not in response
    assert "References" in response
    assert "• README.md (Architecture)" in response
    assert "• SYSTEM_ARCHITECTURE.md" in response
    assert response.count("README.md") == 1

    conversation_store.close()


@pytest.mark.asyncio
async def test_chat_service_does_not_append_references_without_rag_documents(
    temp_workspace: str,
) -> None:
    conversation_store = ConversationStore(
        db_path=str(Path(temp_workspace) / "conversations.db")
    )
    session_manager = SessionManager(conversation_store=conversation_store)
    context_builder = ContextBuilder(conversation_store=conversation_store)
    prompt_builder = PromptBuilder()
    ollama_client = OllamaClient(model="test-model")

    class NoopExtractor:
        def process(
            self,
            user_id: str,
            message: str,
            *,
            workspace_id: str | None = None,
            project_id: str | None = None,
        ) -> list[object]:
            return []

    with patch.object(ollama_client, "generate", return_value="Natural answer only"):
        chat_service = ChatService(
            session_manager=session_manager,
            context_builder=context_builder,
            prompt_builder=prompt_builder,
            ollama_client=ollama_client,
            memory_extractor=NoopExtractor(),
        )
        result = await chat_service.send_message("user-1", "Hi")

    assert result["response"] == "Natural answer only"
    assert "References" not in result["response"]

    conversation_store.close()


@pytest.mark.asyncio
async def test_chat_service_keeps_response_fast_and_saves_profile_memory_immediately(
    temp_workspace: str,
) -> None:
    conversation_store = ConversationStore(
        db_path=str(Path(temp_workspace) / "conversations.db")
    )
    memory_store = SQLiteMemoryStore(db_path=str(Path(temp_workspace) / "memories.db"))
    memory_manager = MemoryManager(store=memory_store)
    session_manager = SessionManager(conversation_store=conversation_store)
    context_builder = ContextBuilder(
        conversation_store=conversation_store,
        memory_manager=memory_manager,
    )
    prompt_builder = PromptBuilder()
    ollama_client = OllamaClient(model="test-model")

    class SlowExtractor:
        def process(
            self,
            user_id: str,
            message: str,
            *,
            workspace_id: str | None = None,
            project_id: str | None = None,
        ) -> list[object]:
            _ = (user_id, message, workspace_id, project_id)
            time.sleep(0.35)
            return []

    with patch.object(ollama_client, "generate", return_value="Noted."):
        chat_service = ChatService(
            session_manager=session_manager,
            context_builder=context_builder,
            prompt_builder=prompt_builder,
            ollama_client=ollama_client,
            memory_manager=memory_manager,
            memory_extractor=SlowExtractor(),
        )

        started = time.monotonic()
        await chat_service.send_message("user-1", "My name is Sandeep.")
        elapsed_seconds = time.monotonic() - started

    # The response path should not block on slow full extraction.
    assert elapsed_seconds < 0.25

    # Fast profile extraction should still persist identity memory immediately.
    persisted = memory_manager.find_by_key("user-1", "name")
    assert persisted is not None
    assert persisted.value.lower() == "sandeep"

    # Let deferred extractor finish to avoid leaked background tasks in tests.
    await asyncio.sleep(0.45)

    memory_store.close()
    conversation_store.close()
