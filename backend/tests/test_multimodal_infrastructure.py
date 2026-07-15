from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.api.dependencies import register_runtime_dependencies
from backend.config.config_manager import ConfigManager
from backend.core.container.container import Container
from backend.multimodal.attachment_router import AttachmentRouter
from backend.multimodal.attachment_types import AttachmentType
from backend.multimodal.image_cache import InMemoryImageCache
from backend.multimodal.models import AttachmentMetadata, OCRAnalysis, VisionAnalysis
from backend.multimodal.multimodal_context import AttachmentContextBuilder
from backend.multimodal.providers.base import OCRProvider, VisionProvider
from backend.multimodal.providers.ollama_vision_provider import OllamaVisionProvider
from backend.multimodal.providers.registry import ProviderRegistry


class FakeVisionProvider(VisionProvider):
    def is_available(self) -> bool:
        return True

    def analyze_image(
        self,
        image_path: str,
        metadata: AttachmentMetadata | None = None,
    ) -> VisionAnalysis:
        _ = (image_path, metadata)
        return VisionAnalysis(
            provider="fake_vision",
            summary="Indoor desk setup",
            description="A laptop on a desk with a cup of coffee.",
            objects=["laptop", "desk", "coffee cup"],
            ocr_text="",
            confidence=0.88,
            raw_response={"visible_text": "none"},
            metadata={"visible_text": "none"},
        )

    def health(self) -> dict[str, Any]:
        return {"status": "ok"}


class FakeOCRProvider(OCRProvider):
    def extract_text(
        self,
        image_bytes: bytes,
        metadata: AttachmentMetadata,
    ) -> OCRAnalysis:
        _ = (image_bytes, metadata)
        return OCRAnalysis(provider="fake_ocr", ocr_text="hello")

    def health(self) -> dict[str, Any]:
        return {"status": "ok"}


@pytest.mark.parametrize(
    ("filename", "mime_type", "expected"),
    [
        ("image.png", "image/png", AttachmentType.IMAGE),
        ("paper.pdf", "application/pdf", AttachmentType.PDF),
        (
            "proposal.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            AttachmentType.WORD,
        ),
        (
            "sheet.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            AttachmentType.EXCEL,
        ),
        (
            "deck.pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            AttachmentType.POWERPOINT,
        ),
        ("notes.txt", "text/plain", AttachmentType.TEXT),
        ("records.csv", "text/csv", AttachmentType.CSV),
        ("archive.bin", "application/octet-stream", AttachmentType.UNKNOWN),
    ],
)
def test_attachment_router_classifies_supported_types(
    filename: str,
    mime_type: str,
    expected: AttachmentType,
) -> None:
    router = AttachmentRouter()
    assert (
        router.classify_attachment(filename=filename, mime_type=mime_type) == expected
    )


def test_attachment_router_detects_mime_type() -> None:
    router = AttachmentRouter()
    assert router.detect_mime_type(filename="report.pdf") == "application/pdf"


def test_attachment_router_prefers_explicit_mime_type() -> None:
    router = AttachmentRouter()
    assert (
        router.detect_mime_type(
            filename="report.unknown",
            provided_mime_type="text/plain",
        )
        == "text/plain"
    )


def test_provider_registry_registers_and_discovers_providers() -> None:
    registry = ProviderRegistry(vision_provider_name="vision", ocr_provider_name="ocr")
    registry.register_provider("vision", FakeVisionProvider())
    registry.register_provider("ocr", FakeOCRProvider())

    discovered = registry.discover_providers()

    assert discovered["vision"] == ["vision"]
    assert discovered["ocr"] == ["ocr"]
    assert "vision" in discovered["capabilities"]
    assert isinstance(registry.get_active_vision_provider(), FakeVisionProvider)
    assert isinstance(registry.get_active_ocr_provider(), FakeOCRProvider)


def test_provider_registry_returns_none_for_missing_active_provider() -> None:
    registry = ProviderRegistry(vision_provider_name="missing")
    assert registry.get_active_vision_provider() is None


def test_provider_registry_rejects_invalid_provider_type() -> None:
    registry = ProviderRegistry()
    with pytest.raises(TypeError):
        registry.register_provider("invalid", object())  # type: ignore[arg-type]


