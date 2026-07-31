"""
SandSwap AI - Memory Manager
"""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime

from backend.core.logging.logger import LoggerFactory
from backend.memory.models.memory_record import MemoryRecord
from backend.memory.stores.base_store import BaseMemoryStore
from backend.memory.stores.sqlite.sqlite_store import SQLiteMemoryStore

VALID_CATEGORIES = {
    "identity",
    "preference",
    "work",
    "project",
    "skill",
    "relationship",
    "location",
    "goal",
    "fact",
    "other",
}

HIGH_IMPORTANCE_KEYWORDS = {
    "name",
    "employer",
    "company",
    "project",
    "preference",
    "skill",
    "favorite",
}

HIGH_PRIORITY_IMPORTANCE_THRESHOLD = 0.75

LOW_IMPORTANCE_KEYWORDS = {
    "hello",
    "hi",
    "hey",
    "thanks",
    "thank",
    "ack",
    "ok",
}


_UNINFORMATIVE_VALUES: frozenset[str] = frozenset(
    {
        "",
        "unknown",
        "null",
        "n/a",
        "none",
        "nan",
        "undefined",
        "not available",
        "not specified",
        "not provided",
    }
)


class MemoryManager:
    """High-level memory operations."""

    def __init__(self, store: BaseMemoryStore | None = None) -> None:
        self.store = store or SQLiteMemoryStore()
        self.logger = LoggerFactory.get_logger("MemoryManager")
        self.importance_threshold = float(
            os.getenv("MEMORY_IMPORTANCE_THRESHOLD", "0.2")
        )

    @staticmethod
    def _normalize_text(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip().lower())

    @staticmethod
    def _tokenize(value: str) -> set[str]:
        return {
            token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 1
        }

    def _resolve_category(
        self,
        *,
        category: str | None,
        memory_type: str,
        key: str,
        value: str,
    ) -> str:
        if category:
            normalized_category = category.lower()
            if normalized_category == "profile":
                return "identity"
            if normalized_category in VALID_CATEGORIES:
                return normalized_category

        combined = " ".join([memory_type, key, value]).lower()
        if any(token in combined for token in ("name", "age", "identity")):
            return "identity"
        if any(
            token in combined
            for token in ("favorite", "prefer", "preference", "likes", "dislike")
        ):
            return "preference"
        if any(token in combined for token in ("work", "job", "employer", "office")):
            return "work"
        if "project" in combined:
            return "project"
        if any(token in combined for token in ("skill", "expert", "proficient")):
            return "skill"
        if any(token in combined for token in ("friend", "wife", "husband", "partner")):
            return "relationship"
        if any(token in combined for token in ("city", "country", "location", "live")):
            return "location"
        if any(token in combined for token in ("goal", "target", "plan")):
            return "goal"
        if memory_type.lower() in {"fact", "profile"}:
            return "fact"
        return "other"

    def _score_importance(
        self,
        *,
        key: str,
        value: str,
        category: str,
        explicit_importance: float | None,
    ) -> float:
        if explicit_importance is not None:
            return max(0.0, min(1.0, float(explicit_importance)))

        key_tokens = self._tokenize(key)
        value_tokens = self._tokenize(value)
        tokens = key_tokens | value_tokens

        if tokens & LOW_IMPORTANCE_KEYWORDS:
            return 0.05
        if category in {"identity", "preference", "work", "project", "skill"}:
            return 0.85
        if tokens & HIGH_IMPORTANCE_KEYWORDS:
            return 0.8
        if category in {"goal", "relationship", "location", "fact"}:
            return 0.6
        return 0.35

    @staticmethod
    def _score_recency(memory: MemoryRecord) -> float:
        now = datetime.now(UTC)
        reference = memory.updated_at or memory.created_at
        age_days = max(0.0, (now - reference).total_seconds() / 86400)
        return 1.0 / (1.0 + age_days / 30.0)

    def _score_relevance(
        self,
        memory: MemoryRecord,
        *,
        query_tokens: set[str],
        category_hint: set[str],
        workspace_id: str | None,
        project_id: str | None,
    ) -> float:
        key_tokens = self._tokenize(memory.key)
        value_tokens = self._tokenize(memory.value)
        combined = key_tokens | value_tokens

        overlap = len(query_tokens & combined)
        key_overlap = len(query_tokens & key_tokens)
        category_bonus = 1.0 if memory.category in category_hint else 0.0

        memory_workspace = str(memory.metadata.get("workspace_id") or "")
        workspace_bonus = 0.0
        if workspace_id is not None:
            workspace_bonus = 0.75 if memory_workspace == workspace_id else 0.0

        project_bonus = 0.0
        if project_id is not None:
            project_bonus = 0.75 if (memory.project_id == project_id) else 0.0

        return (
            overlap * 1.25
            + key_overlap * 1.75
            + category_bonus
            + workspace_bonus
            + project_bonus
            + memory.importance * 2.0
            + self._score_recency(memory)
        )

    @staticmethod
    def _score_priority(memory: MemoryRecord) -> float:
        return memory.importance * 2.0 + MemoryManager._score_recency(memory)

    def remember(
        self,
        user_id: str,
        memory_type: str,
        key: str,
        value: str,
        **kwargs,
    ) -> MemoryRecord | None:
        self.logger.info(
            "remember() called user_id=%s category=%s key=%s value=%s",
            user_id,
            kwargs.get("category"),
            key,
            value,
        )
        resolved_category = self._resolve_category(
            category=kwargs.get("category"),
            memory_type=memory_type,
            key=key,
            value=value,
        )
        resolved_importance = self._score_importance(
            key=key,
            value=value,
            category=resolved_category,
            explicit_importance=kwargs.get("importance"),
        )

        if resolved_importance < self.importance_threshold:
            self.logger.info(
                "Decision: skip-below-threshold key=%s importance=%.3f threshold=%.3f",
                key,
                resolved_importance,
                self.importance_threshold,
            )
            return None

        normalized_value = self._normalize_text(value)
        existing = self.store.find_by_key(user_id, key)
        if existing:
            if self._normalize_text(existing.value) == normalized_value:
                self.logger.info("Decision: duplicate key=%s", key)
                return existing

            # Skip update when the new value is non-informative to protect
            # existing useful memories from being overwritten with placeholders.
            if normalized_value in _UNINFORMATIVE_VALUES:
                self.logger.info(
                    "Decision: skip-uninformative-update key=%s proposed_value=%r keeping_existing=%r",
                    key,
                    value,
                    existing.value,
                )
                return existing

            self.logger.info(
                "Decision: conflict-update key=%s old=%s new=%s",
                key,
                existing.value,
                value,
            )
            existing.update(
                value,
                importance=resolved_importance,
                confidence=kwargs.get("confidence"),
            )
            existing.category = resolved_category
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
            category=resolved_category,
            summary=kwargs.get("summary", ""),
            importance=resolved_importance,
            confidence=kwargs.get("confidence", 1.0),
            source=kwargs.get("source", "chat"),
            metadata=kwargs.get("metadata", {}),
            tags=kwargs.get("tags", []),
        )
        self.logger.info("Decision: insert key=%s category=%s", key, resolved_category)
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

    def retrieve_relevant(
        self,
        user_id: str,
        query: str,
        *,
        workspace_id: str | None = None,
        project_id: str | None = None,
        top_n: int = 5,
    ) -> list[MemoryRecord]:
        query_tokens = self._tokenize(query)
        category_hint = {token for token in query_tokens if token in VALID_CATEGORIES}
        candidates = [
            memory for memory in self.store.get_all() if memory.user_id == user_id
        ]

        ranked = sorted(
            candidates,
            key=lambda memory: self._score_relevance(
                memory,
                query_tokens=query_tokens,
                category_hint=category_hint,
                workspace_id=workspace_id,
                project_id=project_id,
            ),
            reverse=True,
        )
        return ranked[:top_n]

    def retrieve_context_memories(
        self,
        user_id: str,
        query: str,
        *,
        workspace_id: str | None = None,
        project_id: str | None = None,
        top_n_relevant: int = 5,
        top_n_priority: int = 5,
    ) -> list[MemoryRecord]:
        """Return ordered persistent memories for prompt context.

        Order: high-priority persistent memories first, then semantically relevant
        memories, deduplicated by memory id.
        """
        all_user_memories = [
            memory for memory in self.store.get_all() if memory.user_id == user_id
        ]
        high_priority = sorted(
            [
                memory
                for memory in all_user_memories
                if memory.importance >= HIGH_PRIORITY_IMPORTANCE_THRESHOLD
            ],
            key=self._score_priority,
            reverse=True,
        )[:top_n_priority]

        relevant = self.retrieve_relevant(
            user_id,
            query,
            workspace_id=workspace_id,
            project_id=project_id,
            top_n=top_n_relevant,
        )

        ordered: list[MemoryRecord] = []
        seen_ids: set[str] = set()
        for memory in [*high_priority, *relevant]:
            if memory.id in seen_ids:
                continue
            seen_ids.add(memory.id)
            ordered.append(memory)

        return ordered

    def forget(self, memory_id: str) -> bool:
        return self.store.delete(memory_id)

    def close(self):
        self.store.close()

    async def shutdown(self) -> None:
        """Release memory-store resources during application shutdown."""
        self.close()
