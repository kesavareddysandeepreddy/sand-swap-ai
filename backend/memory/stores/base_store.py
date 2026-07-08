"""
SandSwap AI - Base Memory Store
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.memory.models.memory_record import MemoryRecord


class BaseMemoryStore(ABC):
    """Abstract interface for all memory storage providers."""

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the store."""
        raise NotImplementedError

    @abstractmethod
    def save(self, memory: MemoryRecord) -> MemoryRecord:
        """Persist a memory."""
        raise NotImplementedError

    @abstractmethod
    def update(self, memory: MemoryRecord) -> MemoryRecord:
        """Update a memory."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, memory_id: str) -> bool:
        """Delete a memory."""
        raise NotImplementedError

    @abstractmethod
    def get(self, memory_id: str) -> MemoryRecord | None:
        """Get a memory by id."""
        raise NotImplementedError

    @abstractmethod
    def get_all(self) -> list[MemoryRecord]:
        """Return all memories."""
        raise NotImplementedError

    @abstractmethod
    def find_by_key(
        self,
        user_id: str,
        key: str,
    ) -> MemoryRecord | None:
        """Find a memory by key."""
        raise NotImplementedError

    @abstractmethod
    def find_by_type(
        self,
        user_id: str,
        memory_type: str,
    ) -> list[MemoryRecord]:
        """Find memories by type."""
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        user_id: str,
        query: str,
    ) -> list[MemoryRecord]:
        """Search memories."""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Close the store."""
        raise NotImplementedError
