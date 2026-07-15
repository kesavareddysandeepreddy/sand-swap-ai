"""Attachment type definitions for multimodal routing."""

from __future__ import annotations

from enum import StrEnum


class AttachmentType(StrEnum):
    """Supported high-level attachment categories."""

    IMAGE = "image"
    PDF = "pdf"
    WORD = "word"
    EXCEL = "excel"
    POWERPOINT = "powerpoint"
    TEXT = "text"
    CSV = "csv"
    UNKNOWN = "unknown"
