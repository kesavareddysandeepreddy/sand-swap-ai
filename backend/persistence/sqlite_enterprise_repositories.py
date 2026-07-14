"""SQLite repository implementations for enterprise ownership models."""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from backend.database.sqlite_connection import create_sqlite_connection
from backend.domain.entities.ownership import (
    AgentOwner,
    ConversationOwner,
    DocumentOwner,
    MemoryOwner,
)
from backend.domain.entities.project import Project
from backend.domain.entities.user import User
from backend.domain.entities.workspace_project import WorkspaceProject
from backend.domain.repositories.ownership_repositories import (
    AgentOwnerRepository,
    ConversationOwnerRepository,
    DocumentOwnerRepository,
    MemoryOwnerRepository,
    ProjectRepository,
    UserRepository,
    WorkspaceProjectRepository,
)


class _SQLiteRepositoryBase:
    """Base class for SQLite-backed repository implementations."""

    def __init__(self, db_path: str = "data/enterprise/enterprise.db") -> None:
        self.db_path = str(Path(db_path).resolve())
        self._lock = threading.RLock()
        self._connection = create_sqlite_connection(self.db_path)
        self._initialize()

    def _initialize(self) -> None:
        """Create required tables for concrete repositories."""

    def _ensure_column(
        self, table_name: str, column_name: str, column_sql: str
    ) -> None:
        with self._lock:
            rows = self._connection.execute(
                f"PRAGMA table_info({table_name})"
            ).fetchall()
            existing_columns = {str(row[1]) for row in rows}
            if column_name in existing_columns:
                return
            self._connection.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"
            )
            self._connection.commit()

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        with self._lock:
            self._connection.close()


