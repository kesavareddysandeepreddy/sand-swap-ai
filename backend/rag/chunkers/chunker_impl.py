"""Chunker implementations for parsed document content."""

from __future__ import annotations

import json
import re
import uuid
from typing import Iterable
from xml.etree import ElementTree

from backend.rag.domain.interfaces import Chunker
from backend.rag.domain.models import DocumentChunk, DocumentRecord, ParsedDocument


def _build_chunk(
    *,
    document: DocumentRecord,
    text: str,
    metadata: dict[str, object],
) -> DocumentChunk:
    merged_metadata: dict[str, object] = {
        "document_id": document.id,
        "document_name": document.name,
        "file_type": document.file_type,
        "owner_id": document.metadata.get("owner_id"),
        "parser": document.metadata.get("parser"),
        "language": document.metadata.get("language"),
        "source_type": document.metadata.get(
            "source_type", document.metadata.get("category")
        ),
        "category": document.metadata.get("category"),
        "workspace_id": document.metadata.get("workspace_id"),
        "author": document.metadata.get("author"),
        "created": document.metadata.get("created"),
        "modified": document.metadata.get("modified"),
        "project": document.metadata.get("project"),
        "tags": document.metadata.get("tags", []),
    }
    merged_metadata.update(metadata)
    return DocumentChunk(
        id=str(uuid.uuid4()),
        document_id=document.id,
        document_name=document.name,
        text=text,
        file_type=document.file_type,
        metadata=merged_metadata,
    )


