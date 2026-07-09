"""Chunker factory for document-type-aware chunking."""

from __future__ import annotations

from backend.rag.chunkers.chunker_impl import (
    CodeChunker,
    CSVChunker,
    EmailChunker,
    EngineeringChunker,
    ExcelChunker,
    ImageChunker,
    JsonChunker,
    MarkdownChunker,
    ParagraphChunker,
    PDFChunker,
    PowerPointChunker,
    WordChunker,
    XmlChunker,
)
from backend.rag.domain.interfaces import Chunker
from backend.rag.parsers.file_types import detect_file_spec


class ChunkerFactory:
    """Resolve chunker implementation from file type mapping."""

    def __init__(self, semantic: bool = True) -> None:
        self._chunkers: dict[str, Chunker] = {
            "pdf": PDFChunker(),
            "word": WordChunker(),
            "excel": ExcelChunker(),
            "csv": CSVChunker(),
            "json": JsonChunker(),
            "xml": XmlChunker(),
            "markdown": MarkdownChunker(),
            "code": CodeChunker(),
            "powerpoint": PowerPointChunker(),
            "email": EmailChunker(),
            "engineering": EngineeringChunker(),
            "image": ImageChunker(),
            "paragraph": ParagraphChunker(semantic=semantic),
        }

    def resolve(self, file_name: str) -> Chunker:
        """Return chunker based on file spec routing table."""
        spec = detect_file_spec(file_name)
        chunker = self._chunkers.get(spec.chunker)
        if chunker is None:
            raise ValueError(f"No chunker registered for '{spec.chunker}'")
        return chunker
