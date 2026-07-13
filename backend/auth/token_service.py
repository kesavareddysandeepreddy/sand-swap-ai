"""JWT token creation and verification service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

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
        default_refresh_expires_days: int = 30,
    ) -> None:
        config = ConfigManager()
        configured_secret = str(config.get("auth.jwt_secret", "")).strip()
        self.secret = secret or configured_secret or "development-secret"
        self.algorithm = algorithm
        self.default_expires_minutes = default_expires_minutes
        self.default_refresh_expires_days = default_refresh_expires_days
        self._revoked_refresh_tokens: set[str] = set()

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
            "token_type": "access",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=duration_minutes)).timestamp()),
        }
        token = jwt.encode(payload, self.secret, algorithm=self.algorithm)
        return str(token)

    def create_refresh_token(
        self,
        user_id: str,
        email: str,
        expires_days: int | None = None,
    ) -> str:
        """Create a signed JWT refresh token."""
        jwt = self._jwt_module()
        now = datetime.now(UTC)
        ttl_days = expires_days or self.default_refresh_expires_days
        payload: dict[str, Any] = {
            "sub": user_id,
            "email": email,
            "token_type": "refresh",
            "jti": str(uuid4()),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(days=ttl_days)).timestamp()),
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
        token_type = payload.get("token_type", "access")
        if token_type != "access":
            raise TokenMalformedError("Token is not an access token")
        return dict(payload)

    def verify_refresh_token(self, token: str) -> dict[str, Any]:
        """Verify a signed refresh token and return claims."""
        payload = self._decode_token(token)
        if "sub" not in payload or "email" not in payload:
            raise TokenMalformedError("Token missing required claims")
        if payload.get("token_type") != "refresh":
            raise TokenMalformedError("Token is not a refresh token")
        jti = payload.get("jti")
        if not isinstance(jti, str) or not jti:
            raise TokenMalformedError("Refresh token missing jti")
        if jti in self._revoked_refresh_tokens:
            raise TokenMalformedError("Refresh token revoked")
        return dict(payload)

    def revoke_refresh_token(self, token: str) -> None:
        """Revoke an existing refresh token if decodable."""
        try:
            payload = self.verify_refresh_token(token)
        except TokenError:
            return
        jti = payload.get("jti")
        if isinstance(jti, str) and jti:
            self._revoked_refresh_tokens.add(jti)

    def _decode_token(self, token: str) -> dict[str, Any]:
        """Decode JWT and normalize service-specific token exceptions."""
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

        return dict(payload)
