"""Vision analysis stage for multimodal pipeline."""

from __future__ import annotations

from backend.core.logging.logger import LoggerFactory
from backend.knowledge.knowledge_service import KnowledgeService
from backend.multimodal.models import AttachmentAnalysis
from backend.multimodal.pipeline.processor import MultimodalPipelineContext
from backend.multimodal.providers.registry import ProviderRegistry


class VisionStage:
    """Analyze image attachments with the active vision provider."""

    def __init__(
        self,
        provider_registry: ProviderRegistry,
        knowledge_service: KnowledgeService,
    ) -> None:
        self.provider_registry = provider_registry
        self.knowledge_service = knowledge_service
        self.logger = LoggerFactory.get_logger("VisionStage")

    def process(self, context: MultimodalPipelineContext) -> MultimodalPipelineContext:
        provider = self.provider_registry.get_active_vision_provider()
        if provider is None:
            context.metadata["vision_status"] = "unavailable"
            context.metadata["vision_reason"] = "no_vision_model"
            return context

        analyses: list[AttachmentAnalysis] = []
        knowledge_by_id = {item.id: item for item in context.knowledge_objects}

        for attachment in context.attachments:
            knowledge_id = attachment.metadata.get("knowledge_object_id")
            if not isinstance(knowledge_id, str) or not knowledge_id:
                continue

            knowledge_object = knowledge_by_id.get(knowledge_id)
            if (
                knowledge_object is not None
                and isinstance(knowledge_object.vision_analysis, dict)
                and knowledge_object.vision_analysis
            ):
                self.logger.debug("Cache hit knowledge_object=%s", knowledge_id)
                payload = dict(knowledge_object.vision_analysis)
                context.conversation.analysis_cache[
                    str(attachment.metadata.get("sha256") or attachment.filename)
                ] = payload
                analyses.append(
                    AttachmentAnalysis(
                        filename=attachment.filename,
                        mime_type=attachment.mime_type,
                        extension=attachment.extension,
                        size=attachment.size,
                        width=attachment.width,
                        height=attachment.height,
                        summary=knowledge_object.semantic_summary,
                        description=knowledge_object.description,
                        objects=list(knowledge_object.objects),
                        ocr_text=knowledge_object.ocr_text,
                        confidence=knowledge_object.confidence,
                        provider=knowledge_object.provider,
                        processing_time=knowledge_object.processing_time,
                        metadata={
                            **(
                                payload.get("metadata", {})
                                if isinstance(payload.get("metadata"), dict)
                                else {}
                            ),
                            "cache_hit": True,
                        },
                    )
                )
                continue

            cache_key = str(attachment.metadata.get("sha256") or attachment.filename)
            cached_payload = context.conversation.analysis_cache.get(cache_key)

            if isinstance(cached_payload, dict):
                self.logger.debug("Cache hit key=%s", cache_key)
                knowledge_object = self.knowledge_service.apply_cache_payload(
                    knowledge_id=knowledge_id,
                    payload=cached_payload,
                )
                analyses.append(
                    AttachmentAnalysis(
                        filename=attachment.filename,
                        mime_type=attachment.mime_type,
                        extension=attachment.extension,
                        size=attachment.size,
                        width=attachment.width,
                        height=attachment.height,
                        summary=knowledge_object.semantic_summary,
                        description=knowledge_object.description,
                        objects=list(knowledge_object.objects),
                        ocr_text=knowledge_object.ocr_text,
                        confidence=knowledge_object.confidence,
                        provider=knowledge_object.provider,
                        processing_time=knowledge_object.processing_time,
                        metadata={
                            **(
                                knowledge_object.vision_analysis.get("metadata", {})
                                if isinstance(
                                    knowledge_object.vision_analysis.get("metadata"),
                                    dict,
                                )
                                else {}
                            ),
                            "cache_hit": True,
                        },
                    )
                )
                continue

            image_path = attachment.metadata.get("path")
            if not isinstance(image_path, str) or not image_path.strip():
                continue

            self.logger.debug("Cache miss key=%s", cache_key)
            self.logger.debug(
                "Vision analysis started filename=%s", attachment.filename
            )
            try:
                vision = provider.analyze_image(image_path.strip(), metadata=attachment)
            except Exception as exc:  # noqa: BLE001
                self.logger.debug(
                    "Vision analysis skipped filename=%s error=%s",
                    attachment.filename,
                    exc,
                )
                continue

            analysis = AttachmentAnalysis(
                filename=attachment.filename,
                mime_type=attachment.mime_type,
                extension=attachment.extension,
                size=attachment.size,
                width=attachment.width,
                height=attachment.height,
                summary=vision.summary,
                description=vision.description,
                objects=list(vision.objects),
                ocr_text=vision.ocr_text,
                confidence=vision.confidence,
                provider=vision.provider,
                processing_time=vision.processing_time,
                metadata=dict(vision.metadata),
                vision=vision,
            )
            self.knowledge_service.apply_vision_analysis(
                knowledge_id=knowledge_id,
                analysis=analysis,
            )
            analyses.append(analysis)
            context.conversation.analysis_cache[cache_key] = {
                "summary": analysis.summary,
                "description": analysis.description,
                "objects": list(analysis.objects),
                "ocr_text": analysis.ocr_text,
                "confidence": analysis.confidence,
                "provider": analysis.provider,
                "processing_time": analysis.processing_time,
                "metadata": dict(analysis.metadata),
            }
            self.logger.debug(
                "Vision completed filename=%s provider=%s",
                attachment.filename,
                analysis.provider,
            )

        context.analyses = analyses
        context.metadata["vision_status"] = "completed"
        context.metadata["analysis_count"] = len(analyses)
        return context
