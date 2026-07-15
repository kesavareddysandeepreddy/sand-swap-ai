"""Typed multimodal models for attachment metadata and analysis artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AttachmentMetadata:
    """Metadata describing one uploaded attachment."""

    filename: str
    mime_type: str
    extension: str
    size: int
    width: int | None = None
    height: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class VisionAnalysis:
    """Vision-provider output for one image attachment."""

    summary: str = ""
    description: str = ""
    objects: list[str] = field(default_factory=list)
    ocr_text: str = ""
    confidence: float = 0.0
    provider: str = ""
    processing_time: float = 0.0
    raw_response: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OCRAnalysis:
    """OCR-provider output for one attachment."""

    ocr_text: str = ""
    tables: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    provider: str = ""
    processing_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AttachmentAnalysis:
    """Unified analysis record for an attachment."""

    filename: str
    mime_type: str
    extension: str
    size: int
    width: int | None = None
    height: int | None = None
    summary: str = ""
    description: str = ""
    objects: list[str] = field(default_factory=list)
    ocr_text: str = ""
    tables: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    provider: str = ""
    processing_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    vision: VisionAnalysis | None = None
    ocr: OCRAnalysis | None = None


@dataclass(slots=True)
class AttachmentContext:
    """Attachment-derived context payload for downstream chat composition."""

    attachments: list[AttachmentMetadata] = field(default_factory=list)
    analyses: list[AttachmentAnalysis] = field(default_factory=list)
    summary: str = "No attachments"
    metadata: dict[str, Any] = field(default_factory=dict)
