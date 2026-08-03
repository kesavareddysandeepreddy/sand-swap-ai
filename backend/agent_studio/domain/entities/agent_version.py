"""Agent Studio agent version entity."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class AgentVersion:
    """Persisted snapshot of an agent configuration."""

    id: str = field(default_factory=lambda: str(uuid4()))
    agent_id: str = ""
    version_number: int = 1
    change_summary: str = ""
    snapshot: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
