"""Parser implementations for universal knowledge ingestion."""

from __future__ import annotations

import configparser
import csv
import json
import re
import tempfile
import tomllib
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any
from xml.etree import ElementTree
from zipfile import ZipFile

from backend.rag.domain.interfaces import DocumentParser
from backend.rag.domain.models import ParsedDocument
from backend.rag.parsers.file_types import detect_file_spec
from backend.rag.parsers.ocr import OCRProvider, OCRProviderFactory


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
        headings: list[dict[str, Any]] = []
        table_hints = 0
        image_count = 0
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            pages.append(f"[Page {index}]\n{text}")
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                if re.match(r"^(\d+(?:\.\d+)+\s+.+|[A-Z][A-Z\s\-]{6,})$", stripped):
                    headings.append({"page": index, "heading": stripped[:180]})
                if "|" in stripped or "\t" in stripped:
                    table_hints += 1

            resources = getattr(page, "/Resources", None)
            x_objects = {}
            if isinstance(resources, dict):
                x_objects = resources.get("/XObject", {})
            if hasattr(x_objects, "keys"):
                image_count += len(
                    [key for key in x_objects.keys() if str(key).startswith("/Im")]
                )

        return ParsedDocument(
            text="\n\n".join(pages),
            parser="pdf",
            sections=headings,
            metadata={
                "page_count": len(reader.pages),
                "table_hints": table_hints,
                "image_count": image_count,
            },
        )


