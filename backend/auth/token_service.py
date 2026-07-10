"""JWT token creation and verification service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from backend.config.config_manager import ConfigManager


class TokenError(ValueError):
    """Base token error for auth service operations."""


class TokenExpiredError(TokenError):
    """Raised when a token is valid but has expired."""


class TokenInvalidSignatureError(TokenError):
    """Raised when token signature validation fails."""


class TokenMalformedError(TokenError):
    """Raised when a token cannot be decoded as a valid JWT."""


class TokenService:
    """Service for JWT token generation and verification."""

    def __init__(
        self,
        *,
        secret: str | None = None,
        algorithm: str = "HS256",
        default_expires_minutes: int = 60,
    ) -> None:
        config = ConfigManager()
        configured_secret = str(config.get("auth.jwt_secret", "")).strip()
        self.secret = secret or configured_secret or "development-secret"
        self.algorithm = algorithm
        self.default_expires_minutes = default_expires_minutes

    @staticmethod
    def _jwt_module():
        try:
            import jwt
        except ImportError as exc:
            raise RuntimeError("PyJWT is required for token operations") from exc
        return jwt

    def create_access_token(
        self,
        user_id: str,
        email: str,
        expires_minutes: int = 60,
    ) -> str:
        """Create a signed JWT access token.

        Payload includes: sub, email, iat, exp.
        """
        jwt = self._jwt_module()
        now = datetime.now(UTC)
        duration_minutes = expires_minutes or self.default_expires_minutes
        payload: dict[str, Any] = {
            "sub": user_id,
            "email": email,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=duration_minutes)).timestamp()),
        }
        token = jwt.encode(payload, self.secret, algorithm=self.algorithm)
        return str(token)

    def verify_access_token(self, token: str) -> dict[str, Any]:
        """Verify a signed JWT and return claims.

        Raises:
            TokenExpiredError: Token is expired.
            TokenInvalidSignatureError: Signature does not match configured secret.
            TokenMalformedError: Token is malformed or otherwise invalid.
        """
        jwt = self._jwt_module()

        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
        except jwt.ExpiredSignatureError as exc:  # type: ignore[attr-defined]
            raise TokenExpiredError("Token has expired") from exc
        except jwt.InvalidSignatureError as exc:  # type: ignore[attr-defined]
            raise TokenInvalidSignatureError("Invalid token signature") from exc
        except jwt.DecodeError as exc:  # type: ignore[attr-defined]
            raise TokenMalformedError("Malformed token") from exc
        except jwt.InvalidTokenError as exc:  # type: ignore[attr-defined]
            raise TokenMalformedError("Invalid token") from exc

        if "sub" not in payload or "email" not in payload:
            raise TokenMalformedError("Token missing required claims")
        return dict(payload)
