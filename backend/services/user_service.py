"""User service foundation for enterprise ownership lifecycle."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from backend.domain.entities.project import Project
from backend.domain.entities.user import User
from backend.domain.repositories.ownership_repositories import (
    ProjectRepository,
    UserRepository,
)


class UserService:
    """Service layer operations for user lifecycle management."""

    def __init__(
        self,
        user_repository: UserRepository,
        project_repository: ProjectRepository | None = None,
    ) -> None:
        self.user_repository = user_repository
        self.project_repository = project_repository

    def create_user(
        self,
        *,
        user_id: str,
        email: str,
        display_name: str,
        google_subject_id: str | None = None,
        avatar_url: str | None = None,
        auth_provider: str = "local",
    ) -> User:
        """Create and persist a new active user."""
        existing = self.user_repository.get_by_email(email)
        if existing is not None:
            raise ValueError(f"User with email already exists: {email}")

        user = User.create(
            user_id=user_id,
            email=email,
            display_name=display_name,
            google_subject_id=google_subject_id,
            avatar_url=avatar_url,
            auth_provider=auth_provider,
        )
        create_fn = getattr(self.user_repository, "create", None)
        if callable(create_fn):
            created = create_fn(user)
            self.ensure_default_project(created.id, created.display_name)
            return created

        self.user_repository.save(user)
        self.ensure_default_project(user.id, user.display_name)
        return user

    def _require_project_repository(self) -> ProjectRepository:
        if self.project_repository is None:
            raise NotImplementedError(
                "ProjectRepository is required for project workspace operations"
            )
        return self.project_repository

    def create_project(
        self,
        *,
        owner_id: str,
        name: str,
        description: str = "",
        project_id: str | None = None,
    ) -> Project:
        """Create and persist a project workspace for a user."""
        repository = self._require_project_repository()
        project = Project.create(
            project_id=project_id or str(uuid4()),
            owner_id=owner_id,
            name=name,
            description=description,
        )
        create_fn = getattr(repository, "create", None)
        if callable(create_fn):
            return create_fn(project)
        repository.save(project)
        return project

    def update_project(
        self,
        project_id: str,
        *,
        owner_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> Project:
        """Update mutable project fields for an owner."""
        repository = self._require_project_repository()
        current = repository.get_by_id(project_id)
        if current is None:
            raise ValueError(f"Project not found: {project_id}")
        if current.owner_id != owner_id:
            raise ValueError("Project does not belong to the requested owner")

        updated = Project(
            id=current.id,
            owner_id=current.owner_id,
            name=name if name is not None else current.name,
            description=(
                description if description is not None else current.description
            ),
            created_at=current.created_at,
        )
        update_fn = getattr(repository, "update", None)
        if callable(update_fn):
            return update_fn(updated)
        repository.save(updated)
        return updated

    def delete_project(self, project_id: str, *, owner_id: str) -> bool:
        """Delete a project owned by the given user."""
        repository = self._require_project_repository()
        current = repository.get_by_id(project_id)
        if current is None:
            return False
        if current.owner_id != owner_id:
            raise ValueError("Project does not belong to the requested owner")

        delete_fn = getattr(repository, "delete", None)
        if callable(delete_fn):
            return bool(delete_fn(project_id))
        raise NotImplementedError("ProjectRepository does not implement delete()")

    def list_projects_by_owner(self, owner_id: str) -> list[Project]:
        """List projects for a specific owner."""
        repository = self._require_project_repository()
        return repository.list_by_owner(owner_id)

    def get_project_by_id(self, project_id: str, *, owner_id: str) -> Project | None:
        """Return a project by id when it belongs to the owner."""
        repository = self._require_project_repository()
        project = repository.get_by_id(project_id)
        if project is None or project.owner_id != owner_id:
            return None
        return project

    def ensure_default_project(
        self, owner_id: str, display_name: str
    ) -> Project | None:
        """Ensure each user has at least one default project workspace."""
        if self.project_repository is None:
            return None

        existing = self.project_repository.list_by_owner(owner_id)
        if existing:
            return existing[0]

        default_name = "Personal Workspace"
        default_description = f"Personal workspace for {display_name}"
        return self.create_project(
            owner_id=owner_id,
            name=default_name,
            description=default_description,
        )

    def get_active_project_id(self, user_id: str) -> str | None:
        """Return the persisted active project id for a user, if any."""
        user = self.user_repository.get_by_id(user_id)
        if user is None:
            return None
        return user.active_project_id

    def set_active_project_id(self, user_id: str, project_id: str | None) -> User:
        """Persist active project id for a user account."""
        current = self.user_repository.get_by_id(user_id)
        if current is None:
            raise ValueError(f"User not found: {user_id}")

        updated = replace(
            current,
            active_project_id=project_id,
            updated_at=datetime.now(UTC),
        )

        update_fn = getattr(self.user_repository, "update", None)
        if callable(update_fn):
            result = update_fn(updated)
            return result if isinstance(result, User) else updated

        self.user_repository.save(updated)
        return updated

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
