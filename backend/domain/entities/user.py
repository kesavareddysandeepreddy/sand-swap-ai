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
        is_active: bool = True,
    ) -> "User":
        """Build a new active user with initialized timestamps."""
        now = datetime.now(UTC)
        return cls(
            id=user_id,
            email=email,
            display_name=display_name,
            created_at=now,
            updated_at=now,
            is_active=is_active,
        )

    def touch(self) -> None:
        """Refresh the update timestamp after a domain change."""
        self.updated_at = datetime.now(UTC)
