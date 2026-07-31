"""Concrete tool execution helpers."""

from __future__ import annotations

import time
from typing import Any

from backend.tool_execution.resolver import ToolResolution
from backend.tool_execution.result import ToolExecutionResult
from backend.tool_sdk.context import ToolContext


class ToolExecutor:
    """Execute resolved tools and normalize their outputs."""

    @staticmethod
    def _tool_health_status(tool: Any) -> str:
        health = getattr(tool, "health", None)
        if not callable(health):
            return "ok"
        payload = health()
        if isinstance(payload, dict):
            return str(payload.get("status", "ok")).lower()
        return "ok"

    @staticmethod
    def _is_healthy(tool: Any) -> bool:
        return ToolExecutor._tool_health_status(tool) in {"ok", "healthy", "ready"}

    @staticmethod
    def _normalize_artifacts(payload: Any) -> list[dict[str, Any]]:
        artifacts: list[dict[str, Any]] = []
        if isinstance(payload, dict):
            files = payload.get("generated_files")
            if isinstance(files, list):
                for item in files:
                    if isinstance(item, dict):
                        artifacts.append(dict(item))
                    else:
                        artifacts.append({"path": str(item)})

            if payload.get("artifact") is not None:
                artifacts.append({"value": payload["artifact"]})

        return artifacts

    @staticmethod
    def _payload_to_text(
        payload: Any,
    ) -> tuple[str, str, bool, list[dict[str, Any]], dict[str, Any], str | None]:
        if isinstance(payload, dict):
            stdout = str(payload.get("stdout", ""))
            stderr = str(payload.get("stderr", ""))
            success = bool(payload.get("success", True))
            artifacts = ToolExecutor._normalize_artifacts(payload)
            metadata = {
                key: value
                for key, value in payload.items()
                if key not in {"stdout", "stderr", "success", "generated_files"}
            }
            error = (
                str(payload.get("error")) if payload.get("error") is not None else None
            )
            return stdout, stderr, success, artifacts, metadata, error

        return str(payload), "", True, [], {}, None

    def execute(
        self,
        *,
        resolution: ToolResolution,
        context: ToolContext | dict[str, Any],
        payload: ToolContext | dict[str, Any],
        step_id: str,
    ) -> ToolExecutionResult:
        started = time.perf_counter()
        tool = resolution.tool

        if not self._is_healthy(tool):
            return ToolExecutionResult(
                tool_name=resolution.tool_name,
                step_id=step_id,
                success=False,
                stderr=f"Tool unhealthy: {resolution.tool_name}",
                duration_ms=round((time.perf_counter() - started) * 1000, 3),
                error="unhealthy",
            )

        try:
            if hasattr(tool, "call_tool") and resolution.tool_name == "MCP":
                server_name = str(payload.get("server_name", "")).strip()
                tool_name = str(payload.get("mcp_tool", "")).strip()
                arguments = payload.get("arguments")
                response = tool.call_tool(
                    server_name=server_name,
                    tool_name=tool_name,
                    arguments=arguments if isinstance(arguments, dict) else None,
                )
                stdout = ""
                stderr = response.error or ""
                success = not response.is_error
                artifacts: list[dict[str, Any]] = []
                metadata = {
                    "server_name": response.server_name,
                    "tool_name": response.tool_name,
                    "content": response.content,
                    "latency_ms": response.latency_ms,
                }
                error = response.error
            else:
                output = tool.execute(payload)
                stdout, stderr, success, artifacts, metadata, error = (
                    self._payload_to_text(output)
                )

            duration_ms = round((time.perf_counter() - started) * 1000, 3)
            metadata.setdefault("resolution_source", resolution.source)
            metadata.setdefault("capability", resolution.capability)
            return ToolExecutionResult(
                tool_name=resolution.tool_name,
                step_id=step_id,
                success=success,
                stdout=stdout,
                stderr=stderr,
                artifacts=artifacts,
                metadata=metadata,
                duration_ms=duration_ms,
                error=error,
            )
        except Exception as exc:  # noqa: BLE001
            duration_ms = round((time.perf_counter() - started) * 1000, 3)
            return ToolExecutionResult(
                tool_name=resolution.tool_name,
                step_id=step_id,
                success=False,
                stderr=str(exc),
                duration_ms=duration_ms,
                error=str(exc),
            )
