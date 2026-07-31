"""
SandSwap AI - LLM Memory Extractor
"""

from __future__ import annotations

import json
import re
from typing import Any

from backend.core.logging.logger import LoggerFactory
from backend.llm.client import OllamaClient
from backend.llm.prompt_manager import PromptManager
from backend.memory.core.memory_manager import MemoryManager

STRUCTURED_FACT_KEYS = {
    "memory_type",
    "category",
    "key",
    "value",
    "importance",
    "confidence",
    "summary",
    "metadata",
    "tags",
}

CATEGORY_ALIASES = {
    "profile": "identity",
    "persona": "identity",
    "identity": "identity",
    "preference": "preference",
    "prefs": "preference",
    "project": "project",
    "goal": "goal",
    "work": "work",
    "location": "location",
    "relationship": "relationship",
    "skill": "skill",
    "fact": "fact",
    "other": "other",
}

LOWER_PRIORITY_TERMS = {"today", "now", "currently", "maybe", "probably"}
TRANSIENT_PREFIXES = {
    "what",
    "why",
    "how",
    "when",
    "where",
    "can you",
    "please",
    "tell me",
    "show me",
}


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "fact"


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _first_present(item: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in item and item[name] is not None:
            return item[name]
    return None


class LLMMemoryExtractor:
    def __init__(
        self,
        model: str = "qwen2.5:14b",
        memory: MemoryManager | None = None,
    ) -> None:
        self.client = OllamaClient(model=model)
        self.memory = memory or MemoryManager()
        self.logger = LoggerFactory.get_logger("LLMMemoryExtractor")

    @staticmethod
    def _normalize(result: Any) -> list[dict[str, Any]]:
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                return []

        if isinstance(result, list):
            return result

        if isinstance(result, dict):
            for key in ("memories", "facts", "items", "records"):
                if key in result and isinstance(result[key], list):
                    return result[key]

            # Accept any single memory object that contains a key and value.
            # memory_type is optional because _normalize_item() defaults it to "fact".
            if any(
                alias in result for alias in ("key", "memory_key", "fact_key")
            ) and any(
                alias in result for alias in ("value", "memory_value", "fact_value")
            ):
                return [result]

        return []

    @classmethod
    def _normalize_item(cls, item: dict[str, Any]) -> dict[str, Any] | None:
        memory_type = _first_present(item, "memory_type", "type") or "fact"
        category = _first_present(item, "category") or "other"
        category = CATEGORY_ALIASES.get(str(category).lower(), "other")

        key = _first_present(item, "key", "memory_key", "fact_key")
        value = _first_present(item, "value", "memory_value", "fact_value")

        if key is None and value is None:
            return None

        if key is None:
            key = cls._infer_key(category, str(value))

        if value is None:
            return None

        return {
            "memory_type": str(memory_type),
            "category": category,
            "key": str(key),
            "value": str(value),
            "importance": _coerce_float(item.get("importance"), 0.5),
            "confidence": _coerce_float(item.get("confidence"), 1.0),
            "summary": item.get("summary", ""),
            "metadata": item.get("metadata", {}),
            "tags": item.get("tags", []),
        }

    @staticmethod
    def _infer_key(category: str, value: str) -> str:
        normalized_value = _slugify(value)
        if category == "identity":
            return "name" if " " not in normalized_value else "identity"
        if category == "preference":
            return f"preferred_{normalized_value}"
        if category == "project":
            return "project_name"
        if category == "goal":
            return "learning_goal"
        if category == "work":
            return "work_context"
        if category == "location":
            return "location"
        if category == "relationship":
            return "relationship"
        if category == "skill":
            return "skill"
        return "fact"

    @staticmethod
    def _fallback_extract(message: str) -> list[dict[str, Any]]:
        text = message.strip()
        if not text:
            return []

        patterns: list[tuple[str, str, str, str]] = [
            (r"^my name is (?P<value>.+?)[\.!?]?$", "identity", "name", "name"),
            (r"^i live in (?P<value>.+?)[\.!?]?$", "location", "location", "location"),
            (
                r"^i am building (?P<value>.+?)[\.!?]?$",
                "project",
                "project_name",
                "project",
            ),
            (
                r"^i work on (?P<value>.+?)[\.!?]?$",
                "project",
                "project_name",
                "project",
            ),
            (
                r"^i am working on (?P<value>.+?)[\.!?]?$",
                "project",
                "project_name",
                "project",
            ),
            (r"^i work at (?P<value>.+?)[\.!?]?$", "work", "employer", "work"),
            (
                r"^i want to learn (?P<value>.+?)[\.!?]?$",
                "goal",
                "learning_goal",
                "goal",
            ),
            (r"^i am a[n]? (?P<value>.+?)[\.!?]?$", "identity", "role", "fact"),
            (r"^i am (?P<value>.+?)[\.!?]?$", "identity", "role", "fact"),
            (
                r"^my favorite (?P<subject>.+?) is (?P<value>.+?)[\.!?]?$",
                "preference",
                "favorite_{subject}",
                "preference",
            ),
            (
                r"^my preferred (?P<subject>.+?) is (?P<value>.+?)[\.!?]?$",
                "preference",
                "preferred_{subject}",
                "preference",
            ),
            (
                r"^i prefer (?P<value>.+?)[\.!?]?$",
                "preference",
                "preference",
                "preference",
            ),
            (
                r"^i work as (?P<value>.+?)[\.!?]?$",
                "work",
                "job_title",
                "work",
            ),
            (
                r"^my project is (?P<value>.+?)[\.!?]?$",
                "project",
                "project_name",
                "project",
            ),
            (
                r"^my favourite (?P<subject>.+?) is (?P<value>.+?)[\.!?]?$",
                "preference",
                "favorite_{subject}",
                "preference",
            ),
            (
                r"^i always use (?P<value>.+?)[\.!?]?$",
                "preference",
                "always_use",
                "preference",
            ),
        ]

        extracted: list[dict[str, Any]] = []
        for segment in re.split(r"(?<=[.!?])\s+", text):
            lowered = segment.lower().strip()
            if not lowered:
                continue
            if any(lowered.startswith(prefix) for prefix in TRANSIENT_PREFIXES):
                continue

            for pattern, category, key_template, memory_type in patterns:
                match = re.match(pattern, lowered, flags=re.IGNORECASE)
                if not match:
                    continue

                groups = match.groupdict()
                value = groups.get("value", "").strip()
                if not value:
                    continue

                subject = groups.get("subject", "").strip()
                key = key_template.format(subject=_slugify(subject))
                if category == "preference" and key == "preference":
                    key = f"preferred_{_slugify(value)}"

                if (
                    any(term in lowered for term in LOWER_PRIORITY_TERMS)
                    and len(value) < 2
                ):
                    continue

                extracted.append(
                    {
                        "memory_type": memory_type,
                        "category": category,
                        "key": key,
                        "value": value.strip().rstrip(".?!"),
                        "importance": 0.75 if category != "preference" else 0.8,
                        "confidence": 0.85,
                    }
                )
                break

        return extracted

    def process(
        self,
        user_id: str,
        message: str,
        *,
        workspace_id: str | None = None,
        project_id: str | None = None,
    ) -> list[object]:
        self.logger.info("process() called for user_id=%s", user_id)
        result: Any = []
        try:
            result = self.client.generate(
                prompt=PromptManager.memory_extraction(message),
                system=PromptManager.MEMORY_EXTRACTION_SYSTEM,
                format_json=True,
            )
            self.logger.info("Raw LLM response: %s", result)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(
                "LLM extraction unavailable, using fallback patterns: %s",
                exc,
            )

        items = self._normalize(result)
        self.logger.info("Parsed memories payload: %s", items)

        saved = []

        for item in items:
            if not isinstance(item, dict):
                continue

            normalized = self._normalize_item(item)
            if normalized is None:
                continue

            stored = self.memory.remember(
                user_id=user_id,
                memory_type=normalized["memory_type"],
                key=normalized["key"],
                value=normalized["value"],
                project_id=project_id,
                category=normalized["category"],
                importance=normalized["importance"],
                confidence=normalized["confidence"],
                metadata={
                    **normalized["metadata"],
                    "workspace_id": workspace_id,
                },
                tags=normalized["tags"],
            )
            if stored is not None:
                saved.append(stored)

        if not saved:
            for item in self._fallback_extract(message):
                stored = self.memory.remember(
                    user_id=user_id,
                    memory_type=item["memory_type"],
                    key=item["key"],
                    value=item["value"],
                    project_id=project_id,
                    category=item["category"],
                    importance=item["importance"],
                    confidence=item["confidence"],
                    metadata={"workspace_id": workspace_id},
                )
                if stored is not None:
                    saved.append(stored)

            self.logger.info("Number of memories extracted: %d", len(saved))

        return saved

    def close(self):
        self.memory.close()