class SQLiteUserRepository(_SQLiteRepositoryBase, UserRepository):
    """SQLite-backed repository for user ownership records."""

    def _initialize(self) -> None:
        with self._lock:
            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS enterprise_users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    google_subject_id TEXT,
                    avatar_url TEXT,
                    auth_provider TEXT NOT NULL DEFAULT 'local',
                    active_workspace_id TEXT,
                    active_project_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    is_active INTEGER NOT NULL
                )
                """)
            self._connection.commit()
            self._ensure_column("enterprise_users", "google_subject_id", "TEXT")
            self._ensure_column("enterprise_users", "avatar_url", "TEXT")
            self._ensure_column(
                "enterprise_users",
                "auth_provider",
                "TEXT NOT NULL DEFAULT 'local'",
            )
            self._ensure_column("enterprise_users", "active_workspace_id", "TEXT")
            self._ensure_column("enterprise_users", "active_project_id", "TEXT")

    def create(self, user: User) -> User:
        """Create a user and fail if the id already exists."""
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO enterprise_users (
                    id, email, display_name, google_subject_id, avatar_url,
                    auth_provider, active_workspace_id, active_project_id, created_at, updated_at, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user.id,
                    user.email,
                    user.display_name,
                    user.google_subject_id,
                    user.avatar_url,
                    user.auth_provider,
                    user.active_workspace_id,
                    user.active_project_id,
                    user.created_at.isoformat(),
                    user.updated_at.isoformat(),
                    1 if user.is_active else 0,
                ),
            )
            self._connection.commit()
        return user

    def save(self, user: User) -> None:
        """Create or update a user record."""
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO enterprise_users (
                    id, email, display_name, google_subject_id, avatar_url,
                    auth_provider, active_workspace_id, active_project_id, created_at, updated_at, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    email=excluded.email,
                    display_name=excluded.display_name,
                    google_subject_id=excluded.google_subject_id,
                    avatar_url=excluded.avatar_url,
                    auth_provider=excluded.auth_provider,
                    active_workspace_id=excluded.active_workspace_id,
                    active_project_id=excluded.active_project_id,
                    updated_at=excluded.updated_at,
                    is_active=excluded.is_active
                """,
                (
                    user.id,
                    user.email,
                    user.display_name,
                    user.google_subject_id,
                    user.avatar_url,
                    user.auth_provider,
                    user.active_workspace_id,
                    user.active_project_id,
                    user.created_at.isoformat(),
                    user.updated_at.isoformat(),
                    1 if user.is_active else 0,
                ),
            )
            self._connection.commit()

    def get_by_id(self, user_id: str) -> User | None:
        """Fetch a user by identifier."""
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM enterprise_users WHERE id = ?",
                (user_id,),
            ).fetchone()
        return self._row_to_user(row)

    def get_by_email(self, email: str) -> User | None:
        """Fetch a user by unique email."""
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM enterprise_users WHERE email = ?",
                (email,),
            ).fetchone()
        return self._row_to_user(row)

    def list(self) -> list[User]:
        """List all users ordered by creation timestamp."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM enterprise_users ORDER BY created_at ASC"
            ).fetchall()
        return [self._row_to_user(row) for row in rows if row is not None]

    def update(self, user: User) -> User:
        """Update an existing user record."""
        updated = replace(user, updated_at=datetime.now(UTC))
        with self._lock:
            cursor = self._connection.execute(
                """
                UPDATE enterprise_users
                SET email = ?, display_name = ?, active_workspace_id = ?, active_project_id = ?, updated_at = ?, is_active = ?
                WHERE id = ?
                """,
                (
                    updated.email,
                    updated.display_name,
                    updated.active_workspace_id,
                    updated.active_project_id,
                    updated.updated_at.isoformat(),
                    1 if updated.is_active else 0,
                    updated.id,
                ),
            )
            self._connection.commit()
        if cursor.rowcount == 0:
            raise ValueError(f"User not found: {updated.id}")
        return updated

    def delete(self, user_id: str) -> bool:
        """Delete a user by identifier."""
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM enterprise_users WHERE id = ?",
                (user_id,),
            )
            self._connection.commit()
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_user(row: sqlite3.Row | None) -> User | None:
        if row is None:
            return None
        return User(
            id=str(row["id"]),
            email=str(row["email"]),
            display_name=str(row["display_name"]),
            google_subject_id=(
                str(row["google_subject_id"]) if row["google_subject_id"] else None
            ),
            avatar_url=str(row["avatar_url"]) if row["avatar_url"] else None,
            auth_provider=str(row["auth_provider"]),
            active_workspace_id=(
                str(row["active_workspace_id"]) if row["active_workspace_id"] else None
            ),
            active_project_id=(
                str(row["active_project_id"]) if row["active_project_id"] else None
            ),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
            is_active=bool(int(row["is_active"])),
        )


class SQLiteWorkspaceProjectRepository(
    _SQLiteRepositoryBase, WorkspaceProjectRepository
):
    """SQLite-backed repository for nested projects inside a workspace."""

    def _initialize(self) -> None:
        with self._lock:
            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS enterprise_workspace_projects (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """)
            self._connection.commit()

    def create(self, project: WorkspaceProject) -> WorkspaceProject:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO enterprise_workspace_projects (
                    id, workspace_id, owner_id, name, description, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project.id,
                    project.workspace_id,
                    project.owner_id,
                    project.name,
                    project.description,
                    project.created_at.isoformat(),
                ),
            )
            self._connection.commit()
        return project

    def save(self, project: WorkspaceProject) -> None:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO enterprise_workspace_projects (
                    id, workspace_id, owner_id, name, description, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    workspace_id=excluded.workspace_id,
                    owner_id=excluded.owner_id,
                    name=excluded.name,
                    description=excluded.description
                """,
                (
                    project.id,
                    project.workspace_id,
                    project.owner_id,
                    project.name,
                    project.description,
                    project.created_at.isoformat(),
                ),
            )
            self._connection.commit()

    def get_by_id(self, project_id: str) -> WorkspaceProject | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM enterprise_workspace_projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        return self._row_to_workspace_project(row)

    def update(self, project: WorkspaceProject) -> WorkspaceProject:
        with self._lock:
            cursor = self._connection.execute(
                """
                UPDATE enterprise_workspace_projects
                SET workspace_id = ?, owner_id = ?, name = ?, description = ?
                WHERE id = ?
                """,
                (
                    project.workspace_id,
                    project.owner_id,
                    project.name,
                    project.description,
                    project.id,
                ),
            )
            self._connection.commit()
        if cursor.rowcount == 0:
            raise ValueError(f"Workspace project not found: {project.id}")
        return project

    def delete(self, project_id: str) -> bool:
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM enterprise_workspace_projects WHERE id = ?",
                (project_id,),
            )
            self._connection.commit()
        return cursor.rowcount > 0

    def list_by_workspace(
        self,
        workspace_id: str,
        *,
        owner_id: str | None = None,
    ) -> list[WorkspaceProject]:
        with self._lock:
            if owner_id is None:
                rows = self._connection.execute(
                    """
                    SELECT * FROM enterprise_workspace_projects
                    WHERE workspace_id = ?
                    ORDER BY created_at ASC
                    """,
                    (workspace_id,),
                ).fetchall()
            else:
                rows = self._connection.execute(
                    """
                    SELECT * FROM enterprise_workspace_projects
                    WHERE workspace_id = ? AND owner_id = ?
                    ORDER BY created_at ASC
                    """,
                    (workspace_id, owner_id),
                ).fetchall()
        return [self._row_to_workspace_project(row) for row in rows if row is not None]

    @staticmethod
    def _row_to_workspace_project(
        row: sqlite3.Row | None,
    ) -> WorkspaceProject | None:
        if row is None:
            return None
        return WorkspaceProject(
            id=str(row["id"]),
            workspace_id=str(row["workspace_id"]),
            owner_id=str(row["owner_id"]),
            name=str(row["name"]),
            description=str(row["description"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
        )


class SQLiteProjectRepository(_SQLiteRepositoryBase, ProjectRepository):
    """SQLite-backed repository for project ownership records."""

    def _initialize(self) -> None:
        with self._lock:
            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS enterprise_projects (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """)
            self._connection.commit()

    def create(self, project: Project) -> Project:
        """Create a project and fail if the id already exists."""
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO enterprise_projects (
                    id, owner_id, name, description, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    project.id,
                    project.owner_id,
                    project.name,
                    project.description,
                    project.created_at.isoformat(),
                ),
            )
            self._connection.commit()
        return project

    def save(self, project: Project) -> None:
        """Create or update a project record."""
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO enterprise_projects (
                    id, owner_id, name, description, created_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    owner_id=excluded.owner_id,
                    name=excluded.name,
                    description=excluded.description
                """,
                (
                    project.id,
                    project.owner_id,
                    project.name,
                    project.description,
                    project.created_at.isoformat(),
                ),
            )
            self._connection.commit()

    def list_by_owner(self, owner_id: str) -> list[Project]:
        """List projects owned by a specific user."""
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM enterprise_projects
                WHERE owner_id = ?
                ORDER BY created_at ASC
                """,
                (owner_id,),
            ).fetchall()
        return [self._row_to_project(row) for row in rows if row is not None]

    def get_by_id(self, project_id: str) -> Project | None:
        """Fetch a project by identifier."""
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM enterprise_projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        return self._row_to_project(row)

    def update(self, project: Project) -> Project:
        """Update an existing project."""
        with self._lock:
            cursor = self._connection.execute(
                """
                UPDATE enterprise_projects
                SET owner_id = ?, name = ?, description = ?
                WHERE id = ?
                """,
                (
                    project.owner_id,
                    project.name,
                    project.description,
                    project.id,
                ),
            )
            self._connection.commit()
        if cursor.rowcount == 0:
            raise ValueError(f"Project not found: {project.id}")
        return project

    def delete(self, project_id: str) -> bool:
        """Delete a project by identifier."""
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM enterprise_projects WHERE id = ?",
                (project_id,),
            )
            self._connection.commit()
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_project(row: sqlite3.Row | None) -> Project | None:
        if row is None:
            return None
        return Project(
            id=str(row["id"]),
            owner_id=str(row["owner_id"]),
            name=str(row["name"]),
            description=str(row["description"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
        )


class SQLiteConversationOwnerRepository(
    _SQLiteRepositoryBase,
    ConversationOwnerRepository,
):
    """SQLite-backed repository for conversation ownership."""

    def _initialize(self) -> None:
        with self._lock:
            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS enterprise_conversation_owners (
                    conversation_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL DEFAULT 'default',
                    project_id TEXT NOT NULL DEFAULT 'default'
                )
                """)
            self._connection.commit()
            self._ensure_column(
                "enterprise_conversation_owners",
                "workspace_id",
                "TEXT NOT NULL DEFAULT 'default'",
            )
            self._ensure_column(
                "enterprise_conversation_owners",
                "project_id",
                "TEXT NOT NULL DEFAULT 'default'",
            )

    def assign(self, relation: ConversationOwner) -> ConversationOwner:
        """Assign a conversation to a user."""
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO enterprise_conversation_owners (
                    conversation_id, user_id, workspace_id, project_id
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(conversation_id) DO UPDATE SET
                    user_id=excluded.user_id,
                    workspace_id=excluded.workspace_id,
                    project_id=excluded.project_id
                """,
                (
                    relation.conversation_id,
                    relation.user_id,
                    relation.workspace_id,
                    relation.project_id,
                ),
            )
            self._connection.commit()
        return relation

    def save(self, relation: ConversationOwner) -> None:
        """Persist a conversation ownership relation."""
        self.assign(relation)

    def unassign(self, conversation_id: str) -> bool:
        """Remove ownership for a conversation."""
        with self._lock:
            cursor = self._connection.execute(
                """
                DELETE FROM enterprise_conversation_owners
                WHERE conversation_id = ?
                """,
                (conversation_id,),
            )
            self._connection.commit()
        return cursor.rowcount > 0

    def get_owner(self, conversation_id: str) -> ConversationOwner | None:
        """Fetch ownership for a conversation id."""
        return self.get_by_conversation(conversation_id)

    def get_by_conversation(self, conversation_id: str) -> ConversationOwner | None:
        """Fetch ownership relation for a conversation."""
        with self._lock:
            row = self._connection.execute(
                """
                SELECT * FROM enterprise_conversation_owners
                WHERE conversation_id = ?
                """,
                (conversation_id,),
            ).fetchone()
        if row is None:
            return None
        return ConversationOwner(
            conversation_id=str(row["conversation_id"]),
            user_id=str(row["user_id"]),
            workspace_id=str(row["workspace_id"]),
            project_id=str(row["project_id"]),
        )

    def list_by_user(self, user_id: str) -> list[ConversationOwner]:
        """List conversation ownership records for a user."""
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM enterprise_conversation_owners
                WHERE user_id = ?
                ORDER BY conversation_id ASC
                """,
                (user_id,),
            ).fetchall()
        return [
            ConversationOwner(
                conversation_id=str(row["conversation_id"]),
                user_id=str(row["user_id"]),
                workspace_id=str(row["workspace_id"]),
                project_id=str(row["project_id"]),
            )
            for row in rows
        ]

    def list_by_project(self, project_id: str) -> list[ConversationOwner]:
        """Return no rows because conversations do not have project ownership yet."""
        _ = project_id
        return []


class SQLiteDocumentOwnerRepository(_SQLiteRepositoryBase, DocumentOwnerRepository):
    """SQLite-backed repository for document ownership."""

    def _initialize(self) -> None:
        with self._lock:
            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS enterprise_document_owners (
                    document_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL DEFAULT 'default',
                    project_id TEXT NOT NULL
                )
                """)
            self._connection.commit()
            self._ensure_column(
                "enterprise_document_owners",
                "workspace_id",
                "TEXT NOT NULL DEFAULT 'default'",
            )

    def assign(self, relation: DocumentOwner) -> DocumentOwner:
        """Assign a document to a user and project."""
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO enterprise_document_owners (
                    document_id, user_id, workspace_id, project_id
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    user_id=excluded.user_id,
                    workspace_id=excluded.workspace_id,
                    project_id=excluded.project_id
                """,
                (
                    relation.document_id,
                    relation.user_id,
                    relation.workspace_id,
                    relation.project_id,
                ),
            )
            self._connection.commit()
        return relation

    def save(self, relation: DocumentOwner) -> None:
        """Persist a document ownership relation."""
        self.assign(relation)

    def unassign(self, document_id: str) -> bool:
        """Remove ownership for a document."""
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM enterprise_document_owners WHERE document_id = ?",
                (document_id,),
            )
            self._connection.commit()
        return cursor.rowcount > 0

    def get_owner(self, document_id: str) -> DocumentOwner | None:
        """Fetch ownership for a document id."""
        return self.get_by_document(document_id)

    def get_by_document(self, document_id: str) -> DocumentOwner | None:
        """Fetch ownership relation for a document."""
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM enterprise_document_owners WHERE document_id = ?",
                (document_id,),
            ).fetchone()
        if row is None:
            return None
        return DocumentOwner(
            document_id=str(row["document_id"]),
            user_id=str(row["user_id"]),
            workspace_id=str(row["workspace_id"]),
            project_id=str(row["project_id"]),
        )

    def list_by_user(self, user_id: str) -> list[DocumentOwner]:
        """List document ownership records for a user."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM enterprise_document_owners WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        return [
            DocumentOwner(
                document_id=str(row["document_id"]),
                user_id=str(row["user_id"]),
                workspace_id=str(row["workspace_id"]),
                project_id=str(row["project_id"]),
            )
            for row in rows
        ]

    def list_by_project(self, project_id: str) -> list[DocumentOwner]:
        """List document ownership records for a project."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM enterprise_document_owners WHERE project_id = ?",
                (project_id,),
            ).fetchall()
        return [
            DocumentOwner(
                document_id=str(row["document_id"]),
                user_id=str(row["user_id"]),
                workspace_id=str(row["workspace_id"]),
                project_id=str(row["project_id"]),
            )
            for row in rows
        ]


class SQLiteMemoryOwnerRepository(_SQLiteRepositoryBase, MemoryOwnerRepository):
    """SQLite-backed repository for memory ownership."""

    def _initialize(self) -> None:
        with self._lock:
            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS enterprise_memory_owners (
                    memory_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL DEFAULT 'default',
                    project_id TEXT NOT NULL
                )
                """)
            self._connection.commit()
            self._ensure_column(
                "enterprise_memory_owners",
                "workspace_id",
                "TEXT NOT NULL DEFAULT 'default'",
            )

    def assign(self, relation: MemoryOwner) -> MemoryOwner:
        """Assign a memory record to a user and project."""
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO enterprise_memory_owners (
                    memory_id, user_id, workspace_id, project_id
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                    user_id=excluded.user_id,
                    workspace_id=excluded.workspace_id,
                    project_id=excluded.project_id
                """,
                (
                    relation.memory_id,
                    relation.user_id,
                    relation.workspace_id,
                    relation.project_id,
                ),
            )
            self._connection.commit()
        return relation

    def save(self, relation: MemoryOwner) -> None:
        """Persist a memory ownership relation."""
        self.assign(relation)

    def unassign(self, memory_id: str) -> bool:
        """Remove ownership for a memory record."""
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM enterprise_memory_owners WHERE memory_id = ?",
                (memory_id,),
            )
            self._connection.commit()
        return cursor.rowcount > 0

    def get_owner(self, memory_id: str) -> MemoryOwner | None:
        """Fetch ownership for a memory id."""
        return self.get_by_memory(memory_id)

    def get_by_memory(self, memory_id: str) -> MemoryOwner | None:
        """Fetch ownership relation for a memory record."""
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM enterprise_memory_owners WHERE memory_id = ?",
                (memory_id,),
            ).fetchone()
        if row is None:
            return None
        return MemoryOwner(
            memory_id=str(row["memory_id"]),
            user_id=str(row["user_id"]),
            workspace_id=str(row["workspace_id"]),
            project_id=str(row["project_id"]),
        )

    def list_by_user(self, user_id: str) -> list[MemoryOwner]:
        """List memory ownership records for a user."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM enterprise_memory_owners WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        return [
            MemoryOwner(
                memory_id=str(row["memory_id"]),
                user_id=str(row["user_id"]),
                workspace_id=str(row["workspace_id"]),
                project_id=str(row["project_id"]),
            )
            for row in rows
        ]

    def list_by_project(self, project_id: str) -> list[MemoryOwner]:
        """List memory ownership records for a project."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM enterprise_memory_owners WHERE project_id = ?",
                (project_id,),
            ).fetchall()
        return [
            MemoryOwner(
                memory_id=str(row["memory_id"]),
                user_id=str(row["user_id"]),
                workspace_id=str(row["workspace_id"]),
                project_id=str(row["project_id"]),
            )
            for row in rows
        ]


class SQLiteAgentOwnerRepository(_SQLiteRepositoryBase, AgentOwnerRepository):
    """SQLite-backed repository for agent ownership."""

    def _initialize(self) -> None:
        with self._lock:
            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS enterprise_agent_owners (
                    agent_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL DEFAULT 'default',
                    project_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """)
            self._connection.commit()
            self._ensure_column(
                "enterprise_agent_owners",
                "workspace_id",
                "TEXT NOT NULL DEFAULT 'default'",
            )

    def assign(self, relation: AgentOwner) -> AgentOwner:
        """Assign an agent resource to a user and project."""
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO enterprise_agent_owners (
                    agent_id, user_id, workspace_id, project_id, created_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    user_id=excluded.user_id,
                    workspace_id=excluded.workspace_id,
                    project_id=excluded.project_id,
                    created_at=excluded.created_at
                """,
                (
                    relation.agent_id,
                    relation.user_id,
                    relation.workspace_id,
                    relation.project_id,
                    relation.created_at.isoformat(),
                ),
            )
            self._connection.commit()
        return relation

    def save(self, relation: AgentOwner) -> None:
        """Persist an agent ownership relation."""
        self.assign(relation)

    def unassign(self, agent_id: str) -> bool:
        """Remove ownership for an agent."""
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM enterprise_agent_owners WHERE agent_id = ?",
                (agent_id,),
            )
            self._connection.commit()
        return cursor.rowcount > 0

    def get_owner(self, agent_id: str) -> AgentOwner | None:
        """Fetch ownership for an agent id."""
        return self.get_by_agent(agent_id)

    def get_by_agent(self, agent_id: str) -> AgentOwner | None:
        """Fetch ownership relation for an agent."""
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM enterprise_agent_owners WHERE agent_id = ?",
                (agent_id,),
            ).fetchone()
        if row is None:
            return None
        return AgentOwner(
            agent_id=str(row["agent_id"]),
            user_id=str(row["user_id"]),
            workspace_id=str(row["workspace_id"]),
            project_id=str(row["project_id"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
        )

    def list_by_user(self, user_id: str) -> list[AgentOwner]:
        """List agent ownership records for a user."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM enterprise_agent_owners WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        return [
            AgentOwner(
                agent_id=str(row["agent_id"]),
                user_id=str(row["user_id"]),
                workspace_id=str(row["workspace_id"]),
                project_id=str(row["project_id"]),
                created_at=datetime.fromisoformat(str(row["created_at"])),
            )
            for row in rows
        ]

    def list_by_project(self, project_id: str) -> list[AgentOwner]:
        """List agent ownership records for a project."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM enterprise_agent_owners WHERE project_id = ?",
                (project_id,),
            ).fetchall()
        return [
            AgentOwner(
                agent_id=str(row["agent_id"]),
                user_id=str(row["user_id"]),
                workspace_id=str(row["workspace_id"]),
                project_id=str(row["project_id"]),
                created_at=datetime.fromisoformat(str(row["created_at"])),
            )
            for row in rows
        ]