class WordParser(DocumentParser):
    """Parse DOCX, DOC, and ODT files."""

    def parse(self, file_path: str) -> ParsedDocument:
        path = Path(file_path)
        suffix = path.suffix.lower()
        if suffix == ".docx":
            with ZipFile(path, "r") as archive:
                with archive.open("word/document.xml") as xml_file:
                    xml_bytes = xml_file.read()
            root = ElementTree.fromstring(xml_bytes)
            namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
            text = " ".join(part.strip() for part in root.itertext() if part.strip())
            table_count = len(root.findall(f".//{namespace}tbl"))
            paragraph_count = len(root.findall(f".//{namespace}p"))
            return ParsedDocument(
                text=text,
                parser="word",
                metadata={
                    "format": "docx",
                    "table_count": table_count,
                    "paragraph_count": paragraph_count,
                },
            )
        if suffix == ".odt":
            text = _zip_xml_text(path, "content.xml")
            return ParsedDocument(text=text, parser="word", metadata={"format": "odt"})

        # Legacy .doc extraction via antiword if available.
        try:
            import subprocess

            completed = subprocess.run(
                ["antiword", file_path],
                check=True,
                capture_output=True,
                text=True,
            )
            return ParsedDocument(
                text=completed.stdout,
                parser="word",
                metadata={"format": "doc"},
            )
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

            workbook = load_workbook(file_path, data_only=True, read_only=False)
            sheet_names = workbook.sheetnames
            blocks: list[str] = []
            table_count = 0
            formula_cells = 0
            merged_cells = 0
            for sheet_name in sheet_names:
                sheet = workbook[sheet_name]
                rows = []
                for row in sheet.iter_rows(values_only=True):
                    values = ["" if value is None else str(value) for value in row]
                    rows.append("\t".join(values))
                table_count += max(0, len(rows) - 1)
                formula_cells += sum(
                    1
                    for row in sheet.iter_rows(values_only=False)
                    for cell in row
                    if isinstance(cell.value, str) and cell.value.startswith("=")
                )
                merged_ranges = getattr(
                    getattr(sheet, "merged_cells", None), "ranges", []
                )
                merged_cells += len(merged_ranges)
                blocks.append(f"[Worksheet: {sheet_name}]\n" + "\n".join(rows))
            return ParsedDocument(
                text="\n\n".join(blocks),
                parser="excel",
                metadata={
                    "worksheets": sheet_names,
                    "format": suffix.lstrip("."),
                    "table_count": table_count,
                    "formula_cells": formula_cells,
                    "merged_cell_ranges": merged_cells,
                },
            )

        if suffix == ".ods":
            text = _zip_xml_text(path, "content.xml")
            return ParsedDocument(text=text, parser="excel", metadata={"format": "ods"})

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
            parser="csv",
            metadata={
                "delimiter": delimiter,
                "row_count": len(rows),
                "headers": headers,
                "table_count": 1 if rows else 0,
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
                    table_count = len(
                        [node for node in slide_root.iter() if node.tag.endswith("tbl")]
                    )
                    slides.append(f"[Slide {index}]\n{text}")

            return ParsedDocument(
                text="\n\n".join(slides),
                parser="powerpoint",
                metadata={
                    "slide_count": len(slides),
                    "format": "pptx",
                    "table_count": table_count,
                },
            )

        if suffix == ".odp":
            text = _zip_xml_text(path, "content.xml")
            return ParsedDocument(
                text=text, parser="powerpoint", metadata={"format": "odp"}
            )

        # Legacy .ppt fallback
        return ParsedDocument(
            text=_read_text_file(path),
            parser="powerpoint",
            metadata={"format": "ppt", "warning": "binary_legacy_format"},
        )


class MarkdownParser(DocumentParser):
    """Parse markdown files."""

    def parse(self, file_path: str) -> ParsedDocument:
        text = _read_text_file(Path(file_path))
        headings = re.findall(r"^#{1,6}\s+(.+)$", text, flags=re.MULTILINE)
        sections = [
            {"heading": heading, "level": heading.count(".") + 1}
            for heading in headings
        ]
        return ParsedDocument(
            text=text,
            language="markdown",
            parser="markdown",
            sections=sections,
            metadata={"headings": headings},
        )


class TextParser(DocumentParser):
    """Parse generic text files."""

    def parse(self, file_path: str) -> ParsedDocument:
        return ParsedDocument(text=_read_text_file(Path(file_path)), parser="text")


class JsonParser(DocumentParser):
    """Parse JSON and JSONC files."""

    def parse(self, file_path: str) -> ParsedDocument:
        raw = _read_text_file(Path(file_path))

        try:
            payload = json.loads(raw)

        except json.JSONDecodeError:
            # Support JSONC (JSON with comments) used by tsconfig,
            # VSCode settings, etc.

            cleaned = re.sub(r"/\*.*?\*/", "", raw, flags=re.DOTALL)
            cleaned = re.sub(r"//.*?$", "", cleaned, flags=re.MULTILINE)

            try:
                payload = json.loads(cleaned)

            except json.JSONDecodeError:
                # Final fallback:
                # Treat as plain text instead of failing repository sync.
                return ParsedDocument(
                    text=raw,
                    language="json",
                    parser="text",
                    metadata={
                        "format": "json",
                        "fallback": True,
                    },
                )

        pretty = json.dumps(payload, indent=2, sort_keys=True)

        return ParsedDocument(
            text=pretty,
            language="json",
            parser="json",
            metadata={
                "root": type(payload).__name__,
            },
        )


class XmlParser(DocumentParser):
    """Parse XML files."""

    def parse(self, file_path: str) -> ParsedDocument:
        root = ElementTree.parse(file_path).getroot()
        text = "\n".join(value.strip() for value in root.itertext() if value.strip())
        return ParsedDocument(
            text=text,
            language="xml",
            parser="xml",
            metadata={"root_tag": root.tag},
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
        return ParsedDocument(
            text=raw, language="yaml", parser="yaml", metadata=metadata
        )


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
        ".bat": "batch",
    }

    def parse(self, file_path: str) -> ParsedDocument:
        path = Path(file_path)
        text = _read_text_file(path)
        language = self.LANGUAGE_BY_SUFFIX.get(path.suffix.lower(), "code")
        import_count = len(
            re.findall(
                r"^(?:from\s+\S+\s+import\s+\S+|import\s+\S+)", text, flags=re.MULTILINE
            )
        )
        class_count = len(re.findall(r"^\s*class\s+\w+", text, flags=re.MULTILINE))
        function_count = len(
            re.findall(
                r"^\s*(?:def|function|public\s+\w+\s+\w+\s*\()",
                text,
                flags=re.MULTILINE,
            )
        )
        comment_count = len(
            re.findall(r"^\s*(?:#|//|/\*|\*)", text, flags=re.MULTILINE)
        )
        return ParsedDocument(
            text=text,
            language=language,
            parser="code",
            metadata={
                "line_count": text.count("\n") + 1,
                "import_count": import_count,
                "class_count": class_count,
                "function_count": function_count,
                "comment_count": comment_count,
            },
        )


class HtmlParser(DocumentParser):
    """Parse HTML while excluding scripts and navigation noise."""

    def parse(self, file_path: str) -> ParsedDocument:
        raw = _read_text_file(Path(file_path))
        title = ""
        headings: list[str] = []
        paragraphs: list[str] = []

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(raw, "html.parser")
            for node in soup(["script", "style", "nav", "footer", "aside"]):
                node.decompose()
            title = (soup.title.string or "").strip() if soup.title else ""
            headings = [
                node.get_text(" ", strip=True)
                for node in soup.find_all(["h1", "h2", "h3", "h4"])
                if node.get_text(" ", strip=True)
            ]
            paragraphs = [
                node.get_text(" ", strip=True)
                for node in soup.find_all("p")
                if node.get_text(" ", strip=True)
            ]
        except ImportError:
            sanitized = re.sub(
                r"<script\b[^>]*>.*?</script>",
                " ",
                raw,
                flags=re.IGNORECASE | re.DOTALL,
            )
            sanitized = re.sub(
                r"<style\b[^>]*>.*?</style>",
                " ",
                sanitized,
                flags=re.IGNORECASE | re.DOTALL,
            )
            text = re.sub(r"<[^>]+>", " ", sanitized)
            paragraphs = [line.strip() for line in text.splitlines() if line.strip()]

        text_parts = [part for part in [title, *headings, *paragraphs] if part]
        return ParsedDocument(
            text="\n".join(text_parts),
            parser="html",
            sections=[{"heading": value} for value in headings],
            paragraphs=paragraphs,
            metadata={"title": title, "heading_count": len(headings)},
        )


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
        elif name in {"dockerfile", "docker-compose.yml", "docker-compose.yaml"}:
            metadata["format"] = name
        elif suffix in {".yaml", ".yml"}:
            metadata["format"] = "yaml"
        elif suffix in {".conf", ".cfg", ".properties", ".env"}:
            metadata["format"] = suffix.lstrip(".")

        return ParsedDocument(text=raw, parser="config", metadata=metadata)


class ImageParser(DocumentParser):
    """Parse image metadata and optional OCR text."""

    def __init__(self, ocr_provider: OCRProvider | None = None) -> None:
        self.ocr_provider = ocr_provider or OCRProviderFactory().create("tesseract")

    def parse(self, file_path: str) -> ParsedDocument:
        path = Path(file_path)
        metadata: dict[str, Any] = {}
        extracted_text = self.ocr_provider.extract_text(file_path)

        try:
            from PIL import Image

            with Image.open(path) as image:
                metadata["width"] = image.width
                metadata["height"] = image.height
                metadata["mode"] = image.mode
                metadata["format"] = str(image.format or "").lower()
        except ImportError:
            metadata["warning"] = "Pillow not installed"

        if not extracted_text:
            extracted_text = f"Image file: {path.name}"

        return ParsedDocument(
            text=extracted_text,
            parser="image",
            images=[{"path": path.name, **metadata}],
            metadata=metadata,
        )


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
            attachment_count = 0
            for part in message.walk():
                if part.get_content_disposition() == "attachment":
                    attachment_count += 1
            text = (
                f"Subject: {subject}\nFrom: {sender}\nTo: {recipient}\n\n{body}".strip()
            )
            return ParsedDocument(
                text=text,
                parser="email",
                metadata={
                    "subject": subject,
                    "from": sender,
                    "to": recipient,
                    "attachment_count": attachment_count,
                },
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
            parser="email",
            metadata={
                "subject": message.subject,
                "from": message.sender,
                "to": message.to,
                "attachment_count": len(getattr(message, "attachments", []) or []),
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
            parser="engineering",
            metadata={"sections": sections, "document_kind": path.suffix.lstrip(".")},
        )


class ZipParser(DocumentParser):
    """Parse ZIP archives recursively by delegating to ParserFactory resolution."""

    def __init__(self, parser_resolver: Any) -> None:
        self.parser_resolver = parser_resolver

    def parse(self, file_path: str) -> ParsedDocument:
        archive_path = Path(file_path)
        parsed_entries: list[str] = []
        total_entries = 0
        supported_entries = 0
        skipped_entries: list[str] = []

        with (
            ZipFile(archive_path, "r") as archive,
            tempfile.TemporaryDirectory() as tmp_dir,
        ):
            for member in archive.infolist():
                if member.is_dir():
                    continue
                total_entries += 1
                member_name = member.filename
                spec = detect_file_spec(member_name)
                if spec.parser == "unknown":
                    skipped_entries.append(member_name)
                    continue

                try:
                    raw = archive.read(member)
                    safe_name = Path(member_name).name or f"entry_{total_entries}"
                    temp_path = Path(tmp_dir) / safe_name
                    temp_path.write_bytes(raw)
                    parser = self.parser_resolver(member_name)
                    parsed = parser.parse(str(temp_path))
                    supported_entries += 1
                    parsed_entries.append(
                        f"[Entry: {member_name}]\n{parsed.text.strip()}"
                    )
                except Exception:  # noqa: BLE001
                    skipped_entries.append(member_name)

        text = (
            "\n\n".join(parsed_entries).strip() or f"Archive file: {archive_path.name}"
        )
        return ParsedDocument(
            text=text,
            parser="zip",
            metadata={
                "entry_count": total_entries,
                "parsed_entry_count": supported_entries,
                "skipped_entries": skipped_entries,
            },
        )
