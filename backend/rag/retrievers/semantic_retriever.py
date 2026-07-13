"""Retriever implementation using embedding provider plus vector store."""

from __future__ import annotations

from typing import Any

from backend.core.logging.logger import LoggerFactory
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
        self.logger = LoggerFactory.get_logger("SemanticRetriever")

    def retrieve(
        self,
        query: str,
        top_k: int,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        if not query.strip() or top_k <= 0:
            return []

        query_vector = self.embedding_provider.embed_text(query)
        self.logger.info(
            "retrieve() input query=%r top_k=%s metadata_filter=%s query_vector_dims=%s",
            query,
            top_k,
            metadata_filter,
            len(query_vector),
        )
        results = self.vector_store.retrieve(
            query_vector=query_vector,
            top_k=top_k,
            metadata_filter=metadata_filter,
        )
        self.logger.info(
            "retrieve() output chunk_count=%s similarity_scores=%s",
            len(results),
            [round(chunk.score, 6) for chunk in results[:5]],
        )
        return results
