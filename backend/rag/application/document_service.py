"""Application services for document ingestion and retrieval."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from backend.core.logging.logger import LoggerFactory
from backend.rag.chunkers.factory import ChunkerFactory
from backend.rag.domain.interfaces import (
    DocumentRepository,
    EmbeddingProvider,
    Retriever,
    VectorStore,
)
from backend.rag.domain.models import DocumentRecord, RetrievedChunk
from backend.rag.parsers.factory import ParserFactory
from backend.rag.parsers.file_types import detect_file_spec


class DocumentIngestionService:
    """Coordinate upload, parse, chunk, embed, and index lifecycle."""

    def __init__(
        self,
        repository: DocumentRepository,
        parser_factory: ParserFactory,
        chunker_factory: ChunkerFactory,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        storage_dir: str,
        default_chunk_size: int = 18,
        default_overlap: int = 4,
    ) -> None:
        self.repository = repository
        self.parser_factory = parser_factory
        self.chunker_factory = chunker_factory
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.default_chunk_size = default_chunk_size
        self.default_overlap = default_overlap
        self.logger = LoggerFactory.get_logger("DocumentIngestionService")

    async def upload_document(
        self,
        upload: UploadFile,
        *,
        project: str | None = None,
        tags: list[str] | None = None,
        chunk_size: int | None = None,
        overlap: int | None = None,
    ) -> DocumentRecord:
        """Store uploaded document and index chunks."""
        payload = await upload.read()
        if not payload:
            raise ValueError("Uploaded file is empty")

        document_id = str(uuid.uuid4())
        original_filename = upload.filename or f"document-{document_id}.bin"
        safe_name = Path(original_filename).name
        spec = detect_file_spec(safe_name)
        stored_name = f"{document_id}_{safe_name}"
        stored_path = self.storage_dir / stored_name
        stored_path.write_bytes(payload)

        digest = hashlib.sha256(payload).hexdigest()
        now = datetime.now(UTC)
        document = DocumentRecord(
            id=document_id,
            name=safe_name,
            original_filename=safe_name,
            stored_path=str(stored_path),
            file_type=spec.key,
            size_bytes=len(payload),
            sha256=digest,
            metadata={
                "project": project,
                "tags": tags or [],
                "language": None,
                "author": None,
                "created": now.isoformat(),
                "modified": now.isoformat(),
                "category": spec.category,
            },
        )
        self.repository.save(document)

        try:
            parser = self.parser_factory.resolve(safe_name)
            parsed = parser.parse(str(stored_path))

            if parsed.language:
                document.metadata["language"] = parsed.language
            document.metadata.update(parsed.metadata)

            chunker = self.chunker_factory.resolve(safe_name)
            chunks = chunker.chunk(
                document=document,
                parsed=parsed,
                chunk_size=chunk_size or self.default_chunk_size,
                overlap=overlap or self.default_overlap,
            )
            vectors = self.embedding_provider.embed_batch(
                [chunk.text for chunk in chunks]
            )
            self.vector_store.upsert_chunks(chunks, vectors)

            document.chunk_count = len(chunks)
            document.embedding_status = "completed"
            document.index_status = "indexed"
            document.updated_at = datetime.now(UTC)
            self.repository.update(document)
            return document
        except Exception as exc:  # noqa: BLE001
            document.embedding_status = "failed"
            document.index_status = "failed"
            document.updated_at = datetime.now(UTC)
            self.repository.update(document)
            self.logger.exception("Failed to index document %s: %s", document.id, exc)
            raise

    def list_documents(self) -> list[DocumentRecord]:
        return self.repository.list_all()

    def get_document(self, document_id: str) -> DocumentRecord | None:
        return self.repository.get(document_id)

    def list_document_chunks(self, document_id: str) -> list[RetrievedChunk]:
        return self.vector_store.list_chunks(document_id=document_id)

    def delete_document(self, document_id: str) -> bool:
        document = self.repository.get(document_id)
        if document is None:
            return False

        self.vector_store.delete_document(document_id)
        deleted = self.repository.delete(document_id)

        path = Path(document.stored_path)
        if path.exists():
            path.unlink()

        return deleted

    def delete_all_documents(self) -> int:
        documents = self.repository.list_all()
        for document in documents:
            path = Path(document.stored_path)
            if path.exists():
                path.unlink()
        self.vector_store.clear()
        return self.repository.clear()


class DocumentRetrievalService:
    """RAG retrieval and citation assembly for prompts and inspector."""

    def __init__(self, retriever: Retriever) -> None:
        self.retriever = retriever

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        document_id: str | None = None,
        file_type: str | None = None,
        category: str | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        filters = dict(metadata_filter or {})
        if document_id:
            filters["document_id"] = document_id
        if file_type:
            filters["file_type"] = file_type
        if category:
            filters["category"] = category

        return self.retriever.retrieve(
            query=query,
            top_k=top_k,
            metadata_filter=filters or None,
        )

    def format_citations(self, chunks: list[RetrievedChunk]) -> list[str]:
        citations: list[str] = []
        for chunk in chunks:
            page = chunk.metadata.get("page", "-")
            section = chunk.metadata.get("section", "-")
            citations.append(
                f"{chunk.document_name} | page={page} | section={section} | chunk={chunk.chunk_id}"
            )
        return citations
