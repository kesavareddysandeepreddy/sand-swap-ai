"""Project ownership domain entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(slots=True)
class Project:
    """Represents a user-owned project boundary."""

    id: str
    owner_id: str
    name: str
    description: str
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        project_id: str,
        owner_id: str,
        name: str,
        description: str,
    ) -> "Project":
        """Build a new project with an initialized creation timestamp."""
        return cls(
            id=project_id,
            owner_id=owner_id,
            name=name,
            description=description,
            created_at=datetime.now(UTC),
        )
