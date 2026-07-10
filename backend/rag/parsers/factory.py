"""Parser factory for universal file ingestion."""

from __future__ import annotations

from backend.rag.domain.interfaces import DocumentParser
from backend.rag.parsers.file_types import detect_file_spec
from backend.rag.parsers.ocr import OCRProviderFactory
from backend.rag.parsers.parser_impl import (
    CodeParser,
    ConfigParser,
    CSVParser,
    EmailParser,
    EngineeringParser,
    ExcelParser,
    HtmlParser,
    ImageParser,
    JsonParser,
    MarkdownParser,
    PDFParser,
    PowerPointParser,
    TextParser,
    WordParser,
    XmlParser,
    YamlParser,
    ZipParser,
)


class ParserFactory:
    """Resolve parser implementation from filename metadata."""

    def __init__(self, ocr_provider: str = "tesseract") -> None:
        ocr = OCRProviderFactory().create(ocr_provider)
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
            "image": ImageParser(ocr_provider=ocr),
            "email": EmailParser(),
            "engineering": EngineeringParser(),
            "config": ConfigParser(),
            "html": HtmlParser(),
        }
        self._parsers["zip"] = ZipParser(parser_resolver=self.resolve)

    def resolve(self, file_name: str) -> DocumentParser:
        """Return parser based on filename and extension registry."""
        spec = detect_file_spec(file_name)
        parser = self._parsers.get(spec.parser)
        if parser is None:
            raise ValueError(f"No parser registered for '{spec.parser}'")
        return parser
