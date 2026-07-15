"""Multimodal infrastructure interfaces and primitives."""

from backend.multimodal.attachment_router import AttachmentRouter
from backend.multimodal.attachment_types import AttachmentType
from backend.multimodal.image_cache import ImageCache, InMemoryImageCache
from backend.multimodal.models import (
    AttachmentAnalysis,
    AttachmentContext,
    AttachmentMetadata,
    OCRAnalysis,
    VisionAnalysis,
)
from backend.multimodal.multimodal_context import AttachmentContextBuilder
from backend.multimodal.providers.base import OCRProvider, VisionProvider
from backend.multimodal.providers.ollama_vision_provider import OllamaVisionProvider
from backend.multimodal.providers.registry import ProviderRegistry

__all__ = [
    "AttachmentAnalysis",
    "AttachmentContext",
    "AttachmentContextBuilder",
    "AttachmentMetadata",
    "AttachmentRouter",
    "AttachmentType",
    "ImageCache",
    "InMemoryImageCache",
    "OCRAnalysis",
    "OCRProvider",
    "OllamaVisionProvider",
    "ProviderRegistry",
    "VisionAnalysis",
    "VisionProvider",
]
