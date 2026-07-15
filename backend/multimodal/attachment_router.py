"""Attachment routing utilities for multimodal classification."""

from __future__ import annotations

import mimetypes
from pathlib import Path

from backend.multimodal.attachment_types import AttachmentType


class AttachmentRouter:
    """Detect MIME types and classify attachments into supported categories."""

    _WORD_MIME_TYPES = {
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    _EXCEL_MIME_TYPES = {
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    _POWERPOINT_MIME_TYPES = {
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }

    def detect_mime_type(
        self,
        filename: str,
        provided_mime_type: str | None = None,
    ) -> str:
        """Return explicit MIME type when provided, otherwise infer from filename."""
        if provided_mime_type:
            normalized = provided_mime_type.strip().lower()
            if normalized:
                return normalized

        guessed, _ = mimetypes.guess_type(filename)
        return guessed or "application/octet-stream"

    def classify_attachment(
        self,
        filename: str,
        mime_type: str | None = None,
    ) -> AttachmentType:
        """Classify an attachment based on MIME type and file extension."""
        detected_mime = self.detect_mime_type(
            filename=filename, provided_mime_type=mime_type
        )
        extension = Path(filename).suffix.lower()

        if detected_mime.startswith("image/"):
            return AttachmentType.IMAGE
        if detected_mime == "application/pdf" or extension == ".pdf":
            return AttachmentType.PDF
        if detected_mime in self._WORD_MIME_TYPES or extension in {".doc", ".docx"}:
            return AttachmentType.WORD
        if detected_mime in self._EXCEL_MIME_TYPES or extension in {".xls", ".xlsx"}:
            return AttachmentType.EXCEL
        if detected_mime in self._POWERPOINT_MIME_TYPES or extension in {
            ".ppt",
            ".pptx",
        }:
            return AttachmentType.POWERPOINT
        if detected_mime == "text/csv" or extension == ".csv":
            return AttachmentType.CSV
        if detected_mime.startswith("text/") or extension in {
            ".txt",
            ".md",
            ".json",
            ".yaml",
            ".yml",
            ".log",
        }:
            return AttachmentType.TEXT
        return AttachmentType.UNKNOWN
