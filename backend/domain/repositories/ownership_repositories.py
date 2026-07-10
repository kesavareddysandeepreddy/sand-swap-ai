"""Repository contracts for enterprise ownership domain models."""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.domain.entities.ownership import (
    AgentOwner,
    ConversationOwner,
    DocumentOwner,
    MemoryOwner,
)
from backend.domain.entities.project import Project
from backend.domain.entities.user import User


class UserRepository(ABC):
    """Persistence contract for users."""

    @abstractmethod
    def save(self, user: User) -> None:
        """Create or update a user record."""
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, user_id: str) -> User | None:
        """Fetch a user by identifier."""
        raise NotImplementedError

    @abstractmethod
    def get_by_email(self, email: str) -> User | None:
        """Fetch a user by unique email."""
        raise NotImplementedError


class ProjectRepository(ABC):
    """Persistence contract for user-owned projects."""

    @abstractmethod
    def save(self, project: Project) -> None:
        """Create or update a project record."""
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, project_id: str) -> Project | None:
        """Fetch a project by identifier."""
        raise NotImplementedError

    @abstractmethod
    def list_by_owner(self, owner_id: str) -> list[Project]:
        """List projects owned by a user."""
        raise NotImplementedError


class ConversationOwnerRepository(ABC):
    """Persistence contract for conversation ownership links."""

    @abstractmethod
    def save(self, relation: ConversationOwner) -> None:
        """Persist a conversation ownership relation."""
        raise NotImplementedError

    @abstractmethod
    def get_by_conversation(self, conversation_id: str) -> ConversationOwner | None:
        """Fetch ownership relation for a conversation."""
        raise NotImplementedError


class DocumentOwnerRepository(ABC):
    """Persistence contract for document ownership links."""

    @abstractmethod
    def save(self, relation: DocumentOwner) -> None:
        """Persist a document ownership relation."""
        raise NotImplementedError

    @abstractmethod
    def get_by_document(self, document_id: str) -> DocumentOwner | None:
        """Fetch ownership relation for a document."""
        raise NotImplementedError


class MemoryOwnerRepository(ABC):
    """Persistence contract for memory ownership links."""

    @abstractmethod
    def save(self, relation: MemoryOwner) -> None:
        """Persist a memory ownership relation."""
        raise NotImplementedError

    @abstractmethod
    def get_by_memory(self, memory_id: str) -> MemoryOwner | None:
        """Fetch ownership relation for a memory record."""
        raise NotImplementedError


class AgentOwnerRepository(ABC):
    """Persistence contract for future agent ownership links."""

    @abstractmethod
    def save(self, relation: AgentOwner) -> None:
        """Persist an agent ownership relation."""
        raise NotImplementedError

    @abstractmethod
    def get_by_agent(self, agent_id: str) -> AgentOwner | None:
        """Fetch ownership relation for an agent."""
        raise NotImplementedError
