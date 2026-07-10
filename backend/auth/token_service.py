"""Token service interface for future access-token implementation."""

from __future__ import annotations

from typing import Any


class TokenService:
    """Interface for token generation and verification."""

    def create_access_token(self, subject: str, expires_in_seconds: int = 3600) -> str:
        """Create an access token for a subject identifier."""
        _ = (subject, expires_in_seconds)
        raise NotImplementedError

    def verify_access_token(self, token: str) -> dict[str, Any]:
        """Verify an access token and return token claims."""
        _ = token
        raise NotImplementedError
