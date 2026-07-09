from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

import pytest

from backend.memory.core.memory_manager import MemoryManager
from backend.memory.stores.sqlite.sqlite_store import SQLiteMemoryStore


@pytest.fixture
def temp_workspace() -> Iterator[str]:
    with TemporaryDirectory() as tmp_dir:
        yield tmp_dir


def test_memory_manager_skips_exact_duplicates(temp_workspace: str) -> None:
    store = SQLiteMemoryStore(db_path=str(Path(temp_workspace) / "memories.db"))
    manager = MemoryManager(store=store)

    first = manager.remember("user-1", "profile", "name", "Sandeep", importance=1.0)
    second = manager.remember("user-1", "profile", "name", "Sandeep", importance=1.0)

    assert first is not None
    assert second is not None
    assert first.id == second.id
    assert len(store.get_all()) == 1

    store.close()


def test_memory_manager_updates_conflicts_for_same_key(temp_workspace: str) -> None:
    store = SQLiteMemoryStore(db_path=str(Path(temp_workspace) / "memories.db"))
    manager = MemoryManager(store=store)

    first = manager.remember("user-1", "profile", "name", "Sandeep", importance=1.0)
    updated = manager.remember("user-1", "profile", "name", "Arun", importance=1.0)

    assert first is not None
    assert updated is not None
    assert updated.id == first.id
    assert updated.value == "Arun"
    assert updated.updated_at >= first.updated_at
    assert len(store.get_all()) == 1

    store.close()


def test_memory_manager_applies_importance_threshold(
    temp_workspace: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEMORY_IMPORTANCE_THRESHOLD", "0.9")

    store = SQLiteMemoryStore(db_path=str(Path(temp_workspace) / "memories.db"))
    manager = MemoryManager(store=store)

    result = manager.remember(
        "user-1",
        "smalltalk",
        "greeting",
        "hello there",
        importance=0.1,
    )

    assert result is None
    assert store.get_all() == []

    store.close()


def test_memory_manager_ranks_relevant_memories(temp_workspace: str) -> None:
    store = SQLiteMemoryStore(db_path=str(Path(temp_workspace) / "memories.db"))
    manager = MemoryManager(store=store)

    manager.remember("user-1", "profile", "name", "Sandeep", importance=1.0)
    manager.remember("user-1", "project", "project_name", "SandSwap", importance=0.8)
    manager.remember("user-1", "preference", "favorite_snack", "samosa", importance=0.4)

    top = manager.retrieve_relevant("user-1", "What is my name?", top_n=2)

    assert len(top) == 2
    assert top[0].key == "name"

    store.close()


def test_memory_persists_across_store_restart(temp_workspace: str) -> None:
    db_path = Path(temp_workspace) / "memories.db"

    store = SQLiteMemoryStore(db_path=str(db_path))
    manager = MemoryManager(store=store)
    manager.remember("user-1", "profile", "name", "Sandeep", importance=1.0)
    store.close()

    reopened_store = SQLiteMemoryStore(db_path=str(db_path))
    reopened_manager = MemoryManager(store=reopened_store)

    matches = reopened_manager.retrieve_relevant(
        "user-1", "Do you remember my name?", top_n=1
    )

    assert len(matches) == 1
    assert matches[0].key == "name"
    assert matches[0].value == "Sandeep"

    reopened_store.close()
