"""Ollama-backed vision provider for semantic image understanding."""

from __future__ import annotations

import base64
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from backend.llm.client import OllamaClient
from backend.multimodal.image_cache import ImageCache
from backend.multimodal.models import AttachmentMetadata, VisionAnalysis
from backend.multimodal.providers.base import VisionProvider


class OllamaVisionProvider(VisionProvider):
    """Vision provider powered by local Ollama multimodal models."""

    _VISION_MODEL_HINTS = (
        "llava",
        "gemma3",
        "qwen2.5-vl",
        "qwen2-vl",
        "moondream",
        "vision",
        "vl",
    )

    def __init__(
        self,
        *,
        ollama_client: OllamaClient,
        image_cache: ImageCache,
        preferred_model: str | None = None,
    ) -> None:
        self.ollama_client = ollama_client
        self.image_cache = image_cache
        self.preferred_model = (preferred_model or "").strip()
        self._discovered_models: list[str] = []
        self._active_model: str | None = None
        self._discover_models()

    def _discover_models(self) -> None:
        """Discover local Ollama models and select a vision-capable model."""
        try:
            available_models = self.ollama_client.list_models()
        except Exception:  # noqa: BLE001
            self._discovered_models = []
            self._active_model = None
            return

        vision_models: list[str] = []
        for name in available_models:
            normalized = name.lower().strip()
            if any(hint in normalized for hint in self._VISION_MODEL_HINTS):
                vision_models.append(name)

        self._discovered_models = vision_models
        if not vision_models:
            self._active_model = None
            return

        if self.preferred_model:
            preferred_normalized = self.preferred_model.lower()
            for candidate in vision_models:
                if candidate.lower() == preferred_normalized:
                    self._active_model = candidate
                    return

        self._active_model = vision_models[0]

    def _cache_key(self, image_bytes: bytes) -> str:
        digest = hashlib.sha256(image_bytes).hexdigest()
        active_model = self._active_model or "unknown"
        return f"vision:{active_model}:{digest}"

    def _vision_prompt(self) -> str:
        return (
            "Describe this image in detail. "
            "Identify scene, objects, visible_text, people, activities, and important_observations. "
            "Return concise structured JSON with keys: "
            "summary, description, objects, visible_text, people, activities, "
            "important_observations, confidence."
        )

    def _coerce_analysis(self, payload: Any, elapsed: float) -> VisionAnalysis:
        if not isinstance(payload, dict):
            payload = {}

        objects = payload.get("objects", [])
        if not isinstance(objects, list):
            objects = []

        confidence_value = payload.get("confidence", 0.0)
        try:
            confidence = float(confidence_value)
        except (TypeError, ValueError):
            confidence = 0.0

        return VisionAnalysis(
            summary=str(payload.get("summary", "")).strip(),
            description=str(payload.get("description", "")).strip(),
            objects=[str(item) for item in objects if isinstance(item, str)],
            ocr_text="",
            confidence=confidence,
            provider="ollama_vision",
            processing_time=elapsed,
            raw_response=payload,
            metadata={
                "scene": payload.get("scene", ""),
                "visible_text": payload.get("visible_text", ""),
                "people": payload.get("people", []),
                "activities": payload.get("activities", []),
                "important_observations": payload.get("important_observations", []),
                "model": self._active_model or "",
                "cache_hit": False,
            },
        )

    def is_available(self) -> bool:
        return self._active_model is not None

    def analyze_image(
        self,
        image_path: str,
        metadata: AttachmentMetadata | None = None,
    ) -> VisionAnalysis:
        _ = metadata
        if self._active_model is None:
            raise RuntimeError("No vision-capable Ollama model is available.")

        path = Path(image_path)
        image_bytes = path.read_bytes()
        cache_key = self._cache_key(image_bytes)

        if self.image_cache.exists(cache_key):
            cached = self.image_cache.load(cache_key)
            if isinstance(cached, VisionAnalysis):
                cached.metadata = {**cached.metadata, "cache_hit": True}
                return cached
            if isinstance(cached, dict):
                return VisionAnalysis(
                    summary=str(cached.get("summary", "")),
                    description=str(cached.get("description", "")),
                    objects=[
                        str(item)
                        for item in cached.get("objects", [])
                        if isinstance(item, str)
                    ],
                    ocr_text=str(cached.get("ocr_text", "")),
                    confidence=float(cached.get("confidence", 0.0)),
                    provider=str(cached.get("provider", "ollama_vision")),
                    processing_time=float(cached.get("processing_time", 0.0)),
                    raw_response=cached.get("raw_response", {}),
                    metadata={
                        **(
                            cached.get("metadata", {})
                            if isinstance(cached.get("metadata", {}), dict)
                            else {}
                        ),
                        "cache_hit": True,
                    },
                )

        started_at = time.perf_counter()
        encoded_image = base64.b64encode(image_bytes).decode("ascii")
        response = self.ollama_client.generate(
            prompt=self._vision_prompt(),
            model=self._active_model,
            temperature=0.1,
            format_json=True,
            images=[encoded_image],
        )
        elapsed = time.perf_counter() - started_at

        payload = response
        if isinstance(response, str):
            try:
                payload = json.loads(response)
            except json.JSONDecodeError:
                payload = {}

        analysis = self._coerce_analysis(payload, elapsed)
        self.image_cache.save(cache_key, analysis, image_size=len(image_bytes))
        return analysis

    def health(self) -> dict[str, Any]:
        return {
            "status": "available" if self.is_available() else "unavailable",
            "provider": "ollama_vision",
            "model_name": self._active_model,
            "discovered_models": list(self._discovered_models),
            "capabilities": {
                "semantic_image_understanding": self.is_available(),
                "ocr": False,
            },
        }
