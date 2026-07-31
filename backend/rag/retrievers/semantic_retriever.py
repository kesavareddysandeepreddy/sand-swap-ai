"""Retriever implementation using embedding provider plus vector store."""

from __future__ import annotations

import re
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
        candidate_k = max(top_k, min(64, top_k * 12))
        results = self.vector_store.retrieve(
            query_vector=query_vector,
            top_k=candidate_k,
            metadata_filter=metadata_filter,
        )
        reranked = self._rerank_by_keyword_overlap(query=query, chunks=results)
        selected = self._select_diverse_chunks(chunks=reranked, top_k=top_k)
        self.logger.info(
            "retrieve() output chunk_count=%s candidate_count=%s similarity_scores=%s",
            len(selected),
            len(results),
            [round(chunk.score, 6) for chunk in selected[:5]],
        )
        return selected

    def _rerank_by_keyword_overlap(
        self, *, query: str, chunks: list[RetrievedChunk]
    ) -> list[RetrievedChunk]:
        query_terms = {
            term
            for term in re.findall(r"[a-zA-Z0-9_\-]+", query.lower())
            if len(term) >= 3
        }
        if not query_terms or not chunks:
            return chunks

        reranked: list[tuple[float, RetrievedChunk]] = []
        for chunk in chunks:
            text_terms = set(re.findall(r"[a-zA-Z0-9_\-]+", chunk.text.lower()))
            path = str(chunk.metadata.get("path", "")).lower()
            repository = str(chunk.metadata.get("repository", "")).lower()
            document_name = str(chunk.document_name).lower()
            metadata_terms = {
                document_name,
                path,
                repository,
            }
            corpus_terms = text_terms.union(metadata_terms)
            overlap_count = sum(1 for term in query_terms if term in corpus_terms)
            overlap_ratio = overlap_count / max(1, len(query_terms))

            architecture_bonus = 0.0
            if any(
                marker in path
                for marker in (
                    "backend/",
                    "frontend/",
                    "docs/",
                    "readme",
                    "architecture",
                    "project_context",
                )
            ):
                architecture_bonus = 0.1

            instruction_penalty = 0.0
            if "copilot-instructions" in document_name or "/.github/" in path:
                instruction_penalty = 0.2

            combined_score = (
                (chunk.score * 0.2)
                + (overlap_ratio * 0.7)
                + architecture_bonus
                - instruction_penalty
            )
            chunk.metadata["semantic_score"] = chunk.score
            chunk.metadata["keyword_score"] = overlap_ratio
            chunk.metadata["combined_score"] = combined_score
            reranked.append((combined_score, chunk))

        reranked.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in reranked]

    def _select_diverse_chunks(
        self,
        *,
        chunks: list[RetrievedChunk],
        top_k: int,
    ) -> list[RetrievedChunk]:
        if top_k <= 0:
            return []

        selected: list[RetrievedChunk] = []
        per_document_limit = 2
        document_counts: dict[str, int] = {}

        for chunk in chunks:
            doc_name = chunk.document_name
            existing = document_counts.get(doc_name, 0)
            if existing >= per_document_limit:
                continue
            selected.append(chunk)
            document_counts[doc_name] = existing + 1
            if len(selected) >= top_k:
                break

        if len(selected) < top_k:
            for chunk in chunks:
                if chunk in selected:
                    continue
                selected.append(chunk)
                if len(selected) >= top_k:
                    break
        return selected
