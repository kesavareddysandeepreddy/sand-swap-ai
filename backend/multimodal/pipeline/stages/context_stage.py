"""Context rendering stage for multimodal pipeline."""

from __future__ import annotations

from backend.core.logging.logger import LoggerFactory
from backend.knowledge.knowledge_context import KnowledgeContextBuilder
from backend.knowledge.knowledge_service import KnowledgeService
from backend.multimodal.pipeline.processor import MultimodalPipelineContext


class ContextStage:
    """Create user-readable multimodal context from processed analyses."""

    def __init__(
        self,
        knowledge_service: KnowledgeService,
        knowledge_context_builder: KnowledgeContextBuilder,
    ) -> None:
        self.knowledge_service = knowledge_service
        self.knowledge_context_builder = knowledge_context_builder
        self.logger = LoggerFactory.get_logger("ContextStage")

    def process(self, context: MultimodalPipelineContext) -> MultimodalPipelineContext:
        knowledge_ids = list(context.conversation.knowledge_object_ids)
        knowledge_objects = self.knowledge_service.load_many(knowledge_ids)
        built = self.knowledge_context_builder.build(knowledge_objects)
        context.knowledge_context = built.rendered_text
        context.generated_context = built.rendered_text
        context.metadata["context_status"] = (
            "enabled" if built.rendered_text else "disabled"
        )
        if built.rendered_text:
            self.logger.debug(
                "Context injected knowledge_objects=%s", len(built.knowledge_ids)
            )
        return context
