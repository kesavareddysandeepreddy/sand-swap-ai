"""Abstract provider contracts for multimodal analysis backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.multimodal.models import AttachmentMetadata, OCRAnalysis, VisionAnalysis


class VisionProvider(ABC):
    """Contract for image understanding providers."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return whether the provider is ready for use."""
        raise NotImplementedError

    @abstractmethod
    def analyze_image(
        self,
        image_path: str,
        metadata: AttachmentMetadata | None = None,
    ) -> VisionAnalysis:
        """Run image analysis and return structured findings."""
        raise NotImplementedError

    @abstractmethod
    def health(self) -> dict[str, Any]:
        """Return a provider health payload."""
        raise NotImplementedError


class OCRProvider(ABC):
    """Contract for text extraction providers."""

    @abstractmethod
    def extract_text(
        self,
        image_bytes: bytes,
        metadata: AttachmentMetadata,
    ) -> OCRAnalysis:
        """Run OCR and return structured text extraction output."""
        raise NotImplementedError

    @abstractmethod
    def health(self) -> dict[str, Any]:
        """Return a provider health payload."""
        raise NotImplementedError
