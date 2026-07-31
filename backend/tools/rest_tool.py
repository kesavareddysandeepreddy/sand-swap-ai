"""REST execution tool for safe HTTP fetch/download within workspace roots."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from backend.tool_sdk.base_tool import BaseTool
from backend.tool_sdk.context import ToolContext
from backend.tool_sdk.decorator import tool


@tool(
    name="RESTTool",
    description="REST placeholder plugin.",
    capabilities=["rest"],
    priority=100,
)
class RESTTool(BaseTool):
    """REST tool implementation for controlled downloads and JSON fetches."""

    _DEFAULT_TIMEOUT_SECONDS = 30.0

    def name(self) -> str:
        return "RESTTool"

    def description(self) -> str:
        return "Safe HTTP fetch and download tool within configured workspace roots."

    def capabilities(self) -> list[str]:
        return ["rest"]

    @staticmethod
    def _get_value(
        context: ToolContext | dict[str, Any], key: str, default: Any = None
    ) -> Any:
        return context.get(key, default)

    @staticmethod
    def _workspace_root(context: ToolContext | dict[str, Any]) -> Path:
        raw_root = (
            context.get("workspace_root") or os.getenv("WORKSPACE_ROOT") or Path.cwd()
        )
        return Path(str(raw_root)).expanduser().resolve(strict=False)

    @staticmethod
    def _ensure_within_workspace(path: Path, workspace_root: Path) -> None:
        try:
            path.resolve(strict=False).relative_to(workspace_root)
        except ValueError as exc:
            raise ValueError(f"Path outside allowed workspace: {path}") from exc

    def validate(self, context: ToolContext | dict[str, Any] | None = None) -> bool:
        payload = context or {}
        url = str(payload.get("url", "")).strip()
        if not url:
            raise ValueError("url is required.")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be a valid http(s) URL.")

        output_path = payload.get("output_path")
        if output_path:
            workspace_root = self._workspace_root(payload)
            candidate = Path(str(output_path)).expanduser()
            if not candidate.is_absolute():
                candidate = workspace_root / candidate
            self._ensure_within_workspace(candidate, workspace_root)
        return True

    def execute(self, context: ToolContext | dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            self.validate(context)
            url = str(self._get_value(context, "url", "")).strip()
            method = str(self._get_value(context, "method", "GET")).upper()
            timeout_seconds = float(
                self._get_value(
                    context, "timeout_seconds", self._DEFAULT_TIMEOUT_SECONDS
                )
            )
            output_path = self._get_value(context, "output_path")
            expect_json = bool(self._get_value(context, "expect_json", False))
            workspace_root = self._workspace_root(context)

            response = requests.request(method, url, timeout=timeout_seconds)
            response.raise_for_status()

            body_text = response.text
            parsed_json: Any = None
            if expect_json:
                parsed_json = response.json()

            generated_files: list[dict[str, Any]] = []
            if output_path:
                candidate = Path(str(output_path)).expanduser()
                if not candidate.is_absolute():
                    candidate = workspace_root / candidate
                self._ensure_within_workspace(candidate, workspace_root)
                candidate.parent.mkdir(parents=True, exist_ok=True)
                candidate.write_text(body_text, encoding="utf-8")
                generated_files.append(
                    {
                        "path": str(candidate.relative_to(workspace_root)),
                        "absolute_path": str(candidate),
                        "exists": True,
                        "size_bytes": candidate.stat().st_size,
                    }
                )

            execution_time = round((time.perf_counter() - started) * 1000, 3)
            payload = {
                "success": True,
                "stdout": (
                    json.dumps(parsed_json, indent=2)
                    if parsed_json is not None
                    else body_text
                ),
                "stderr": "",
                "generated_files": generated_files,
                "execution_time": execution_time,
                "metadata": {
                    "status_code": response.status_code,
                    "content_type": response.headers.get("content-type", ""),
                    "url": url,
                    "method": method,
                },
            }
            return payload
        except Exception as exc:  # noqa: BLE001
            execution_time = round((time.perf_counter() - started) * 1000, 3)
            return {
                "success": False,
                "stdout": "",
                "stderr": str(exc),
                "generated_files": [],
                "execution_time": execution_time,
                "error": str(exc),
            }
