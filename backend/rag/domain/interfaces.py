"""RAG interface contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.rag.domain.models import (
    DocumentChunk,
    DocumentRecord,
    ParsedDocument,
    RetrievedChunk,
)


class DocumentParser(ABC):
    """Parse a document into normalized text and metadata."""

    @abstractmethod
    def parse(self, file_path: str) -> ParsedDocument:
        """Parse a file path into text and metadata."""
        raise NotImplementedError


class Chunker(ABC):
    """Split parsed documents into chunks."""

    @abstractmethod
    def chunk(
        self,
        document: DocumentRecord,
        parsed: ParsedDocument,
        chunk_size: int,
        overlap: int,
    ) -> list[DocumentChunk]:
        """Return chunked content for indexing."""
        raise NotImplementedError


class EmbeddingProvider(ABC):
    """Embed text into dense vectors."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Embed one text sequence."""
        raise NotImplementedError

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of text sequences."""
        raise NotImplementedError


class VectorStore(ABC):
    """Persist and query vectorized chunks."""

    @abstractmethod
    def upsert_chunks(
        self, chunks: list[DocumentChunk], vectors: list[list[float]]
    ) -> None:
        """Insert or update vectors for chunks."""
        raise NotImplementedError

    @abstractmethod
    def delete_document(self, document_id: str) -> int:
        """Delete all vectors for one document."""
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> int:
        """Delete all indexed vectors."""
        raise NotImplementedError

    @abstractmethod
    def list_chunks(self, document_id: str | None = None) -> list[RetrievedChunk]:
        """List indexed chunks, optionally filtered by document id."""
        raise NotImplementedError

    @abstractmethod
    def retrieve(
        self,
        query_vector: list[float],
        top_k: int,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        """Retrieve nearest chunks with optional metadata filtering."""
        raise NotImplementedError


class DocumentRepository(ABC):
    """Persist document records."""

    @abstractmethod
    def save(self, document: DocumentRecord) -> DocumentRecord:
        """Insert a document record."""
        raise NotImplementedError

    @abstractmethod
    def update(self, document: DocumentRecord) -> DocumentRecord:
        """Update an existing document record."""
        raise NotImplementedError

    @abstractmethod
    def list_all(self) -> list[DocumentRecord]:
        """List all documents."""
        raise NotImplementedError

    @abstractmethod
    def get(self, document_id: str) -> DocumentRecord | None:
        """Get one document record by id."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, document_id: str) -> bool:
        """Delete one document record."""
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> int:
        """Delete all document records."""
        raise NotImplementedError


class Retriever(ABC):
    """Domain-level retrieval use case."""

    @abstractmethod
    def retrieve(
        self,
        query: str,
        top_k: int,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        """Retrieve relevant chunks for a query."""
        raise NotImplementedError
