from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from backend.rag.chunkers.factory import ChunkerFactory
from backend.rag.domain.models import DocumentRecord, ParsedDocument
from backend.rag.parsers.factory import ParserFactory
from backend.rag.parsers.file_types import detect_file_spec


def _document(name: str, file_type: str) -> DocumentRecord:
    return DocumentRecord(
        id="doc-1",
        name=name,
        original_filename=name,
        stored_path=f"/tmp/{name}",
        file_type=file_type,
        size_bytes=128,
        sha256="abc",
        metadata={"project": "sand-swap", "tags": ["unit"]},
    )


def test_parser_factory_routes_supported_extensions() -> None:
    factory = ParserFactory()

    assert factory.resolve("guide.pdf").__class__.__name__ == "PDFParser"
    assert factory.resolve("readme.md").__class__.__name__ == "MarkdownParser"
    assert factory.resolve("deploy.yaml").__class__.__name__ == "YamlParser"
    assert factory.resolve("main.py").__class__.__name__ == "CodeParser"
    assert factory.resolve("mail.eml").__class__.__name__ == "EmailParser"
    assert factory.resolve("web.html").__class__.__name__ == "HtmlParser"
    assert factory.resolve("archive.zip").__class__.__name__ == "ZipParser"


def test_file_type_registry_maps_config_and_engineering() -> None:
    docker = detect_file_spec("Dockerfile")
    urs = detect_file_spec("spec.urs")
    zip_file = detect_file_spec("bundle.zip")
    image = detect_file_spec("diagram.webp")
    batch = detect_file_spec("deploy.bat")

    assert docker.parser == "config"
    assert docker.category == "config"
    assert urs.parser == "engineering"
    assert urs.chunker == "engineering"
    assert zip_file.parser == "zip"
    assert image.parser == "image"
    assert batch.parser == "code"


def test_markdown_chunker_uses_header_sections() -> None:
    chunker = ChunkerFactory().resolve("notes.md")
    document = _document("notes.md", "md")
    parsed = ParsedDocument(
        text="# Intro\nLine one\n\n## Details\nLine two\nLine three",
        language="markdown",
    )

    chunks = chunker.chunk(document=document, parsed=parsed, chunk_size=2, overlap=0)

    assert len(chunks) >= 2
    assert any(chunk.metadata.get("section") == "Intro" for chunk in chunks)
    assert any(chunk.metadata.get("section") == "Details" for chunk in chunks)


def test_code_chunker_emits_function_and_class_metadata() -> None:
    chunker = ChunkerFactory().resolve("main.py")
    document = _document("main.py", "python")
    parsed = ParsedDocument(
        text="import os\n\nclass Service:\n    pass\n\ndef build():\n    return Service()",
        language="python",
    )

    chunks = chunker.chunk(document=document, parsed=parsed, chunk_size=6, overlap=1)

    assert chunks
    assert any(chunk.metadata.get("section") == "import" for chunk in chunks)
    assert any(chunk.metadata.get("section") == "class" for chunk in chunks)
    assert any(chunk.metadata.get("section") == "function" for chunk in chunks)


def test_text_parser_reads_plain_file(tmp_path: Path) -> None:
    file_path = tmp_path / "notes.txt"
    file_path.write_text("alpha\nbeta\ngamma", encoding="utf-8")

    parser = ParserFactory().resolve(file_path.name)
    parsed = parser.parse(str(file_path))

    assert "alpha" in parsed.text
    assert "gamma" in parsed.text


def test_html_parser_removes_script_and_keeps_content(tmp_path: Path) -> None:
    html_file = tmp_path / "portal.html"
    html_file.write_text(
        """
        <html>
          <head><title>Portal</title><script>console.log('x')</script></head>
          <body><nav>Ignore nav</nav><h1>Overview</h1><p>Important body text</p></body>
        </html>
        """,
        encoding="utf-8",
    )

    parser = ParserFactory().resolve(html_file.name)
    parsed = parser.parse(str(html_file))

    assert "Important body text" in parsed.text
    assert "console.log" not in parsed.text
    assert parsed.parser == "html"


def test_zip_parser_recursively_extracts_supported_entries(tmp_path: Path) -> None:
    archive_path = tmp_path / "bundle.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("notes.txt", "alpha beta gamma")
        archive.writestr("info.md", "# Header\n\nUseful markdown")
        archive.writestr("binary.bin", b"\x00\x01\x02")

    parser = ParserFactory().resolve(archive_path.name)
    parsed = parser.parse(str(archive_path))

    assert "[Entry: notes.txt]" in parsed.text
    assert "alpha beta gamma" in parsed.text
    assert parsed.metadata["entry_count"] == 3
    assert parsed.metadata["parsed_entry_count"] >= 2


def test_image_parser_falls_back_when_ocr_unavailable(tmp_path: Path) -> None:
    image_file = tmp_path / "chart.png"

    try:
        from PIL import Image
    except ImportError:
        return

    image = Image.new("RGB", (32, 32), "white")
    image.save(image_file)

    parser = ParserFactory(ocr_provider="none").resolve(image_file.name)
    parsed = parser.parse(str(image_file))

    assert "Image file" in parsed.text
    assert parsed.metadata.get("width") == 32
