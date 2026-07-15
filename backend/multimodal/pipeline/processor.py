"""Multimodal processing pipeline orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from backend.chat.domain.conversation import Conversation
from backend.knowledge.knowledge_models import KnowledgeObject
from backend.multimodal.models import AttachmentAnalysis, AttachmentMetadata
from backend.rag.domain.models import DocumentRecord


@dataclass(slots=True)
class MultimodalPipelineContext:
    """Shared state object passed through multimodal pipeline stages."""

    conversation: Conversation
    documents: list[DocumentRecord]
    knowledge_objects: list[KnowledgeObject] = field(default_factory=list)
    attachments: list[AttachmentMetadata] = field(default_factory=list)
    analyses: list[AttachmentAnalysis] = field(default_factory=list)
    knowledge_context: str = ""
    generated_context: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class PipelineStage(Protocol):
    """Protocol for multimodal pipeline stages."""

    def process(self, context: MultimodalPipelineContext) -> MultimodalPipelineContext:
        """Process and return pipeline context."""
        ...


class MultimodalPipeline:
    """Run multimodal stages in order without stage-to-stage coupling."""

    def __init__(self, stages: list[PipelineStage]) -> None:
        self._stages = stages

    def run(self, context: MultimodalPipelineContext) -> MultimodalPipelineContext:
        processed = context
        for stage in self._stages:
            processed = stage.process(processed)
        return processed
