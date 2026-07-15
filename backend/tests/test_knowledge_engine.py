from __future__ import annotations

from backend.chat.domain.conversation import Conversation
from backend.knowledge.knowledge_context import KnowledgeContextBuilder
from backend.knowledge.knowledge_index import KnowledgeIndex
from backend.knowledge.knowledge_models import KnowledgeObject
from backend.knowledge.knowledge_registry import KnowledgeRegistry
from backend.knowledge.knowledge_repository import InMemoryKnowledgeRepository
from backend.knowledge.knowledge_service import KnowledgeService
from backend.multimodal.models import AttachmentAnalysis
from backend.rag.domain.models import DocumentRecord


def _service() -> KnowledgeService:
    return KnowledgeService(
        repository=InMemoryKnowledgeRepository(),
        registry=KnowledgeRegistry(),
        index=KnowledgeIndex(),
        context_builder=KnowledgeContextBuilder(),
    )


def _document(document_id: str = "doc-1") -> DocumentRecord:
    return DocumentRecord(
        id=document_id,
        name="plate.png",
        original_filename="plate.png",
        stored_path="/tmp/plate.png",
        file_type="png",
        size_bytes=128,
        sha256=f"sha-{document_id}",
        metadata={"workspace_id": "ws-1", "project": "pr-1", "tags": ["food"]},
    )


def test_knowledge_lifecycle_create_and_load() -> None:
    service = _service()
    created = service.ensure_from_document(
        document=_document(),
        workspace_id="ws-1",
        project_id="pr-1",
        conversation_id="conv-1",
    )

    loaded = service.load_many([created.id])
    assert len(loaded) == 1
    assert loaded[0].document_id == "doc-1"
    assert loaded[0].workspace_id == "ws-1"


def test_repository_versioning() -> None:
    repo = InMemoryKnowledgeRepository()
    initial = repo.create(KnowledgeObject(filename="f1"))
    initial.description = "first"
    updated = repo.update(initial)

    versions = repo.list_versions(initial.id)
    assert updated.version == 2
    assert len(versions) == 2


def test_registry_conversation_workspace_project_document_mappings() -> None:
    registry = KnowledgeRegistry()
    obj = KnowledgeObject(
        id="k1",
        conversation_id="conv-1",
        workspace_id="ws-1",
        project_id="pr-1",
        document_id="doc-1",
    )
    registry.register(obj)
    registry.map_to_agent("agent-1", "k1")

    assert registry.by_conversation("conv-1") == ["k1"]
    assert registry.by_workspace("ws-1") == ["k1"]
    assert registry.by_project("pr-1") == ["k1"]
    assert registry.by_document("doc-1") == ["k1"]
    assert registry.by_agent("agent-1") == ["k1"]


def test_context_builder_renders_readable_context() -> None:
    builder = KnowledgeContextBuilder()
    context = builder.build(
        [
            KnowledgeObject(
                id="k1",
                filename="plate.png",
                semantic_summary="A breakfast plate.",
                description="Two fried eggs with toast.",
                objects=["eggs", "toast", "coffee"],
                ocr_text="",
                provider="vision",
                confidence=0.95,
            )
        ]
    )

    assert context.knowledge_ids == ["k1"]
    assert "Attached Image" in context.rendered_text
    assert "Summary: A breakfast plate." in context.rendered_text


def test_service_cache_reuse_and_versioning() -> None:
    service = _service()
    created = service.ensure_from_document(
        document=_document("doc-cache"),
        workspace_id="ws-1",
        project_id="pr-1",
        conversation_id="conv-1",
    )

    cached = service.apply_cache_payload(
        knowledge_id=created.id,
        payload={
            "summary": "Cached summary",
            "description": "Cached description",
            "objects": ["obj-1"],
            "ocr_text": "",
            "confidence": 0.8,
            "provider": "cache",
            "processing_time": 0.01,
            "metadata": {"cache_hit": True},
        },
    )

    assert cached.version == 2
    assert cached.semantic_summary == "Cached summary"
    assert cached.status == "cached"


def test_service_apply_vision_analysis_updates_object() -> None:
    service = _service()
    created = service.ensure_from_document(
        document=_document("doc-vision"),
        workspace_id="ws-1",
        project_id="pr-1",
        conversation_id="conv-1",
    )
    analysis = AttachmentAnalysis(
        filename="plate.png",
        mime_type="image/png",
        extension=".png",
        size=128,
        summary="Vision summary",
        description="Vision description",
        objects=["plate", "coffee"],
        confidence=0.9,
        provider="vision-provider",
        processing_time=0.02,
    )

    updated = service.apply_vision_analysis(knowledge_id=created.id, analysis=analysis)
    assert updated.version == 2
    assert updated.semantic_summary == "Vision summary"
    assert updated.provider == "vision-provider"


def test_conversation_stores_knowledge_object_ids_only() -> None:
    conversation = Conversation(user_id="u1")
    conversation.knowledge_object_ids.append("k1")

    payload = conversation.to_dict()
    restored = Conversation.from_dict(payload)

    assert restored.knowledge_object_ids == ["k1"]
