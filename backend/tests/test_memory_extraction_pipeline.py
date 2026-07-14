from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

from backend.chat.application.context_builder import ContextBuilder
from backend.chat.application.prompt_builder import PromptBuilder
from backend.chat.application.session_manager import SessionManager
from backend.chat.infrastructure.conversation_store import ConversationStore
from backend.memory.core.memory_manager import MemoryManager
from backend.memory.extractors.llm_memory_extractor import LLMMemoryExtractor
from backend.memory.stores.sqlite.sqlite_store import SQLiteMemoryStore


class FakeExtractorClient:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    def generate(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return self.payload


class EmptyExtractorClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return []


class TempWorkspaceFixture:
    pass


def _workspace() -> Iterator[str]:
    with TemporaryDirectory() as tmp_dir:
        yield tmp_dir


def test_llm_memory_extractor_persists_structured_facts_and_survives_restart() -> None:
    for temp_dir in _workspace():
        db_path = Path(temp_dir) / "memory.db"
        conversation_db_path = Path(temp_dir) / "conversations.db"

        store = SQLiteMemoryStore(db_path=str(db_path))
        manager = MemoryManager(store=store)
        extractor = LLMMemoryExtractor(memory=manager)
        extractor.client = FakeExtractorClient(
            {
                "facts": [
                    {
                        "memory_type": "fact",
                        "category": "identity",
                        "memory_key": "name",
                        "memory_value": "Sandeep",
                        "importance": 0.99,
                        "confidence": 0.99,
                    },
                    {
                        "memory_type": "fact",
                        "category": "location",
                        "memory_key": "location",
                        "memory_value": "Hyderabad",
                        "importance": 0.9,
                        "confidence": 0.95,
                    },
                    {
                        "memory_type": "fact",
                        "category": "identity",
                        "memory_key": "role",
                        "memory_value": "Cloud Architect",
                        "importance": 0.9,
                        "confidence": 0.95,
                    },
                    {
                        "memory_type": "fact",
                        "category": "preference",
                        "memory_key": "favorite_ide",
                        "memory_value": "Cursor",
                        "importance": 0.95,
                        "confidence": 0.98,
                    },
                    {
                        "memory_type": "fact",
                        "category": "preference",
                        "memory_key": "favorite_language",
                        "memory_value": "Python",
                        "importance": 0.95,
                        "confidence": 0.98,
                    },
                    {
                        "memory_type": "fact",
                        "category": "project",
                        "memory_key": "project_name",
                        "memory_value": "SandSwap AI",
                        "importance": 0.9,
                        "confidence": 0.97,
                    },
                    {
                        "memory_type": "fact",
                        "category": "goal",
                        "memory_key": "learning_goal",
                        "memory_value": "Kubernetes",
                        "importance": 0.88,
                        "confidence": 0.94,
                    },
                ]
            }
        )

        saved = extractor.process(
            "sandeep",
            "My name is Sandeep. I live in Hyderabad. I am a Cloud Architect. My favorite IDE is Cursor. My favorite language is Python. I am building SandSwap AI. I want to learn Kubernetes.",
        )

        assert len(saved) == 7
        assert {memory.key for memory in store.get_all()} == {
            "name",
            "location",
            "role",
            "favorite_ide",
            "favorite_language",
            "project_name",
            "learning_goal",
        }

        store.close()

        reopened_store = SQLiteMemoryStore(db_path=str(db_path))
        reopened_manager = MemoryManager(store=reopened_store)

        assert reopened_manager.find_by_key("sandeep", "favorite_ide") is not None
        assert reopened_manager.find_by_key("sandeep", "favorite_language") is not None
        assert reopened_manager.find_by_key("sandeep", "project_name") is not None
        assert reopened_manager.find_by_key("sandeep", "learning_goal") is not None

        top_memories = reopened_manager.retrieve_relevant(
            "sandeep",
            "What are my favorite IDE and language, and what am I building?",
            top_n=3,
        )
        assert [memory.key for memory in top_memories][0] in {
            "favorite_ide",
            "favorite_language",
            "project_name",
        }

        conversation_store = ConversationStore(db_path=str(conversation_db_path))
        session_manager = SessionManager(conversation_store=conversation_store)
        conversation = session_manager.get_or_create_session("sandeep", "conv-1")
        conversation.add_message("user", "Remember my preferences.")
        conversation_store.save_conversation(conversation)

        context_builder = ContextBuilder(
            conversation_store=conversation_store,
            memory_manager=reopened_manager,
        )
        prompt_builder = PromptBuilder()
        context = context_builder.build_context(
            user_id="sandeep",
            conversation_id=conversation.id,
            current_message="What is my favorite IDE and language?",
        )
        prompt = prompt_builder.build_prompt(context)

        assert "Relevant memories:" in prompt
        assert "favorite_ide: Cursor" in prompt
        assert "favorite_language: Python" in prompt
        assert "project_name: SandSwap AI" in prompt
        assert prompt.index("Relevant memories:") < prompt.index("Recent conversation:")

        reopened_store.close()
        conversation_store.close()


def test_llm_memory_extractor_falls_back_to_generic_fact_patterns() -> None:
    for temp_dir in _workspace():
        db_path = Path(temp_dir) / "memory.db"
        store = SQLiteMemoryStore(db_path=str(db_path))
        manager = MemoryManager(store=store)
        extractor = LLMMemoryExtractor(memory=manager)
        extractor.client = EmptyExtractorClient()

        saved = extractor.process(
            "sandeep",
            "My name is Sandeep. I live in Hyderabad. I am a Cloud Architect. My favorite IDE is Cursor. My favorite language is Python. I work on SandSwap AI. I want to learn Kubernetes.",
        )

        assert len(saved) >= 6
        assert manager.find_by_key("sandeep", "name") is not None
        assert manager.find_by_key("sandeep", "location") is not None
        assert manager.find_by_key("sandeep", "role") is not None
        assert manager.find_by_key("sandeep", "project_name") is not None
        assert manager.find_by_key("sandeep", "learning_goal") is not None

        store.close()


def test_llm_memory_extractor_persists_profile_statements() -> None:
    for temp_dir in _workspace():
        db_path = Path(temp_dir) / "memory.db"
        store = SQLiteMemoryStore(db_path=str(db_path))
        manager = MemoryManager(store=store)
        extractor = LLMMemoryExtractor(memory=manager)
        extractor.client = EmptyExtractorClient()

        saved = extractor.process(
            "sandeep",
            "My name is Sandeep. I work as Cloud Architect.",
            workspace_id="workspace-1",
            project_id="project-1",
        )

        assert len(saved) >= 2
        name = manager.find_by_key("sandeep", "name")
        role = manager.find_by_key("sandeep", "job_title")
        assert name is not None
        assert name.value == "sandeep"
        assert role is not None
        assert role.value == "cloud architect"

        scoped = manager.retrieve_relevant(
            "sandeep",
            "what is my name",
            workspace_id="workspace-1",
            project_id="project-1",
            top_n=5,
        )
        assert any(item.key == "name" for item in scoped)

        store.close()
