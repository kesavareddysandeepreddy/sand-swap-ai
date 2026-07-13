"""Authentication service foundation without API handlers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.auth.password_hasher import PasswordHasher
from backend.auth.token_service import TokenService
from backend.domain.entities.user import User
from backend.services.user_service import UserService


@dataclass(slots=True)
class AuthService:
    """Application service for user registration and authentication."""

    user_service: UserService
    password_hasher: PasswordHasher
    token_service: TokenService = field(default_factory=TokenService)
    _password_hashes: dict[str, str] = field(default_factory=dict)

    def register_user(
        self,
        *,
        user_id: str,
        email: str,
        display_name: str,
        password: str,
    ) -> User:
        """Register a new user and persist password hash in service store."""
        user = self.user_service.create_user(
            user_id=user_id,
            email=email,
            display_name=display_name,
        )
        self._password_hashes[user.id] = self.password_hasher.hash_password(password)
        return user

    def authenticate(self, *, email: str, password: str) -> User | None:
        """Authenticate user by email and password.

        Returns:
            The authenticated user if credentials are valid and user is active.
            Otherwise returns None.
        """
        user = self.user_service.get_user_by_email(email)
        if user is None or not user.is_active:
            return None

        stored_hash = self._password_hashes.get(user.id)
        if stored_hash is None:
            return None

        if not self.password_hasher.verify_password(password, stored_hash):
            return None

        return user

    def get_user(self, user_id: str) -> User | None:
        """Fetch a user by identifier."""
        return self.user_service.get_user(user_id)

    def issue_token(self, user: User, expires_minutes: int = 60) -> str:
        """Issue a signed access token for an authenticated user."""
        return self.token_service.create_access_token(
            user_id=user.id,
            email=user.email,
            expires_minutes=expires_minutes,
        )

    def issue_token_pair(self, user: User, expires_minutes: int = 60) -> dict[str, str]:
        """Issue an access and refresh token pair for an authenticated user."""
        access_token = self.issue_token(user=user, expires_minutes=expires_minutes)
        refresh_token = self.token_service.create_refresh_token(
            user_id=user.id,
            email=user.email,
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    def refresh_access_token(
        self, refresh_token: str, expires_minutes: int = 60
    ) -> str:
        """Rotate a refresh token into a new access token."""
        claims = self.token_service.verify_refresh_token(refresh_token)
        user = self.get_user(str(claims["sub"]))
        if user is None or not user.is_active:
            raise ValueError("User not found or inactive")
        return self.issue_token(user=user, expires_minutes=expires_minutes)

    def logout(self, refresh_token: str | None = None) -> None:
        """Invalidate refresh token state for logout semantics."""
        if not refresh_token:
            return
        self.token_service.revoke_refresh_token(refresh_token)

    def validate_token(self, token: str) -> dict[str, Any]:
        """Validate a JWT access token and return claims."""
        return self.token_service.verify_access_token(token)