def _semantic_segments(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    return [
        segment.strip()
        for segment in re.split(r"(?<=[.!?])\s+", normalized)
        if segment.strip()
    ]


def _window_chunks(
    text: str,
    chunk_size: int,
    overlap: int,
    semantic: bool,
) -> list[str]:
    units = _semantic_segments(text) if semantic else text.splitlines()
    if not units:
        return []

    chunks: list[str] = []
    index = 0
    step = max(1, chunk_size - overlap)
    while index < len(units):
        window = units[index : index + chunk_size]
        content = (
            "\n".join(window).strip() if not semantic else " ".join(window).strip()
        )
        if content:
            chunks.append(content)
        index += step
    return chunks


class ParagraphChunker(Chunker):
    """Generic paragraph chunking."""

    def __init__(self, semantic: bool = True) -> None:
        self.semantic = semantic

    def chunk(
        self,
        document: DocumentRecord,
        parsed: ParsedDocument,
        chunk_size: int,
        overlap: int,
    ) -> list[DocumentChunk]:
        chunk_texts = _window_chunks(parsed.text, chunk_size, overlap, self.semantic)
        return [
            _build_chunk(
                document=document, text=content, metadata={"section": "paragraph"}
            )
            for content in chunk_texts
        ]


class PDFChunker(Chunker):
    """Chunk PDFs by page and heading cues."""

    PAGE_PATTERN = re.compile(r"\[Page\s+(\d+)\]\s*", flags=re.IGNORECASE)

    def chunk(
        self,
        document: DocumentRecord,
        parsed: ParsedDocument,
        chunk_size: int,
        overlap: int,
    ) -> list[DocumentChunk]:
        pages = self.PAGE_PATTERN.split(parsed.text)
        # split returns ['', pageNo, content, pageNo, content...]
        chunks: list[DocumentChunk] = []
        for index in range(1, len(pages), 2):
            page_number = int(pages[index])
            content = pages[index + 1]
            for segment in _window_chunks(content, chunk_size, overlap, semantic=True):
                heading = segment.split("\n", 1)[0][:120]
                chunks.append(
                    _build_chunk(
                        document=document,
                        text=segment,
                        metadata={"page": page_number, "section": heading},
                    )
                )
        return chunks


class WordChunker(Chunker):
    """Chunk word docs by heading sections."""

    HEADING_PATTERN = re.compile(r"^(#{1,6}|\d+(?:\.\d+)*)\s+(.+)$")

    def chunk(
        self,
        document: DocumentRecord,
        parsed: ParsedDocument,
        chunk_size: int,
        overlap: int,
    ) -> list[DocumentChunk]:
        lines = parsed.text.splitlines()
        sections: list[tuple[str, list[str]]] = []
        current_heading = "Introduction"
        current_lines: list[str] = []

        for line in lines:
            match = self.HEADING_PATTERN.match(line.strip())
            if match and current_lines:
                sections.append((current_heading, current_lines))
                current_heading = match.group(2)
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            sections.append((current_heading, current_lines))

        chunks: list[DocumentChunk] = []
        for heading, section_lines in sections:
            content = "\n".join(section_lines)
            for segment in _window_chunks(content, chunk_size, overlap, semantic=True):
                chunks.append(
                    _build_chunk(
                        document=document,
                        text=segment,
                        metadata={"section": heading},
                    )
                )
        return chunks


class ExcelChunker(Chunker):
    """Chunk spreadsheets by worksheet and row windows."""

    WORKSHEET_PATTERN = re.compile(r"^\[Worksheet:\s*(.+?)\]\s*$")

    def chunk(
        self,
        document: DocumentRecord,
        parsed: ParsedDocument,
        chunk_size: int,
        overlap: int,
    ) -> list[DocumentChunk]:
        lines = parsed.text.splitlines()
        worksheet = "Sheet1"
        rows: list[str] = []
        chunks: list[DocumentChunk] = []

        def flush_rows(name: str, values: list[str]) -> None:
            for index, segment in enumerate(
                _window_chunks("\n".join(values), chunk_size, overlap, semantic=False),
                start=1,
            ):
                chunks.append(
                    _build_chunk(
                        document=document,
                        text=segment,
                        metadata={"worksheet": name, "table": "grid", "part": index},
                    )
                )

        for line in lines:
            match = self.WORKSHEET_PATTERN.match(line)
            if match:
                if rows:
                    flush_rows(worksheet, rows)
                    rows = []
                worksheet = match.group(1).strip()
            else:
                rows.append(line)

        if rows:
            flush_rows(worksheet, rows)

        return chunks


class CSVChunker(Chunker):
    """Chunk CSV files by schema and row windows."""

    def chunk(
        self,
        document: DocumentRecord,
        parsed: ParsedDocument,
        chunk_size: int,
        overlap: int,
    ) -> list[DocumentChunk]:
        lines = parsed.text.splitlines()
        if not lines:
            return []

        chunks = [
            _build_chunk(
                document=document,
                text=lines[0],
                metadata={
                    "section": "schema",
                    "headers": parsed.metadata.get("headers", []),
                },
            )
        ]

        row_text = "\n".join(lines[1:])
        for index, segment in enumerate(
            _window_chunks(row_text, chunk_size, overlap, semantic=False),
            start=1,
        ):
            chunks.append(
                _build_chunk(
                    document=document,
                    text=segment,
                    metadata={"section": "rows", "part": index},
                )
            )
        return chunks


class JsonChunker(Chunker):
    """Chunk JSON by top-level objects and arrays."""

    def chunk(
        self,
        document: DocumentRecord,
        parsed: ParsedDocument,
        chunk_size: int,
        overlap: int,
    ) -> list[DocumentChunk]:
        payload = json.loads(parsed.text)
        chunks: list[DocumentChunk] = []

        if isinstance(payload, dict):
            items = list(payload.items())
            for key, value in items:
                chunks.append(
                    _build_chunk(
                        document=document,
                        text=json.dumps(value, indent=2, sort_keys=True),
                        metadata={"section": "object", "object_key": key},
                    )
                )
        elif isinstance(payload, list):
            for index, value in enumerate(payload, start=1):
                chunks.append(
                    _build_chunk(
                        document=document,
                        text=json.dumps(value, indent=2, sort_keys=True),
                        metadata={"section": "array_item", "item_index": index},
                    )
                )
        else:
            chunks.append(
                _build_chunk(
                    document=document,
                    text=parsed.text,
                    metadata={"section": "scalar"},
                )
            )

        return chunks


class XmlChunker(Chunker):
    """Chunk XML by element nodes."""

    def chunk(
        self,
        document: DocumentRecord,
        parsed: ParsedDocument,
        chunk_size: int,
        overlap: int,
    ) -> list[DocumentChunk]:
        root = ElementTree.fromstring(parsed.text)
        chunks: list[DocumentChunk] = []
        for index, element in enumerate(root.iter(), start=1):
            text = " ".join(
                value.strip() for value in element.itertext() if value.strip()
            )
            if not text:
                continue
            chunks.append(
                _build_chunk(
                    document=document,
                    text=text,
                    metadata={
                        "section": "xml_node",
                        "node": element.tag,
                        "node_index": index,
                    },
                )
            )
        return chunks


class MarkdownChunker(Chunker):
    """Chunk markdown by headers."""

    HEADER_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", flags=re.MULTILINE)

    def chunk(
        self,
        document: DocumentRecord,
        parsed: ParsedDocument,
        chunk_size: int,
        overlap: int,
    ) -> list[DocumentChunk]:
        lines = parsed.text.splitlines()
        chunks: list[DocumentChunk] = []
        header = "Document"
        buffer: list[str] = []

        def flush_buffer(section_name: str, values: Iterable[str]) -> None:
            content = "\n".join(values)
            for segment in _window_chunks(content, chunk_size, overlap, semantic=True):
                chunks.append(
                    _build_chunk(
                        document=document,
                        text=segment,
                        metadata={"section": section_name},
                    )
                )

        for line in lines:
            match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if match:
                if buffer:
                    flush_buffer(header, buffer)
                    buffer = []
                header = match.group(2).strip()
            else:
                buffer.append(line)

        if buffer:
            flush_buffer(header, buffer)

        return chunks


class CodeChunker(Chunker):
    """Chunk source code around imports, classes, and functions."""

    CLASS_PATTERN = re.compile(r"^\s*(class|interface|struct)\s+([A-Za-z_][\w]*)")
    FUNC_PATTERN = re.compile(
        r"^\s*(def|function|fn|public|private|protected)\s+([A-Za-z_][\w]*)"
    )
    IMPORT_PATTERN = re.compile(r"^\s*(import|from|using|package)\b")

    def chunk(
        self,
        document: DocumentRecord,
        parsed: ParsedDocument,
        chunk_size: int,
        overlap: int,
    ) -> list[DocumentChunk]:
        lines = parsed.text.splitlines()
        chunks: list[DocumentChunk] = []

        for index, line in enumerate(lines):
            class_match = self.CLASS_PATTERN.match(line)
            func_match = self.FUNC_PATTERN.match(line)
            import_match = self.IMPORT_PATTERN.match(line)

            if not class_match and not func_match and not import_match:
                continue

            start = max(0, index - overlap)
            end = min(len(lines), index + chunk_size)
            snippet = "\n".join(lines[start:end]).strip()
            if not snippet:
                continue

            metadata = {"section": "code"}
            if class_match:
                metadata["class_name"] = class_match.group(2)
                metadata["section"] = "class"
            if func_match:
                metadata["function_name"] = func_match.group(2)
                metadata["section"] = "function"
            if import_match:
                metadata["section"] = "import"

            chunks.append(
                _build_chunk(document=document, text=snippet, metadata=metadata)
            )

        if not chunks:
            for segment in _window_chunks(
                parsed.text, chunk_size, overlap, semantic=False
            ):
                chunks.append(
                    _build_chunk(
                        document=document, text=segment, metadata={"section": "code"}
                    )
                )

        return chunks


class PowerPointChunker(Chunker):
    """Chunk presentation text by slide."""

    SLIDE_PATTERN = re.compile(r"\[Slide\s+(\d+)\]\s*", flags=re.IGNORECASE)

    def chunk(
        self,
        document: DocumentRecord,
        parsed: ParsedDocument,
        chunk_size: int,
        overlap: int,
    ) -> list[DocumentChunk]:
        sections = self.SLIDE_PATTERN.split(parsed.text)
        chunks: list[DocumentChunk] = []
        for index in range(1, len(sections), 2):
            slide_number = int(sections[index])
            content = sections[index + 1].strip()
            for segment in _window_chunks(content, chunk_size, overlap, semantic=True):
                chunks.append(
                    _build_chunk(
                        document=document,
                        text=segment,
                        metadata={
                            "slide": slide_number,
                            "section": f"Slide {slide_number}",
                        },
                    )
                )
        return chunks


class EmailChunker(Chunker):
    """Chunk email by thread-like sections."""

    SPLIT_PATTERN = re.compile(r"\n(?:From:|On\s.+wrote:)\s", flags=re.IGNORECASE)

    def chunk(
        self,
        document: DocumentRecord,
        parsed: ParsedDocument,
        chunk_size: int,
        overlap: int,
    ) -> list[DocumentChunk]:
        parts = [
            segment.strip()
            for segment in self.SPLIT_PATTERN.split(parsed.text)
            if segment.strip()
        ]
        if not parts:
            parts = [parsed.text]

        return [
            _build_chunk(
                document=document,
                text=part,
                metadata={"section": "email_thread", "part": index},
            )
            for index, part in enumerate(parts, start=1)
        ]


class EngineeringChunker(Chunker):
    """Chunk engineering docs by numbered sections and equipment lines."""

    SECTION_PATTERN = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$")
    EQUIPMENT_PATTERN = re.compile(r"\b([A-Z]{2,}-\d{2,})\b")

    def chunk(
        self,
        document: DocumentRecord,
        parsed: ParsedDocument,
        chunk_size: int,
        overlap: int,
    ) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        section_name = "Overview"
        lines: list[str] = []

        def flush(section: str, values: list[str]) -> None:
            content = "\n".join(values)
            equipment = sorted(set(self.EQUIPMENT_PATTERN.findall(content)))
            for segment in _window_chunks(content, chunk_size, overlap, semantic=True):
                chunks.append(
                    _build_chunk(
                        document=document,
                        text=segment,
                        metadata={
                            "section": section,
                            "equipment": equipment,
                            "table": "detected",
                        },
                    )
                )

        for line in parsed.text.splitlines():
            match = self.SECTION_PATTERN.match(line.strip())
            if match and lines:
                flush(section_name, lines)
                lines = []
                section_name = match.group(2)
            else:
                lines.append(line)

        if lines:
            flush(section_name, lines)

        return chunks


class ImageChunker(Chunker):
    """Chunk image documents as a single semantic record."""

    def chunk(
        self,
        document: DocumentRecord,
        parsed: ParsedDocument,
        chunk_size: int,
        overlap: int,
    ) -> list[DocumentChunk]:
        return [
            _build_chunk(
                document=document,
                text=parsed.text,
                metadata={"section": "image", "language": parsed.language},
            )
        ]
