"""Provider registry for multimodal backends."""

from __future__ import annotations

from typing import Any

from backend.multimodal.providers.base import OCRProvider, VisionProvider


class ProviderRegistry:
    """Register and resolve multimodal providers using dependency injection."""

    def __init__(
        self,
        *,
        vision_provider_name: str | None = None,
        ocr_provider_name: str | None = None,
    ) -> None:
        self._vision_providers: dict[str, VisionProvider] = {}
        self._ocr_providers: dict[str, OCRProvider] = {}
        self._capabilities: dict[str, dict[str, Any]] = {"vision": {}, "ocr": {}}
        self._active_vision_provider_name = (vision_provider_name or "").strip()
        self._active_ocr_provider_name = (ocr_provider_name or "").strip()

    def register_provider(
        self, name: str, provider: VisionProvider | OCRProvider
    ) -> None:
        """Register a provider instance under a logical name."""
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Provider name cannot be empty.")

        if isinstance(provider, VisionProvider):
            self._vision_providers[normalized_name] = provider
            self._capabilities["vision"][normalized_name] = provider.health()
            return
        if isinstance(provider, OCRProvider):
            self._ocr_providers[normalized_name] = provider
            self._capabilities["ocr"][normalized_name] = provider.health()
            return
        raise TypeError("Provider must implement VisionProvider or OCRProvider.")

    def discover_providers(self) -> dict[str, list[str]]:
        """Return discovered provider names by capability."""
        return {
            "vision": sorted(self._vision_providers.keys()),
            "ocr": sorted(self._ocr_providers.keys()),
            "capabilities": {
                "vision": dict(self._capabilities["vision"]),
                "ocr": dict(self._capabilities["ocr"]),
            },
        }

    def set_active_provider(self, provider_type: str, name: str) -> None:
        """Set active provider name for a provider category."""
        normalized_name = name.strip()
        normalized_type = provider_type.strip().lower()

        if normalized_type == "vision":
            self._active_vision_provider_name = normalized_name
            return
        if normalized_type == "ocr":
            self._active_ocr_provider_name = normalized_name
            return
        raise ValueError(f"Unsupported provider type: {provider_type}")

    def get_active_vision_provider(self) -> VisionProvider | None:
        """Return the active vision provider when available."""
        if not self._active_vision_provider_name:
            return None
        provider = self._vision_providers.get(self._active_vision_provider_name)
        if provider is None or not provider.is_available():
            return None
        return provider

    def get_active_ocr_provider(self) -> OCRProvider | None:
        """Return the active OCR provider when available."""
        if not self._active_ocr_provider_name:
            return None
        return self._ocr_providers.get(self._active_ocr_provider_name)

    def health(self) -> dict[str, dict[str, Any]]:
        """Return health details for all registered providers."""
        vision_health = {
            name: provider.health() for name, provider in self._vision_providers.items()
        }
        ocr_health = {
            name: provider.health() for name, provider in self._ocr_providers.items()
        }
        self._capabilities["vision"] = vision_health
        self._capabilities["ocr"] = ocr_health
        return {"vision": vision_health, "ocr": ocr_health}

    def get_capabilities(self) -> dict[str, dict[str, Any]]:
        """Return stored provider capabilities."""
        return {
            "vision": dict(self._capabilities["vision"]),
            "ocr": dict(self._capabilities["ocr"]),
        }
