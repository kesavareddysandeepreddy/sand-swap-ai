"""Parser implementations for universal knowledge ingestion."""

from __future__ import annotations

import configparser
import csv
import json
import re
import tomllib
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from xml.etree import ElementTree
from zipfile import ZipFile

from backend.rag.domain.interfaces import DocumentParser
from backend.rag.domain.models import ParsedDocument


def _read_text_file(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _zip_xml_text(path: Path, xml_path: str) -> str:
    with ZipFile(path, "r") as archive:
        with archive.open(xml_path) as xml_file:
            xml_bytes = xml_file.read()
    root = ElementTree.fromstring(xml_bytes)
    return " ".join(text.strip() for text in root.itertext() if text.strip())


class PDFParser(DocumentParser):
    """Parse PDF documents."""

    def parse(self, file_path: str) -> ParsedDocument:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF parsing requires pypdf") from exc

        reader = PdfReader(file_path)
        pages: list[str] = []
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            pages.append(f"[Page {index}]\n{text}")

        return ParsedDocument(
            text="\n\n".join(pages),
            metadata={"page_count": len(reader.pages)},
        )


class WordParser(DocumentParser):
    """Parse DOCX, DOC, and ODT files."""

    def parse(self, file_path: str) -> ParsedDocument:
        path = Path(file_path)
        suffix = path.suffix.lower()
        if suffix == ".docx":
            text = _zip_xml_text(path, "word/document.xml")
            return ParsedDocument(text=text, metadata={"format": "docx"})
        if suffix == ".odt":
            text = _zip_xml_text(path, "content.xml")
            return ParsedDocument(text=text, metadata={"format": "odt"})

        # Legacy .doc extraction via antiword if available.
        try:
            import subprocess

            completed = subprocess.run(
                ["antiword", file_path],
                check=True,
                capture_output=True,
                text=True,
            )
            return ParsedDocument(text=completed.stdout, metadata={"format": "doc"})
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("DOC parsing requires antiword to be installed") from exc


class ExcelParser(DocumentParser):
    """Parse XLSX, XLS, and ODS files."""

    def parse(self, file_path: str) -> ParsedDocument:
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix in {".xlsx", ".xls"}:
            try:
                from openpyxl import load_workbook
            except ImportError as exc:
                raise RuntimeError("Excel parsing requires openpyxl") from exc

            workbook = load_workbook(file_path, data_only=True, read_only=True)
            sheet_names = workbook.sheetnames
            blocks: list[str] = []
            for sheet_name in sheet_names:
                sheet = workbook[sheet_name]
                rows = []
                for row in sheet.iter_rows(values_only=True):
                    values = ["" if value is None else str(value) for value in row]
                    rows.append("\t".join(values))
                blocks.append(f"[Worksheet: {sheet_name}]\n" + "\n".join(rows))
            return ParsedDocument(
                text="\n\n".join(blocks),
                metadata={"worksheets": sheet_names, "format": suffix.lstrip(".")},
            )

        if suffix == ".ods":
            text = _zip_xml_text(path, "content.xml")
            return ParsedDocument(text=text, metadata={"format": "ods"})

        raise RuntimeError(f"Unsupported spreadsheet type: {suffix}")


class CSVParser(DocumentParser):
    """Parse CSV and TSV files."""

    def parse(self, file_path: str) -> ParsedDocument:
        path = Path(file_path)
        content = _read_text_file(path)
        sample = content[:4096]
        delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
        try:
            dialect = csv.Sniffer().sniff(sample)
            delimiter = dialect.delimiter
        except csv.Error:
            pass

        rows: list[list[str]] = []
        reader = csv.reader(content.splitlines(), delimiter=delimiter)
        for row in reader:
            rows.append([value.strip() for value in row])

        lines = [" | ".join(row) for row in rows]
        headers = rows[0] if rows else []
        return ParsedDocument(
            text="\n".join(lines),
            metadata={
                "delimiter": delimiter,
                "row_count": len(rows),
                "headers": headers,
            },
        )


class PowerPointParser(DocumentParser):
    """Parse PPTX, PPT, and ODP files."""

    def parse(self, file_path: str) -> ParsedDocument:
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".pptx":
            with ZipFile(path, "r") as archive:
                slide_files = sorted(
                    [
                        name
                        for name in archive.namelist()
                        if name.startswith("ppt/slides/slide") and name.endswith(".xml")
                    ]
                )
                slides: list[str] = []
                for index, slide_file in enumerate(slide_files, start=1):
                    with archive.open(slide_file) as xml_file:
                        slide_root = ElementTree.fromstring(xml_file.read())
                    text = " ".join(
                        value.strip()
                        for value in slide_root.itertext()
                        if value.strip()
                    )
                    slides.append(f"[Slide {index}]\n{text}")

            return ParsedDocument(
                text="\n\n".join(slides),
                metadata={"slide_count": len(slides), "format": "pptx"},
            )

        if suffix == ".odp":
            text = _zip_xml_text(path, "content.xml")
            return ParsedDocument(text=text, metadata={"format": "odp"})

        # Legacy .ppt fallback
        return ParsedDocument(
            text=_read_text_file(path),
            metadata={"format": "ppt", "warning": "binary_legacy_format"},
        )


class MarkdownParser(DocumentParser):
    """Parse markdown files."""

    def parse(self, file_path: str) -> ParsedDocument:
        text = _read_text_file(Path(file_path))
        headings = re.findall(r"^#{1,6}\s+(.+)$", text, flags=re.MULTILINE)
        return ParsedDocument(
            text=text, language="markdown", metadata={"headings": headings}
        )


class TextParser(DocumentParser):
    """Parse generic text files."""

    def parse(self, file_path: str) -> ParsedDocument:
        return ParsedDocument(text=_read_text_file(Path(file_path)))


class JsonParser(DocumentParser):
    """Parse JSON files."""

    def parse(self, file_path: str) -> ParsedDocument:
        payload = json.loads(_read_text_file(Path(file_path)))
        pretty = json.dumps(payload, indent=2, sort_keys=True)
        return ParsedDocument(
            text=pretty, language="json", metadata={"root": type(payload).__name__}
        )


class XmlParser(DocumentParser):
    """Parse XML files."""

    def parse(self, file_path: str) -> ParsedDocument:
        root = ElementTree.parse(file_path).getroot()
        text = "\n".join(value.strip() for value in root.itertext() if value.strip())
        return ParsedDocument(
            text=text, language="xml", metadata={"root_tag": root.tag}
        )


class YamlParser(DocumentParser):
    """Parse YAML files."""

    def parse(self, file_path: str) -> ParsedDocument:
        raw = _read_text_file(Path(file_path))
        metadata: dict[str, Any] = {}
        try:
            import yaml

            payload = yaml.safe_load(raw)
            metadata["root"] = type(payload).__name__ if payload is not None else "none"
        except ImportError:
            metadata["root"] = "unknown"
        return ParsedDocument(text=raw, language="yaml", metadata=metadata)


class CodeParser(DocumentParser):
    """Parse source-code files."""

    LANGUAGE_BY_SUFFIX = {
        ".py": "python",
        ".java": "java",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".jsx": "jsx",
        ".cs": "csharp",
        ".vb": "vb",
        ".c": "c",
        ".cpp": "cpp",
        ".go": "go",
        ".rs": "rust",
        ".kt": "kotlin",
        ".swift": "swift",
        ".php": "php",
        ".rb": "ruby",
        ".scala": "scala",
        ".sql": "sql",
        ".ps1": "powershell",
        ".sh": "shell",
    }

    def parse(self, file_path: str) -> ParsedDocument:
        path = Path(file_path)
        text = _read_text_file(path)
        language = self.LANGUAGE_BY_SUFFIX.get(path.suffix.lower(), "code")
        return ParsedDocument(
            text=text,
            language=language,
            metadata={"line_count": text.count("\n") + 1},
        )


class _HTMLTextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        cleaned = data.strip()
        if cleaned:
            self.parts.append(cleaned)


class ConfigParser(DocumentParser):
    """Parse infra and configuration files."""

    def parse(self, file_path: str) -> ParsedDocument:
        path = Path(file_path)
        suffix = path.suffix.lower()
        name = path.name.lower()
        raw = _read_text_file(path)
        metadata: dict[str, Any] = {}

        if suffix in {".toml"}:
            data = tomllib.loads(raw)
            metadata["keys"] = sorted(data.keys())
        elif suffix in {".ini"}:
            parser = configparser.ConfigParser()
            parser.read_string(raw)
            metadata["sections"] = parser.sections()
        elif suffix in {".html", ".htm"}:
            collector = _HTMLTextCollector()
            collector.feed(raw)
            raw = "\n".join(collector.parts)
            metadata["format"] = "html"
        elif name in {"dockerfile", "docker-compose.yml", "docker-compose.yaml"}:
            metadata["format"] = name
        elif suffix in {".yaml", ".yml"}:
            metadata["format"] = "yaml"

        return ParsedDocument(text=raw, metadata=metadata)


class ImageParser(DocumentParser):
    """Parse image metadata and optional OCR text."""

    def parse(self, file_path: str) -> ParsedDocument:
        path = Path(file_path)
        metadata: dict[str, Any] = {}
        extracted_text = ""

        try:
            from PIL import Image

            with Image.open(path) as image:
                metadata["width"] = image.width
                metadata["height"] = image.height
                metadata["mode"] = image.mode

                try:
                    import pytesseract

                    extracted_text = pytesseract.image_to_string(image).strip()
                except Exception:  # noqa: BLE001
                    extracted_text = ""
        except ImportError:
            metadata["warning"] = "Pillow not installed"

        if not extracted_text:
            extracted_text = f"Image file: {path.name}"

        return ParsedDocument(text=extracted_text, metadata=metadata)


class EmailParser(DocumentParser):
    """Parse EML and MSG email files."""

    def parse(self, file_path: str) -> ParsedDocument:
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".eml":
            with path.open("rb") as stream:
                message = BytesParser(policy=policy.default).parse(stream)

            subject = message.get("subject", "")
            sender = message.get("from", "")
            recipient = message.get("to", "")
            body = self._extract_email_body(message)
            text = (
                f"Subject: {subject}\nFrom: {sender}\nTo: {recipient}\n\n{body}".strip()
            )
            return ParsedDocument(
                text=text,
                metadata={"subject": subject, "from": sender, "to": recipient},
            )

        try:
            import extract_msg
        except ImportError as exc:
            raise RuntimeError("MSG parsing requires extract-msg") from exc

        message = extract_msg.Message(file_path)
        text = (
            f"Subject: {message.subject}\nFrom: {message.sender}\n"
            f"To: {message.to}\n\n{message.body or ''}"
        )
        return ParsedDocument(
            text=text,
            metadata={
                "subject": message.subject,
                "from": message.sender,
                "to": message.to,
            },
        )

    def _extract_email_body(self, message: Any) -> str:
        if message.is_multipart():
            parts = []
            for part in message.walk():
                if part.get_content_type() in {"text/plain", "text/html"}:
                    try:
                        parts.append(part.get_content())
                    except Exception:  # noqa: BLE001
                        continue
            return "\n".join(parts)
        return message.get_content() or ""


class EngineeringParser(DocumentParser):
    """Parse engineering documents such as FDS/URS/SDS/P&ID exports."""

    SECTION_PATTERN = re.compile(r"^(\d+(?:\.\d+)*)\s+([A-Za-z].+)$")

    def parse(self, file_path: str) -> ParsedDocument:
        path = Path(file_path)
        text = _read_text_file(path)
        sections: list[str] = []

        for line in text.splitlines():
            match = self.SECTION_PATTERN.match(line.strip())
            if match:
                sections.append(match.group(2).strip())

        return ParsedDocument(
            text=text,
            metadata={"sections": sections, "document_kind": path.suffix.lstrip(".")},
        )
