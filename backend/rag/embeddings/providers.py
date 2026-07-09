"""Embedding provider implementations."""

from __future__ import annotations

from typing import Any

import requests

from backend.rag.domain.interfaces import EmbeddingProvider


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by Ollama /api/embeddings."""

    def __init__(
        self,
        model: str,
        base_url: str = "http://127.0.0.1:11434",
        timeout: int = 120,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def embed_text(self, text: str) -> list[float]:
        payload = {"model": self.model, "prompt": text}
        response = requests.post(
            f"{self.base_url}/api/embeddings",
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        embedding = data.get("embedding")
        if not isinstance(embedding, list):
            raise RuntimeError("Ollama embedding response missing vector")
        return [float(value) for value in embedding]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]


class DeterministicMockEmbeddingProvider(EmbeddingProvider):
    """Stable embedding provider for deterministic tests."""

    def embed_text(self, text: str) -> list[float]:
        if not text:
            return [0.0, 0.0, 0.0]
        total = float(sum(ord(char) for char in text))
        length = float(len(text))
        vowels = float(sum(1 for char in text.lower() if char in "aeiou"))
        return [total / max(1.0, length), length, vowels]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]


class EmbeddingProviderFactory:
    """Factory for embedding providers."""

    def create(self, provider: str, config: dict[str, Any]) -> EmbeddingProvider:
        normalized = provider.lower().strip()
        if normalized == "ollama":
            return OllamaEmbeddingProvider(
                model=str(config.get("model", "nomic-embed-text")),
                base_url=str(config.get("base_url", "http://127.0.0.1:11434")),
                timeout=int(config.get("timeout", 120)),
            )
        if normalized in {"mock", "deterministic"}:
            return DeterministicMockEmbeddingProvider()

        raise ValueError(f"Unsupported embedding provider: {provider}")
