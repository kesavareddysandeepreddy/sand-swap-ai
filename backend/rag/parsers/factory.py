"""Parser factory for universal file ingestion."""

from __future__ import annotations

from backend.rag.domain.interfaces import DocumentParser
from backend.rag.parsers.file_types import detect_file_spec
from backend.rag.parsers.parser_impl import (
    CodeParser,
    ConfigParser,
    CSVParser,
    EmailParser,
    EngineeringParser,
    ExcelParser,
    ImageParser,
    JsonParser,
    MarkdownParser,
    PDFParser,
    PowerPointParser,
    TextParser,
    WordParser,
    XmlParser,
    YamlParser,
)


class ParserFactory:
    """Resolve parser implementation from filename metadata."""

    def __init__(self) -> None:
        self._parsers: dict[str, DocumentParser] = {
            "pdf": PDFParser(),
            "word": WordParser(),
            "excel": ExcelParser(),
            "csv": CSVParser(),
            "powerpoint": PowerPointParser(),
            "markdown": MarkdownParser(),
            "text": TextParser(),
            "json": JsonParser(),
            "xml": XmlParser(),
            "yaml": YamlParser(),
            "code": CodeParser(),
            "image": ImageParser(),
            "email": EmailParser(),
            "engineering": EngineeringParser(),
            "config": ConfigParser(),
        }

    def resolve(self, file_name: str) -> DocumentParser:
        """Return parser based on filename and extension registry."""
        spec = detect_file_spec(file_name)
        parser = self._parsers.get(spec.parser)
        if parser is None:
            raise ValueError(f"No parser registered for '{spec.parser}'")
        return parser
