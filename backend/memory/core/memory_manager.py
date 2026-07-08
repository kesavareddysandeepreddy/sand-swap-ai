"""
SandSwap AI - Memory Manager
"""

from __future__ import annotations

from backend.memory.models.memory_record import MemoryRecord
from backend.memory.stores.base_store import BaseMemoryStore
from backend.memory.stores.sqlite.sqlite_store import SQLiteMemoryStore


class MemoryManager:
    """High-level memory operations."""

    def __init__(self, store: BaseMemoryStore | None = None) -> None:
        self.store = store or SQLiteMemoryStore()

    def remember(
        self,
        user_id: str,
        memory_type: str,
        key: str,
        value: str,
        **kwargs,
    ) -> MemoryRecord:
        existing = self.store.find_by_key(user_id, key)
        if existing:
            existing.update(
                value,
                importance=kwargs.get("importance"),
                confidence=kwargs.get("confidence"),
            )
            existing.summary = kwargs.get("summary", existing.summary)
            existing.metadata.update(kwargs.get("metadata", {}))
            existing.tags = kwargs.get("tags", existing.tags)
            return self.store.update(existing)

        memory = MemoryRecord(
            user_id=user_id,
            memory_type=memory_type,
            key=key,
            value=value,
            project_id=kwargs.get("project_id"),
            conversation_id=kwargs.get("conversation_id"),
            category=kwargs.get("category", ""),
            summary=kwargs.get("summary", ""),
            importance=kwargs.get("importance", 0.5),
            confidence=kwargs.get("confidence", 1.0),
            source=kwargs.get("source", "chat"),
            metadata=kwargs.get("metadata", {}),
            tags=kwargs.get("tags", []),
        )
        return self.store.save(memory)

    def recall(self, memory_id: str):
        m = self.store.get(memory_id)
        if m:
            m.touch()
            self.store.update(m)
        return m

    def recall_all(self):
        return self.store.get_all()

    def find_by_key(self, user_id: str, key: str):
        return self.store.find_by_key(user_id, key)

    def find_by_type(self, user_id: str, memory_type: str):
        return self.store.find_by_type(user_id, memory_type)

    def search(self, user_id: str, query: str):
        return self.store.search(user_id, query)

    def forget(self, memory_id: str) -> bool:
        return self.store.delete(memory_id)

    def close(self):
        self.store.close()
