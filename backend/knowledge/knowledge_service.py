"""Service layer for Knowledge Object lifecycle and semantic updates."""

from __future__ import annotations

import mimetypes
from datetime import UTC, datetime
from typing import Any

from backend.knowledge.knowledge_context import KnowledgeContextBuilder
from backend.knowledge.knowledge_index import KnowledgeIndex
from backend.knowledge.knowledge_models import KnowledgeContext, KnowledgeObject
from backend.knowledge.knowledge_registry import KnowledgeRegistry
from backend.knowledge.knowledge_repository import KnowledgeRepository
from backend.multimodal.models import AttachmentAnalysis
from backend.rag.domain.models import DocumentRecord


class KnowledgeService:
    """Coordinate creation, enrichment, and retrieval of knowledge objects."""

    def __init__(
        self,
        *,
        repository: KnowledgeRepository,
        registry: KnowledgeRegistry,
        index: KnowledgeIndex,
        context_builder: KnowledgeContextBuilder,
    ) -> None:
        self.repository = repository
        self.registry = registry
        self.index = index
        self.context_builder = context_builder

    def ensure_from_document(
        self,
        *,
        document: DocumentRecord,
        workspace_id: str,
        project_id: str,
        conversation_id: str | None,
    ) -> KnowledgeObject:
        """Return existing knowledge object for document or create a new one."""
        existing_ids = self.registry.by_document(document.id)
        if existing_ids:
            loaded = self.repository.load(existing_ids[0])
            if loaded is not None:
                if conversation_id and loaded.conversation_id != conversation_id:
                    loaded.conversation_id = conversation_id
                    loaded.processing_history.append(
                        {
                            "stage": "conversation_mapping",
                            "timestamp": datetime.now(UTC).isoformat(),
                        }
                    )
                    loaded = self.repository.update(loaded)
                    self.registry.register(loaded)
                return loaded

        mime_type = mimetypes.guess_type(document.name)[0] or "application/octet-stream"
        knowledge_object = KnowledgeObject(
            workspace_id=workspace_id,
            project_id=project_id,
            conversation_id=conversation_id,
            document_id=document.id,
            filename=document.name,
            mime_type=mime_type,
            file_type=document.file_type,
            storage_path=document.stored_path,
            status="created",
            semantic_summary=str(document.metadata.get("summary", "")).strip(),
            description=str(document.metadata.get("description", "")).strip(),
            metadata=dict(document.metadata),
            attachment_metadata={
                "document_id": document.id,
                "sha256": document.sha256,
                "path": document.stored_path,
            },
            tags=[
                str(tag)
                for tag in document.metadata.get("tags", [])
                if isinstance(tag, str)
            ],
            processing_history=[
                {
                    "stage": "upload",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "status": "completed",
                }
            ],
        )
        stored = self.repository.create(knowledge_object)
        self.registry.register(stored)
        self.index.index(stored)
        return stored

    def apply_vision_analysis(
        self,
        *,
        knowledge_id: str,
        analysis: AttachmentAnalysis,
    ) -> KnowledgeObject:
        """Persist vision enrichment into an existing knowledge object."""
        knowledge_object = self.repository.load(knowledge_id)
        if knowledge_object is None:
            raise KeyError(f"Knowledge object '{knowledge_id}' not found.")

        knowledge_object.semantic_summary = analysis.summary
        knowledge_object.description = analysis.description
        knowledge_object.objects = list(analysis.objects)
        knowledge_object.ocr_text = analysis.ocr_text
        knowledge_object.provider = analysis.provider
        knowledge_object.confidence = analysis.confidence
        knowledge_object.processing_time = analysis.processing_time
        knowledge_object.vision_analysis = {
            "summary": analysis.summary,
            "description": analysis.description,
            "objects": list(analysis.objects),
            "ocr_text": analysis.ocr_text,
            "confidence": analysis.confidence,
            "provider": analysis.provider,
            "processing_time": analysis.processing_time,
            "metadata": dict(analysis.metadata),
        }
        knowledge_object.status = "analyzed"
        knowledge_object.processing_history.append(
            {
                "stage": "vision",
                "timestamp": datetime.now(UTC).isoformat(),
                "status": "completed",
            }
        )
        stored = self.repository.update(knowledge_object)
        self.registry.register(stored)
        self.index.index(stored)
        return stored

    def apply_cache_payload(
        self,
        *,
        knowledge_id: str,
        payload: dict[str, Any],
    ) -> KnowledgeObject:
        """Persist cache payload into an existing knowledge object."""
        knowledge_object = self.repository.load(knowledge_id)
        if knowledge_object is None:
            raise KeyError(f"Knowledge object '{knowledge_id}' not found.")

        knowledge_object.vision_analysis = dict(payload)
        knowledge_object.semantic_summary = str(payload.get("summary", "")).strip()
        knowledge_object.description = str(payload.get("description", "")).strip()
        knowledge_object.objects = [
            str(item) for item in payload.get("objects", []) if isinstance(item, str)
        ]
        knowledge_object.ocr_text = str(payload.get("ocr_text", ""))
        knowledge_object.provider = str(payload.get("provider", ""))
        knowledge_object.confidence = float(payload.get("confidence", 0.0))
        knowledge_object.processing_time = float(payload.get("processing_time", 0.0))
        knowledge_object.status = "cached"
        knowledge_object.processing_history.append(
            {
                "stage": "cache_reuse",
                "timestamp": datetime.now(UTC).isoformat(),
                "status": "completed",
            }
        )
        stored = self.repository.update(knowledge_object)
        self.registry.register(stored)
        self.index.index(stored)
        return stored

    def load_many(self, knowledge_ids: list[str]) -> list[KnowledgeObject]:
        """Load multiple knowledge objects preserving input order."""
        loaded: list[KnowledgeObject] = []
        for knowledge_id in knowledge_ids:
            item = self.repository.load(knowledge_id)
            if item is not None:
                loaded.append(item)
        return loaded

    def build_context(self, knowledge_ids: list[str]) -> KnowledgeContext:
        """Build reusable prompt context for selected knowledge objects."""
        return self.context_builder.build(self.load_many(knowledge_ids))

    def search(self, query: str) -> list[KnowledgeObject]:
        """Search knowledge objects by indexed semantic terms."""
        indexed_ids = self.index.search_ids(query)
        if indexed_ids:
            return self.load_many(indexed_ids)
        return self.repository.search(query)
