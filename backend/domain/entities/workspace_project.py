"""Project entity nested inside a workspace boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(slots=True)
class WorkspaceProject:
    """Represents a project owned by a user within a workspace."""

    id: str
    workspace_id: str
    owner_id: str
    name: str
    description: str
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        project_id: str,
        workspace_id: str,
        owner_id: str,
        name: str,
        description: str,
    ) -> "WorkspaceProject":
        """Build a new workspace project with initialized timestamps."""
        return cls(
            id=project_id,
            workspace_id=workspace_id,
            owner_id=owner_id,
            name=name,
            description=description,
            created_at=datetime.now(UTC),
        )
