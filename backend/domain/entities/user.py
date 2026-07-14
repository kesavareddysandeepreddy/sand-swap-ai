"""User ownership domain entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(slots=True)
class User:
    """Represents a workspace user for enterprise ownership boundaries."""

    id: str
    email: str
    display_name: str
    google_subject_id: str | None
    avatar_url: str | None
    auth_provider: str
    active_workspace_id: str | None
    active_project_id: str | None
    created_at: datetime
    updated_at: datetime
    is_active: bool = True

    @classmethod
    def create(
        cls,
        *,
        user_id: str,
        email: str,
        display_name: str,
        google_subject_id: str | None = None,
        avatar_url: str | None = None,
        auth_provider: str = "local",
        active_workspace_id: str | None = None,
        active_project_id: str | None = None,
        is_active: bool = True,
    ) -> "User":
        """Build a new active user with initialized timestamps."""
        now = datetime.now(UTC)
        return cls(
            id=user_id,
            email=email,
            display_name=display_name,
            google_subject_id=google_subject_id,
            avatar_url=avatar_url,
            auth_provider=auth_provider,
            active_workspace_id=active_workspace_id,
            active_project_id=active_project_id,
            created_at=now,
            updated_at=now,
            is_active=is_active,
        )

    def touch(self) -> None:
        """Refresh the update timestamp after a domain change."""
        self.updated_at = datetime.now(UTC)
