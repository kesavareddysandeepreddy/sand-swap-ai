"""
SandSwap AI - LLM Memory Extractor
"""

from __future__ import annotations

from backend.llm.client import OllamaClient
from backend.llm.prompt_manager import PromptManager
from backend.memory.core.memory_manager import MemoryManager


class LLMMemoryExtractor:
    def __init__(
        self,
        model: str = "qwen2.5:14b",
        memory: MemoryManager | None = None,
    ) -> None:
        self.client = OllamaClient(model=model)
        self.memory = memory or MemoryManager()

    @staticmethod
    def _normalize(result):

        if isinstance(result, list):
            return result

        if isinstance(result, dict):
            if "memories" in result and isinstance(result["memories"], list):
                return result["memories"]

            if "memory_type" in result and "key" in result and "value" in result:
                return [result]

        return []

    def process(self, user_id: str, message: str):

        result = self.client.generate(
            prompt=PromptManager.memory_extraction(message),
            system=PromptManager.MEMORY_EXTRACTION_SYSTEM,
            format_json=True,
        )

        items = self._normalize(result)

        saved = []

        for item in items:
            if not isinstance(item, dict):
                continue

            if not all(k in item for k in ("memory_type", "key", "value")):
                continue

            saved.append(
                self.memory.remember(
                    user_id=user_id,
                    memory_type=item["memory_type"],
                    key=item["key"],
                    value=item["value"],
                    importance=float(item.get("importance", 0.5)),
                    confidence=float(item.get("confidence", 1.0)),
                    metadata=item.get("metadata", {}),
                    tags=item.get("tags", []),
                )
            )

        return saved

    def close(self):
        self.memory.close()
