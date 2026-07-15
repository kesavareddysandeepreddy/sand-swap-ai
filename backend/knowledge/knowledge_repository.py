"""Repository contracts and in-memory implementation for knowledge objects."""

from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import UTC, datetime

from backend.knowledge.knowledge_models import KnowledgeObject


class KnowledgeRepository(ABC):
    """Abstract persistence contract for knowledge objects."""

    @abstractmethod
    def create(self, knowledge_object: KnowledgeObject) -> KnowledgeObject:
        """Create and persist a new knowledge object."""
        raise NotImplementedError

    @abstractmethod
    def update(self, knowledge_object: KnowledgeObject) -> KnowledgeObject:
        """Persist a new version of an existing knowledge object."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, knowledge_id: str) -> bool:
        """Delete knowledge object and all versions."""
        raise NotImplementedError

    @abstractmethod
    def load(self, knowledge_id: str) -> KnowledgeObject | None:
        """Load latest version of one knowledge object."""
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str) -> list[KnowledgeObject]:
        """Search knowledge objects by semantic fields and tags."""
        raise NotImplementedError

    @abstractmethod
    def list_versions(self, knowledge_id: str) -> list[KnowledgeObject]:
        """List all versions for one knowledge object."""
        raise NotImplementedError


class InMemoryKnowledgeRepository(KnowledgeRepository):
    """In-memory repository implementation for sprint-safe storage."""

    def __init__(self) -> None:
        self._store: dict[str, list[KnowledgeObject]] = {}

    def create(self, knowledge_object: KnowledgeObject) -> KnowledgeObject:
        stored = deepcopy(knowledge_object)
        stored.version = 1
        stored.created_at = datetime.now(UTC)
        stored.updated_at = stored.created_at
        self._store[stored.id] = [stored]
        return deepcopy(stored)

    def update(self, knowledge_object: KnowledgeObject) -> KnowledgeObject:
        if knowledge_object.id not in self._store:
            raise KeyError(f"Knowledge object '{knowledge_object.id}' does not exist.")

        latest = self._store[knowledge_object.id][-1]
        stored = deepcopy(knowledge_object)
        stored.version = latest.version + 1
        stored.created_at = latest.created_at
        stored.updated_at = datetime.now(UTC)
        self._store[stored.id].append(stored)
        return deepcopy(stored)

    def delete(self, knowledge_id: str) -> bool:
        return self._store.pop(knowledge_id, None) is not None

    def load(self, knowledge_id: str) -> KnowledgeObject | None:
        versions = self._store.get(knowledge_id)
        if not versions:
            return None
        return deepcopy(versions[-1])

    def search(self, query: str) -> list[KnowledgeObject]:
        normalized = query.strip().lower()
        if not normalized:
            return [deepcopy(versions[-1]) for versions in self._store.values()]

        results: list[KnowledgeObject] = []
        for versions in self._store.values():
            current = versions[-1]
            haystack = " ".join(
                [
                    current.filename,
                    current.semantic_summary,
                    current.description,
                    " ".join(current.objects),
                    " ".join(current.tags),
                    current.ocr_text,
                ]
            ).lower()
            if normalized in haystack:
                results.append(deepcopy(current))
        return results

    def list_versions(self, knowledge_id: str) -> list[KnowledgeObject]:
        versions = self._store.get(knowledge_id, [])
        return [deepcopy(item) for item in versions]
