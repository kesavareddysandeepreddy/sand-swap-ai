"""Request-scoped authenticated user context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CurrentUser:
    """Resolved request user context.

    Anonymous requests remain valid and resolve to an unauthenticated context.
    """

    user_id: str | None
    email: str | None
    is_authenticated: bool
    claims: dict[str, Any] = field(default_factory=dict)
    auth_error: str | None = None

    @classmethod
    def anonymous(cls, auth_error: str | None = None) -> "CurrentUser":
        """Build an anonymous request context."""
        return cls(
            user_id=None,
            email=None,
            is_authenticated=False,
            claims={},
            auth_error=auth_error,
        )

    @classmethod
    def authenticated(cls, claims: dict[str, Any]) -> "CurrentUser":
        """Build an authenticated request context from JWT claims."""
        return cls(
            user_id=str(claims["sub"]),
            email=str(claims["email"]),
            is_authenticated=True,
            claims=dict(claims),
        )
