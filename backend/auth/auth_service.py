"""Authentication service foundation without API handlers."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.auth.password_hasher import PasswordHasher
from backend.domain.entities.user import User
from backend.services.user_service import UserService


@dataclass(slots=True)
class AuthService:
    """Application service for user registration and authentication."""

    user_service: UserService
    password_hasher: PasswordHasher
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
