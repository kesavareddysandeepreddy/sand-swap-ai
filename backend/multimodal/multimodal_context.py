"""Attachment context builder for future multimodal chat enrichment."""

from __future__ import annotations

from pathlib import Path

from backend.multimodal.attachment_router import AttachmentRouter
from backend.multimodal.attachment_types import AttachmentType
from backend.multimodal.image_cache import ImageCache
from backend.multimodal.models import (
    AttachmentAnalysis,
    AttachmentContext,
    AttachmentMetadata,
)
from backend.multimodal.providers.registry import ProviderRegistry


class AttachmentContextBuilder:
    """Build chat context from attachments and optional vision analysis."""

    def __init__(
        self,
        *,
        attachment_router: AttachmentRouter,
        provider_registry: ProviderRegistry,
        image_cache: ImageCache,
        supported_types: list[str] | None = None,
    ) -> None:
        self.attachment_router = attachment_router
        self.provider_registry = provider_registry
        self.image_cache = image_cache
        self.supported_types = supported_types or []

    def build_context(
        self,
        attachments: list[AttachmentMetadata] | None = None,
        analyses: list[AttachmentAnalysis] | None = None,
    ) -> AttachmentContext:
        if not attachments:
            return AttachmentContext(
                attachments=[],
                analyses=[],
                summary="No attachments",
                metadata={"status": "disabled", "reason": "no_attachments"},
            )

        vision_provider = self.provider_registry.get_active_vision_provider()
        if vision_provider is None and not analyses:
            return AttachmentContext(
                attachments=list(attachments),
                analyses=[],
                summary="No attachments",
                metadata={
                    "status": "disabled",
                    "reason": "vision_provider_unavailable",
                },
            )

        resolved_analyses: list[AttachmentAnalysis] = list(analyses or [])
        context_blocks: list[str] = []
        normalized_supported_types = {item.lower() for item in self.supported_types}

        if not resolved_analyses and vision_provider is not None:
            for attachment in attachments:
                attachment_type = self.attachment_router.classify_attachment(
                    filename=attachment.filename,
                    mime_type=attachment.mime_type,
                )
                if attachment_type != AttachmentType.IMAGE:
                    continue
                if (
                    normalized_supported_types
                    and attachment_type.value not in normalized_supported_types
                ):
                    continue

                image_path = self._resolve_image_path(attachment)
                if image_path is None:
                    continue

                vision = vision_provider.analyze_image(
                    str(image_path), metadata=attachment
                )
                resolved_analyses.append(
                    AttachmentAnalysis(
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
                        metadata={
                            **vision.metadata,
                            "raw_response": vision.raw_response,
                        },
                        vision=vision,
                    )
                )

        for analysis in resolved_analyses:
            objects_text = ", ".join(analysis.objects) if analysis.objects else "none"
            visible_text = str(analysis.metadata.get("visible_text", "")).strip()
            if not visible_text:
                visible_text = "none"
            context_blocks.append(
                "\n".join(
                    [
                        "Attached Image",
                        f"Filename: {analysis.filename}",
                        f"Summary: {analysis.summary or 'none'}",
                        f"Description: {analysis.description or 'none'}",
                        f"Objects: {objects_text}",
                        f"Visible Text: {visible_text}",
                        f"Provider: {analysis.provider or 'unknown'}",
                        f"Confidence: {analysis.confidence:.2f}",
                    ]
                )
            )

        if not resolved_analyses:
            return AttachmentContext(
                attachments=list(attachments),
                analyses=[],
                summary="No attachments",
                metadata={"status": "disabled", "reason": "no_image_analysis"},
            )

        return AttachmentContext(
            attachments=list(attachments),
            analyses=resolved_analyses,
            summary="\n\n".join(context_blocks),
            metadata={
                "status": "enabled",
                "analyzed_images": len(resolved_analyses),
                "provider_health": self.provider_registry.health().get("vision", {}),
            },
        )

    def _resolve_image_path(self, attachment: AttachmentMetadata) -> Path | None:
        metadata_path = attachment.metadata.get("path")
        if isinstance(metadata_path, str) and metadata_path.strip():
            path = Path(metadata_path.strip())
            if path.exists():
                return path

        image_path = attachment.metadata.get("image_path")
        if isinstance(image_path, str) and image_path.strip():
            path = Path(image_path.strip())
            if path.exists():
                return path

        fallback = Path(attachment.filename)
        if fallback.exists():
            return fallback
        return None
