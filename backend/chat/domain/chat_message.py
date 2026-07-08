"""Chat message domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class ChatMessage:
    """Represents a single chat turn."""

    role: str
    content: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict[str, Any]:
        """Serialize the message for storage or transport."""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
        }
