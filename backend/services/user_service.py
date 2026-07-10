"""User service foundation for enterprise ownership lifecycle."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from backend.domain.entities.user import User
from backend.domain.repositories.ownership_repositories import UserRepository


class UserService:
    """Service layer operations for user lifecycle management."""

    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    def create_user(self, *, user_id: str, email: str, display_name: str) -> User:
        """Create and persist a new active user."""
        existing = self.user_repository.get_by_email(email)
        if existing is not None:
            raise ValueError(f"User with email already exists: {email}")

        user = User.create(user_id=user_id, email=email, display_name=display_name)
        create_fn = getattr(self.user_repository, "create", None)
        if callable(create_fn):
            return create_fn(user)

        self.user_repository.save(user)
        return user

    def update_user(
        self,
        user_id: str,
        *,
        email: str | None = None,
        display_name: str | None = None,
        is_active: bool | None = None,
    ) -> User:
        """Update mutable user fields and persist changes."""
        current = self.user_repository.get_by_id(user_id)
        if current is None:
            raise ValueError(f"User not found: {user_id}")

        updated = replace(
            current,
            email=email if email is not None else current.email,
            display_name=(
                display_name if display_name is not None else current.display_name
            ),
            is_active=is_active if is_active is not None else current.is_active,
            updated_at=datetime.now(UTC),
        )

        update_fn = getattr(self.user_repository, "update", None)
        if callable(update_fn):
            result = update_fn(updated)
            return result if isinstance(result, User) else updated

        self.user_repository.save(updated)
        return updated

    def deactivate_user(self, user_id: str) -> User:
        """Deactivate a user account without deleting it."""
        return self.update_user(user_id, is_active=False)

    def list_users(self) -> list[User]:
        """List known users from repository."""
        list_fn = getattr(self.user_repository, "list", None)
        if callable(list_fn):
            result = list_fn()
            return list(result)
        raise NotImplementedError("UserRepository does not implement list()")

    def get_user(self, user_id: str) -> User | None:
        """Get a user by id."""
        return self.user_repository.get_by_id(user_id)

    def get_user_by_email(self, email: str) -> User | None:
        """Get a user by email."""
        return self.user_repository.get_by_email(email)
