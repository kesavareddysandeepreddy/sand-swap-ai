from __future__ import annotations

from pathlib import Path

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


def test_file_type_registry_maps_config_and_engineering() -> None:
    docker = detect_file_spec("Dockerfile")
    urs = detect_file_spec("spec.urs")

    assert docker.parser == "config"
    assert docker.category == "config"
    assert urs.parser == "engineering"
    assert urs.chunker == "engineering"


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
