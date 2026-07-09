"""Retriever implementation using embedding provider plus vector store."""

from __future__ import annotations

from typing import Any

from backend.rag.domain.interfaces import EmbeddingProvider, Retriever, VectorStore
from backend.rag.domain.models import RetrievedChunk


class SemanticRetriever(Retriever):
    """Semantic similarity retriever with metadata filtering."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
    ) -> None:
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store

    def retrieve(
        self,
        query: str,
        top_k: int,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        if not query.strip() or top_k <= 0:
            return []

        query_vector = self.embedding_provider.embed_text(query)
        return self.vector_store.retrieve(
            query_vector=query_vector,
            top_k=top_k,
            metadata_filter=metadata_filter,
        )
