"""Agent Studio test run entity."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class AgentTestRun:
    """Persisted test run for an agent prompt execution."""

    id: str = field(default_factory=lambda: str(uuid4()))
    agent_id: str = ""
    prompt: str = ""
    reasoning: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    execution: list[dict[str, Any]] = field(default_factory=list)
    final_answer: str = ""
    success: bool = False
    error: str | None = None
    timing_ms: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
