from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.chat.application.context_builder import ContextBuilder
from backend.chat.application.prompt_builder import PromptBuilder
from backend.chat.domain.conversation import Conversation
from backend.chat.infrastructure.conversation_store import ConversationStore
from backend.knowledge.knowledge_context import KnowledgeContextBuilder
from backend.knowledge.knowledge_index import KnowledgeIndex
from backend.knowledge.knowledge_registry import KnowledgeRegistry
from backend.knowledge.knowledge_repository import InMemoryKnowledgeRepository
from backend.knowledge.knowledge_service import KnowledgeService
from backend.multimodal.attachment_router import AttachmentRouter
from backend.multimodal.models import AttachmentMetadata, VisionAnalysis
from backend.multimodal.pipeline.processor import (
    MultimodalPipeline,
    MultimodalPipelineContext,
)
from backend.multimodal.pipeline.stages.attachment_stage import AttachmentStage
from backend.multimodal.pipeline.stages.context_stage import ContextStage
from backend.multimodal.pipeline.stages.vision_stage import VisionStage
from backend.multimodal.providers.base import VisionProvider
from backend.multimodal.providers.registry import ProviderRegistry
from backend.rag.application.document_service import DocumentIngestionService
from backend.rag.domain.models import DocumentRecord


class FakeVisionProvider(VisionProvider):
    def __init__(self) -> None:
        self.calls = 0

    def is_available(self) -> bool:
        return True

    def analyze_image(
        self,
        image_path: str,
        metadata: AttachmentMetadata | None = None,
    ) -> VisionAnalysis:
        _ = (image_path, metadata)
        self.calls += 1
        return VisionAnalysis(
            summary="A breakfast plate.",
            description="Two fried eggs with toast on a ceramic plate.",
            objects=["eggs", "toast", "coffee"],
            ocr_text="",
            confidence=0.93,
            provider="fake_vision",
            processing_time=0.01,
            raw_response={},
            metadata={"visible_text": "none", "cache_hit": False},
        )

    def health(self) -> dict[str, Any]:
        return {"status": "available", "model_name": "fake-vision"}


def _image_document(path: Path) -> DocumentRecord:
    return DocumentRecord(
        id="doc-1",
        name="plate.png",
        original_filename="plate.png",
        stored_path=str(path),
        file_type="png",
        size_bytes=path.stat().st_size,
        sha256="sha-plate",
        metadata={"workspace_id": "default", "project": "default", "category": "image"},
    )


def _build_pipeline(provider_registry: ProviderRegistry) -> MultimodalPipeline:
    knowledge_service = KnowledgeService(
        repository=InMemoryKnowledgeRepository(),
        registry=KnowledgeRegistry(),
        index=KnowledgeIndex(),
        context_builder=KnowledgeContextBuilder(),
    )
    attachment_router = AttachmentRouter()
    return MultimodalPipeline(
        stages=[
            AttachmentStage(
                attachment_router=attachment_router,
                knowledge_service=knowledge_service,
            ),
            VisionStage(
                provider_registry=provider_registry,
                knowledge_service=knowledge_service,
            ),
            ContextStage(
                knowledge_service=knowledge_service,
                knowledge_context_builder=KnowledgeContextBuilder(),
            ),
        ]
    )


def test_pipeline_stage_ordering() -> None:
    called: list[str] = []

    class StageA:
        def process(
            self, context: MultimodalPipelineContext
        ) -> MultimodalPipelineContext:
            called.append("a")
            return context

    class StageB:
        def process(
            self, context: MultimodalPipelineContext
        ) -> MultimodalPipelineContext:
            called.append("b")
            return context

    pipeline = MultimodalPipeline(stages=[StageA(), StageB()])
    pipeline.run(
        MultimodalPipelineContext(
            conversation=Conversation(user_id="u1"),
            documents=[],
        )
    )
    assert called == ["a", "b"]


def test_pipeline_cache_reuse(tmp_path: Path) -> None:
    image_path = tmp_path / "plate.png"
    image_path.write_bytes(b"image-bytes")

    provider = FakeVisionProvider()
    registry = ProviderRegistry(vision_provider_name="vision")
    registry.register_provider("vision", provider)

    pipeline = _build_pipeline(registry)
    conversation = Conversation(user_id="u1")
    document = _image_document(image_path)

    first = pipeline.run(
        MultimodalPipelineContext(conversation=conversation, documents=[document])
    )
    second = pipeline.run(
        MultimodalPipelineContext(conversation=conversation, documents=[document])
    )

    assert provider.calls == 1
    assert len(first.analyses) == 1
    assert len(second.analyses) == 1
    assert second.analyses[0].metadata.get("cache_hit") is True


def test_pipeline_fallback_without_vision_provider(tmp_path: Path) -> None:
    image_path = tmp_path / "plate.png"
    image_path.write_bytes(b"image-bytes")

    registry = ProviderRegistry(vision_provider_name="missing")
    pipeline = _build_pipeline(registry)
    conversation = Conversation(user_id="u1")
    document = _image_document(image_path)

    result = pipeline.run(
        MultimodalPipelineContext(conversation=conversation, documents=[document])
    )
    assert result.generated_context == ""
    assert result.metadata["vision_status"] == "unavailable"


def test_context_builder_injects_multimodal_context(tmp_path: Path) -> None:
    image_path = tmp_path / "plate.png"
    image_path.write_bytes(b"image-bytes")

    provider = FakeVisionProvider()
    registry = ProviderRegistry(vision_provider_name="vision")
    registry.register_provider("vision", provider)
    pipeline = _build_pipeline(registry)

    class FakeIngestionService(DocumentIngestionService):
        def __init__(self, document: DocumentRecord) -> None:
            self._document = document

        def list_documents(
            self,
            owner_id: str | None = None,
            workspace_id: str | None = None,
            project_id: str | None = None,
        ) -> list[DocumentRecord]:
            _ = (owner_id, workspace_id, project_id)
            return [self._document]

    store = ConversationStore(db_path=str(tmp_path / "conversations.db"))
    conversation = store.create_conversation("u1", "u1:conv-1")
    conversation.add_message("user", "What do you see?")
    store.save_conversation(conversation)

    context_builder = ContextBuilder(
        conversation_store=store,
        document_ingestion_service=FakeIngestionService(_image_document(image_path)),
        multimodal_pipeline=pipeline,
    )

    context = context_builder.build_context(
        user_id="u1",
        conversation_id="u1:conv-1",
        current_message="what do you see",
    )
    prompt = PromptBuilder().build_prompt(context)

    assert "Multimodal context:" in prompt
    assert "Attached Image" in prompt
    assert "Summary: A breakfast plate." in prompt
    assert "Provider: fake_vision" in prompt
    persisted = store.get_conversation("u1:conv-1")
    assert persisted is not None
    assert len(persisted.knowledge_object_ids) == 1

    store.close()
