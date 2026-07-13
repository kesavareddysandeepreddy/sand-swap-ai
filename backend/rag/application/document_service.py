"""Application services for document ingestion and retrieval."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
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
from backend.services import ANONYMOUS_USER_ID, normalize_user_id
from backend.services.ownership_service import OwnershipService


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
        ownership_service: OwnershipService | None = None,
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
        self.ownership_service = ownership_service
        self.default_chunk_size = default_chunk_size
        self.default_overlap = default_overlap
        self.logger = LoggerFactory.get_logger("DocumentIngestionService")

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _resolve_owner_id(owner_id: str | None) -> str:
        """Return the normalized owner for document access decisions."""
        return normalize_user_id(owner_id)

    @classmethod
    def _document_owner_id(cls, document: DocumentRecord) -> str:
        """Return the normalized owner stored on a document."""
        owner_id = document.metadata.get("owner_id")
        return cls._resolve_owner_id(owner_id if isinstance(owner_id, str) else None)

    def _resolve_default_project_for_owner(self, owner_id: str) -> str:
        """Resolve the owner default project id with a legacy-safe fallback."""
        if self.ownership_service is None:
            return "default"

        try:
            projects = self.ownership_service.list_projects_for_user(owner_id)
            if projects:
                default_project = next(
                    (
                        project
                        for project in projects
                        if project.name.strip().lower()
                        in {"default", "default workspace", "personal workspace"}
                    ),
                    None,
                )
                return (default_project or projects[0]).id
        except Exception:  # noqa: BLE001
            return "default"
        return "default"

    def _resolve_project_id(self, owner_id: str, project_id: str | None) -> str:
        """Return an explicit project id or fallback default workspace."""
        if isinstance(project_id, str) and project_id.strip():
            return project_id
        return self._resolve_default_project_for_owner(owner_id)

    def _ensure_document_ownership(
        self,
        *,
        document_id: str,
        owner_id: str,
        project_id: str,
    ) -> str:
        """Persist ownership links, falling back to owner default workspace."""
        if self.ownership_service is None:
            return project_id

        try:
            self.ownership_service.assign_project_owner(
                project_id=project_id,
                user_id=owner_id,
            )
            self.ownership_service.assign_document_owner(
                document_id=document_id,
                user_id=owner_id,
                project_id=project_id,
            )
            return project_id
        except Exception:  # noqa: BLE001
            fallback_project_id = self._resolve_default_project_for_owner(owner_id)
            if fallback_project_id == project_id:
                return project_id
            try:
                self.ownership_service.assign_project_owner(
                    project_id=fallback_project_id,
                    user_id=owner_id,
                )
                self.ownership_service.assign_document_owner(
                    document_id=document_id,
                    user_id=owner_id,
                    project_id=fallback_project_id,
                )
                return fallback_project_id
            except Exception:  # noqa: BLE001
                return project_id

    def _attach_document_ownership(self, document: DocumentRecord) -> DocumentRecord:
        """Merge ownership relation data into document metadata for internal consumers."""
        if self.ownership_service is None:
            return document

        try:
            owner = self.ownership_service.get_document_owner(document.id)
        except Exception:  # noqa: BLE001
            return document
        if owner is not None:
            document.metadata["owner_id"] = owner.user_id
            document.metadata["project"] = owner.project_id
            return document

        resolved_owner_id = self._document_owner_id(document)
        if not document.metadata.get("project"):
            document.metadata["project"] = self._resolve_default_project_for_owner(
                resolved_owner_id
            )
        return document

    async def upload_document(
        self,
        upload: UploadFile,
        *,
        owner_id: str | None = None,
        project: str | None = None,
        tags: list[str] | None = None,
        chunk_size: int | None = None,
        overlap: int | None = None,
    ) -> DocumentRecord:
        """Store uploaded document and index chunks."""
        started_at = perf_counter()
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
        resolved_owner_id = self._resolve_owner_id(owner_id)
        resolved_project_id = self._resolve_project_id(resolved_owner_id, project)
        ownership_project_id = self._resolve_default_project_for_owner(
            resolved_owner_id
        )
        document = DocumentRecord(
            id=document_id,
            name=safe_name,
            original_filename=safe_name,
            stored_path=str(stored_path),
            file_type=spec.key,
            size_bytes=len(payload),
            sha256=digest,
            metadata={
                "owner_id": resolved_owner_id,
                "project": resolved_project_id,
                "tags": tags or [],
                "language": None,
                "author": None,
                "created": now.isoformat(),
                "modified": now.isoformat(),
                "category": spec.category,
                "parser": spec.parser,
                "source_type": spec.category,
                "checksum_sha256": digest,
                "file_size_bytes": len(payload),
                "processing_status": "processing",
            },
        )
        self.repository.save(document)

        try:
            parser = self.parser_factory.resolve(safe_name)
            parsed = parser.parse(str(stored_path))

            if parsed.language:
                document.metadata["language"] = parsed.language
            document.metadata.update(parsed.metadata)
            document.metadata["owner_id"] = resolved_owner_id
            document.metadata["project"] = resolved_project_id
            document.metadata["parser"] = parsed.parser or spec.parser

            page_count = self._to_int(document.metadata.get("page_count"))
            slide_count = self._to_int(document.metadata.get("slide_count"))
            worksheet_count = len(document.metadata.get("worksheets", []))
            document.metadata["pages"] = max(page_count, slide_count, worksheet_count)
            table_count = self._to_int(document.metadata.get("table_count"))
            if table_count == 0:
                table_count = self._to_int(document.metadata.get("table_hints"))
            image_count = self._to_int(document.metadata.get("image_count"))
            if image_count == 0 and parsed.images:
                image_count = len(parsed.images)
            document.metadata["tables"] = table_count
            document.metadata["images"] = image_count
            document.metadata["section_count"] = len(parsed.sections)
            document.metadata["paragraph_count"] = len(parsed.paragraphs)

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
            document.metadata["chunks"] = len(chunks)
            document.embedding_status = "completed"
            document.index_status = "indexed"
            elapsed_ms = int((perf_counter() - started_at) * 1000)
            document.metadata["processing_time_ms"] = elapsed_ms
            document.metadata["processing_status"] = "completed"
            document.metadata["owner_id"] = resolved_owner_id
            document.metadata["project"] = resolved_project_id
            document.updated_at = datetime.now(UTC)
            self.repository.update(document)
            resolved_project_id = self._ensure_document_ownership(
                document_id=document.id,
                owner_id=resolved_owner_id,
                project_id=ownership_project_id,
            )
            document.metadata["project"] = resolved_project_id
            document.updated_at = datetime.now(UTC)
            self.repository.update(document)
            return document
        except Exception as exc:  # noqa: BLE001
            document.embedding_status = "failed"
            document.index_status = "failed"
            elapsed_ms = int((perf_counter() - started_at) * 1000)
            document.metadata["processing_time_ms"] = elapsed_ms
            document.metadata["processing_status"] = "failed"
            document.metadata["processing_error"] = str(exc)
            document.metadata["owner_id"] = resolved_owner_id
            document.metadata["project"] = resolved_project_id
            document.updated_at = datetime.now(UTC)
            self.repository.update(document)
            self.logger.exception("Failed to index document %s: %s", document.id, exc)
            raise

    def list_documents(self, owner_id: str | None = None) -> list[DocumentRecord]:
        documents = [
            self._attach_document_ownership(document)
            for document in self.repository.list_all()
        ]
        if owner_id is None:
            return documents

        resolved_owner_id = self._resolve_owner_id(owner_id)
        return [
            document
            for document in documents
            if self._document_owner_id(document) == resolved_owner_id
        ]

    def get_document(
        self,
        document_id: str,
        owner_id: str | None = None,
    ) -> DocumentRecord | None:
        document = self.repository.get(document_id)
        if document is None:
            return None
        document = self._attach_document_ownership(document)
        if owner_id is None:
            return document
        if self._document_owner_id(document) != self._resolve_owner_id(owner_id):
            return None
        return document

    def list_document_chunks(
        self,
        document_id: str,
        owner_id: str | None = None,
    ) -> list[RetrievedChunk]:
        if self.get_document(document_id, owner_id=owner_id) is None:
            return []
        return self.vector_store.list_chunks(document_id=document_id)

    def delete_document(
        self,
        document_id: str,
        owner_id: str | None = None,
    ) -> bool:
        document = self.get_document(document_id, owner_id=owner_id)
        if document is None:
            return False

        self.vector_store.delete_document(document_id)
        deleted = self.repository.delete(document_id)

        path = Path(document.stored_path)
        if path.exists():
            path.unlink()

        return deleted

    def delete_all_documents(self, owner_id: str | None = None) -> int:
        documents = self.list_documents(owner_id=owner_id)
        for document in documents:
            path = Path(document.stored_path)
            if path.exists():
                path.unlink()

        if owner_id is None:
            self.vector_store.clear()
            return self.repository.clear()

        deleted = 0
        for document in documents:
            self.vector_store.delete_document(document.id)
            if self.repository.delete(document.id):
                deleted += 1
        return deleted


class DocumentRetrievalService:
    """RAG retrieval and citation assembly for prompts and inspector."""

    def __init__(self, retriever: Retriever) -> None:
        self.retriever = retriever
        self.logger = LoggerFactory.get_logger("DocumentRetrievalService")

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        owner_id: str | None = None,
        document_id: str | None = None,
        file_type: str | None = None,
        category: str | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        filters = dict(metadata_filter or {})
        normalized_owner_id = None
        if owner_id is not None:
            normalized_owner_id = normalize_user_id(owner_id)
            filters["owner_id"] = normalized_owner_id
        if document_id:
            filters["document_id"] = document_id
        if file_type:
            filters["file_type"] = file_type
        if category:
            filters["category"] = category

        self.logger.info(
            "retrieve() input query=%r top_k=%s metadata_filters=%s owner_filter=%s project_filter=%s conversation_filter=%s document_filter=%s",
            query,
            top_k,
            filters or None,
            filters.get("owner_id"),
            filters.get("project"),
            filters.get("conversation_id"),
            filters.get("document_id"),
        )

        chunks = self.retriever.retrieve(
            query=query,
            top_k=top_k,
            metadata_filter=filters or None,
        )

        if (
            not chunks
            and normalized_owner_id is not None
            and normalized_owner_id != ANONYMOUS_USER_ID
        ):
            fallback_filters = dict(filters)
            fallback_filters["owner_id"] = ANONYMOUS_USER_ID
            self.logger.info(
                "retrieve() owner-scoped query returned zero chunks; retrying with anonymous legacy owner filter=%s",
                fallback_filters,
            )
            chunks = self.retriever.retrieve(
                query=query,
                top_k=top_k,
                metadata_filter=fallback_filters,
            )

        for chunk in chunks:
            if "semantic_score" not in chunk.metadata:
                chunk.metadata["semantic_score"] = chunk.score
            if "keyword_score" not in chunk.metadata:
                chunk.metadata["keyword_score"] = 0.0
            if "combined_score" not in chunk.metadata:
                chunk.metadata["combined_score"] = chunk.score

        self.logger.info(
            "retrieve() output chunk_count=%s similarity_scores=%s owner_filter=%s project_filter=%s conversation_filter=%s",
            len(chunks),
            [round(chunk.score, 6) for chunk in chunks[:5]],
            filters.get("owner_id"),
            filters.get("project"),
            filters.get("conversation_id"),
        )
        return chunks

    def format_citations(self, chunks: list[RetrievedChunk]) -> list[str]:
        citations: list[str] = []
        for chunk in chunks:
            page = chunk.metadata.get("page", "-")
            section = chunk.metadata.get("section", "-")
            citations.append(
                f"{chunk.document_name} | page={page} | section={section} | chunk={chunk.chunk_id}"
            )
        return citations
