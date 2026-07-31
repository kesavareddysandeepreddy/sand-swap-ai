"""Structured tool execution result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ToolExecutionResult:
    """Structured outcome for one tool invocation."""

    tool_name: str
    step_id: str
    success: bool
    stdout: str = ""
    stderr: str = ""
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    error: str | None = None

    def as_metadata(self) -> dict[str, Any]:
        """Serialize the result for workflow and trace metadata."""
        return {
            "tool_name": self.tool_name,
            "step_id": self.step_id,
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "artifacts": list(self.artifacts),
            "metadata": dict(self.metadata),
            "duration_ms": self.duration_ms,
            "error": self.error,
            "stdout_length": len(self.stdout),
            "generated_files": [
                artifact
                for artifact in self.artifacts
                if isinstance(artifact, dict) and "path" in artifact
            ],
        }