def test_config_manager_loads_multimodal_configuration() -> None:
    config = ConfigManager()
    assert config.get("multimodal.vision_provider") == "none"
    assert config.get("multimodal.ocr_provider") == "none"
    assert config.get("multimodal.cache_enabled") is True
    assert config.get("multimodal.max_image_size") == 10485760
    assert config.get("multimodal.supported_types") == [
        "image",
        "pdf",
        "word",
        "excel",
        "powerpoint",
        "text",
        "csv",
    ]


def test_attachment_context_builder_generates_structured_image_context(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "chart.png"
    image_path.write_bytes(b"fake-png-bytes")

    router = AttachmentRouter()
    registry = ProviderRegistry(vision_provider_name="vision")
    registry.register_provider("vision", FakeVisionProvider())
    cache = InMemoryImageCache()
    builder = AttachmentContextBuilder(
        attachment_router=router,
        provider_registry=registry,
        image_cache=cache,
        supported_types=["image"],
    )

    context = builder.build_context(
        attachments=[
            AttachmentMetadata(
                filename="chart.png",
                mime_type="image/png",
                extension=".png",
                size=123,
                metadata={"path": str(image_path)},
            )
        ]
    )

    assert len(context.attachments) == 1
    assert len(context.analyses) == 1
    assert "Attached Image" in context.summary
    assert "Filename: chart.png" in context.summary
    assert "Objects: laptop, desk, coffee cup" in context.summary
    assert "Provider: fake_vision" in context.summary
    assert context.metadata["status"] == "enabled"


def test_attachment_context_builder_falls_back_when_provider_unavailable(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "fallback.png"
    image_path.write_bytes(b"fake-png-bytes")

    router = AttachmentRouter()
    registry = ProviderRegistry(vision_provider_name="missing")
    cache = InMemoryImageCache()
    builder = AttachmentContextBuilder(
        attachment_router=router,
        provider_registry=registry,
        image_cache=cache,
        supported_types=["image"],
    )

    context = builder.build_context(
        attachments=[
            AttachmentMetadata(
                filename="fallback.png",
                mime_type="image/png",
                extension=".png",
                size=123,
                metadata={"path": str(image_path)},
            )
        ]
    )

    assert context.summary == "No attachments"
    assert context.metadata["reason"] == "vision_provider_unavailable"


class MockOllamaClient:
    def __init__(
        self, models: list[str], response: dict[str, Any] | None = None
    ) -> None:
        self._models = models
        self._response = response or {}
        self.generate = MagicMock(return_value=self._response)

    def list_models(self) -> list[str]:
        return list(self._models)


def test_ollama_vision_provider_discovers_supported_model() -> None:
    client = MockOllamaClient(models=["llama3:latest", "llava:latest"])  # type: ignore[arg-type]
    cache = InMemoryImageCache()
    provider = OllamaVisionProvider(ollama_client=client, image_cache=cache)

    assert provider.is_available() is True
    health = provider.health()
    assert health["status"] == "available"
    assert health["model_name"] == "llava:latest"


def test_ollama_vision_provider_is_unavailable_without_vision_model() -> None:
    client = MockOllamaClient(models=["llama3:latest"])  # type: ignore[arg-type]
    cache = InMemoryImageCache()
    provider = OllamaVisionProvider(ollama_client=client, image_cache=cache)

    assert provider.is_available() is False
    assert provider.health()["status"] == "unavailable"


def test_ollama_vision_provider_cache_miss_and_analysis(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "scene.png"
    image_path.write_bytes(b"scene-image-bytes")

    client = MockOllamaClient(
        models=["llava:latest"],
        response={
            "summary": "City street at sunset",
            "description": "A busy street scene with cars and pedestrians.",
            "objects": ["cars", "pedestrians", "buildings"],
            "visible_text": "Main St",
            "confidence": 0.91,
        },
    )  # type: ignore[arg-type]
    cache = InMemoryImageCache()
    provider = OllamaVisionProvider(ollama_client=client, image_cache=cache)

    analysis = provider.analyze_image(str(image_path))

    assert analysis.summary == "City street at sunset"
    assert analysis.description.startswith("A busy street scene")
    assert analysis.objects == ["cars", "pedestrians", "buildings"]
    assert analysis.ocr_text == ""
    assert analysis.provider == "ollama_vision"
    assert isinstance(analysis.processing_time, float)
    assert analysis.raw_response["visible_text"] == "Main St"
    assert analysis.metadata["cache_hit"] is False
    assert client.generate.call_count == 1


def test_ollama_vision_provider_cache_hit_reuses_previous_result(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "cached.png"
    image_path.write_bytes(b"cached-image-bytes")

    client = MockOllamaClient(
        models=["llava:latest"],
        response={
            "summary": "Desk scene",
            "description": "Desk with notebook and pen.",
            "objects": ["desk", "notebook", "pen"],
            "confidence": 0.85,
        },
    )  # type: ignore[arg-type]
    cache = InMemoryImageCache()
    provider = OllamaVisionProvider(ollama_client=client, image_cache=cache)

    first = provider.analyze_image(str(image_path))
    second = provider.analyze_image(str(image_path))

    assert first.summary == "Desk scene"
    assert second.summary == "Desk scene"
    assert second.metadata["cache_hit"] is True
    assert client.generate.call_count == 1


def test_in_memory_image_cache_save_load_exists_invalidate() -> None:
    cache = InMemoryImageCache()

    assert cache.exists("k1") is False
    cache.save("k1", {"value": 1}, image_size=1024)
    assert cache.exists("k1") is True
    assert cache.load("k1") == {"value": 1}

    cache.invalidate("k1")
    assert cache.exists("k1") is False
    assert cache.load("k1") is None


def test_in_memory_image_cache_honors_limits_and_enabled_flag() -> None:
    cache = InMemoryImageCache(enabled=True, max_image_size=100)
    cache.save("too-big", {"value": 1}, image_size=101)
    assert cache.exists("too-big") is False

    disabled_cache = InMemoryImageCache(enabled=False)
    disabled_cache.save("k2", {"value": 2}, image_size=10)
    assert disabled_cache.exists("k2") is False
    assert disabled_cache.load("k2") is None


def test_runtime_registers_multimodal_dependencies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "memory.db"))
    monkeypatch.setenv("RAG_DB_PATH", str(tmp_path / "rag.db"))
    monkeypatch.setenv("ENTERPRISE_DB_PATH", str(tmp_path / "enterprise.db"))

    container = Container()
    container.clear()
    register_runtime_dependencies(container)

    assert container.exists("attachment_router") is True
    assert container.exists("multimodal_provider_registry") is True
    assert container.exists("attachment_context_builder") is True
    assert container.exists("multimodal_pipeline") is True
    assert container.exists("image_cache") is True
    assert container.exists("knowledge_service") is True
    assert container.exists("knowledge_repository") is True
    assert container.exists("knowledge_registry") is True
    assert container.exists("knowledge_context_builder") is True
    assert container.exists("tool_router") is True
    assert container.exists("planner_agent") is True
    assert container.exists("agent_registry") is True
    assert container.exists("general_chat_agent") is True
    assert container.exists("workflow_registry") is True
    assert container.exists("workflow_queue") is True
    assert container.exists("workflow_executor") is True
    assert container.exists("workflow_engine") is True
    assert container.exists("mcp_registry") is True
    assert container.exists("mcp_capability_discovery") is True
    assert container.exists("mcp_discovery_service") is True
    assert container.exists("mcp_session_manager") is True
    assert container.exists("mcp_client") is True
    assert container.exists("agent_runtime") is True


def test_runtime_gracefully_handles_missing_vision_models(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "memory.db"))
    monkeypatch.setenv("RAG_DB_PATH", str(tmp_path / "rag.db"))
    monkeypatch.setenv("ENTERPRISE_DB_PATH", str(tmp_path / "enterprise.db"))

    from backend.llm.client import OllamaClient

    monkeypatch.setattr(OllamaClient, "list_models", lambda _self: ["llama3:latest"])

    container = Container()
    container.clear()
    register_runtime_dependencies(container)

    registry = container.resolve("multimodal_provider_registry")
    assert isinstance(registry, ProviderRegistry)
    assert registry.get_active_vision_provider() is None
