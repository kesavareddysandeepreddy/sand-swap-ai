"""
SandSwap AI - Ollama Client
"""

from __future__ import annotations

import json
from typing import Any

import requests


class OllamaClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "llama3",
        timeout: int = 120,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system: str = "",
        temperature: float = 0.2,
        stream: bool = False,
        format_json: bool = False,
    ) -> Any:
        requested_model = (model or "").strip() or self.model
        payload = {
            "model": requested_model,
            "prompt": prompt,
            "system": system,
            "stream": stream,
            "options": {"temperature": temperature},
        }

        if format_json:
            payload["format"] = "json"

        response = requests.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()

        if stream:
            return response.iter_lines()

        data = response.json()
        text = data.get("response", "")

        if format_json:
            return json.loads(text)

        return text

    def list_models(self) -> list[str]:
        response = requests.get(
            f"{self.base_url}/api/tags",
            timeout=self.timeout,
        )
        response.raise_for_status()
        return [m["name"] for m in response.json().get("models", [])]
