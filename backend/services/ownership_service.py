"""Service layer for enterprise ownership assignments and lookups."""

from __future__ import annotations

from uuid import uuid4

from backend.domain.entities.ownership import (
    AgentOwner,
    ConversationOwner,
    DocumentOwner,
    MemoryOwner,
)
from backend.domain.entities.project import Project
from backend.domain.entities.workspace_project import WorkspaceProject
from backend.domain.repositories.ownership_repositories import (
    AgentOwnerRepository,
    ConversationOwnerRepository,
    DocumentOwnerRepository,
    MemoryOwnerRepository,
    ProjectRepository,
    WorkspaceProjectRepository,
)
from backend.services.user_service import UserService


class OwnershipService:
    """Coordinates ownership assignments across enterprise resources."""

    def __init__(
        self,
        *,
        user_service: UserService,
        project_repository: ProjectRepository,
        workspace_project_repository: WorkspaceProjectRepository,
        document_owner_repository: DocumentOwnerRepository,
        conversation_owner_repository: ConversationOwnerRepository,
        memory_owner_repository: MemoryOwnerRepository,
        agent_owner_repository: AgentOwnerRepository,
    ) -> None:
        self.user_service = user_service
        self.project_repository = project_repository
        self.workspace_project_repository = workspace_project_repository
        self.document_owner_repository = document_owner_repository
        self.conversation_owner_repository = conversation_owner_repository
        self.memory_owner_repository = memory_owner_repository
        self.agent_owner_repository = agent_owner_repository

    def assign_project_owner(
        self,
        *,
        project_id: str,
        user_id: str,
        name: str | None = None,
        description: str = "",
    ) -> Project:
        """Assign a project to a user, creating the project when missing."""
        existing = self.project_repository.get_by_id(project_id)

        if existing is None:
            project = Project.create(
                project_id=project_id,
                owner_id=user_id,
                name=name or "Workspace",
                description=description,
            )
            create_fn = getattr(self.project_repository, "create", None)
            if callable(create_fn):
                return create_fn(project)
            self.project_repository.save(project)
            return project

        if (
            existing.owner_id == user_id
            and (name is None or name == existing.name)
            and description == existing.description
        ):
            return existing

        updated = Project(
            id=existing.id,
            owner_id=user_id,
            name=name if name is not None else existing.name,
            description=description if description else existing.description,
            created_at=existing.created_at,
        )
        update_fn = getattr(self.project_repository, "update", None)
        if callable(update_fn):
            return update_fn(updated)
        self.project_repository.save(updated)
        return updated

    def assign_document_owner(
        self,
        *,
        document_id: str,
        user_id: str,
        workspace_id: str,
        project_id: str,
    ) -> DocumentOwner:
        """Assign ownership metadata for a document."""
        relation = DocumentOwner(
            document_id=document_id,
            user_id=user_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        self.document_owner_repository.save(relation)
        return relation

    def assign_conversation_owner(
        self,
        *,
        conversation_id: str,
        user_id: str,
        workspace_id: str,
        project_id: str,
    ) -> ConversationOwner:
        """Assign ownership metadata for a conversation."""
        relation = ConversationOwner(
            conversation_id=conversation_id,
            user_id=user_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        self.conversation_owner_repository.save(relation)
        return relation

    def assign_memory_owner(
        self,
        *,
        memory_id: str,
        user_id: str,
        workspace_id: str,
        project_id: str,
    ) -> MemoryOwner:
        """Assign ownership metadata for a memory item."""
        relation = MemoryOwner(
            memory_id=memory_id,
            user_id=user_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        self.memory_owner_repository.save(relation)
        return relation

    def assign_agent_owner(
        self,
        *,
        agent_id: str,
        user_id: str,
        workspace_id: str,
        project_id: str,
    ) -> AgentOwner:
        """Assign ownership metadata for an agent resource."""
        relation = AgentOwner.create(
            agent_id=agent_id,
            user_id=user_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        self.agent_owner_repository.save(relation)
        return relation

    def get_document_owner(self, document_id: str) -> DocumentOwner | None:
        """Look up owner metadata for a document."""
        return self.document_owner_repository.get_by_document(document_id)

    def list_document_owners(self, user_id: str) -> list[DocumentOwner]:
        """List document ownership metadata for a user."""
        return self.document_owner_repository.list_by_user(user_id)

    def unassign_document_owner(self, document_id: str) -> bool:
        """Remove owner metadata for a document."""
        return self.document_owner_repository.unassign(document_id)

    def get_conversation_owner(
        self,
        conversation_id: str,
    ) -> ConversationOwner | None:
        """Look up owner metadata for a conversation."""
        return self.conversation_owner_repository.get_by_conversation(conversation_id)

    def list_conversation_owners(self, user_id: str) -> list[ConversationOwner]:
        """List conversation ownership metadata for a user."""
        return self.conversation_owner_repository.list_by_user(user_id)

    def unassign_conversation_owner(self, conversation_id: str) -> bool:
        """Remove owner metadata for a conversation."""
        return self.conversation_owner_repository.unassign(conversation_id)

    def get_memory_owner(self, memory_id: str) -> MemoryOwner | None:
        """Look up owner metadata for a memory item."""
        return self.memory_owner_repository.get_by_memory(memory_id)

    def get_agent_owner(self, agent_id: str) -> AgentOwner | None:
        """Look up owner metadata for an agent resource."""
        return self.agent_owner_repository.get_by_agent(agent_id)

    def list_projects_for_user(self, user_id: str) -> list[Project]:
        """List all projects owned by a user."""
        return self.project_repository.list_by_owner(user_id)

    def get_default_project_for_user(self, user_id: str) -> Project:
        """Return or create a default workspace project for a user."""
        projects = self.list_projects_for_user(user_id)
        if projects:
            default_project = next(
                (
                    project
                    for project in projects
                    if project.name.strip().lower()
                    in {"default", "default workspace", "personal workspace"}
                ),
                None,
            )
            return default_project or projects[0]

        return self.assign_project_owner(
            project_id=f"workspace-{user_id}",
            user_id=user_id,
            name="Default Workspace",
            description="Default workspace for authenticated user",
        )

    def get_active_project_for_user(self, user_id: str) -> Project:
        """Resolve and persist an active workspace for the user."""
        active_project_id = self.user_service.get_active_project_id(user_id)
        if active_project_id:
            active = self.project_repository.get_by_id(active_project_id)
            if active is not None and active.owner_id == user_id:
                return active

        default_project = self.get_default_project_for_user(user_id)
        self.user_service.set_active_project_id(user_id, default_project.id)
        return default_project

    def get_active_workspace_project_for_user(
        self,
        user_id: str,
        *,
        workspace_id: str,
    ) -> WorkspaceProject:
        """Resolve and persist the active nested project inside a workspace."""
        active_project_id = self.user_service.get_active_workspace_project_id(user_id)
        if active_project_id:
            active_project = self.workspace_project_repository.get_by_id(
                active_project_id
            )
            if (
                active_project is not None
                and active_project.owner_id == user_id
                and active_project.workspace_id == workspace_id
            ):
                return active_project

        projects = self.workspace_project_repository.list_by_workspace(
            workspace_id,
            owner_id=user_id,
        )
        if projects:
            self.user_service.set_active_workspace_project_id(user_id, projects[0].id)
            return projects[0]

        default_project = self.create_project_for_workspace(
            user_id=user_id,
            workspace_id=workspace_id,
            name="General Project",
            description="Default project for workspace",
            set_active=True,
        )
        return default_project

    def set_active_project_for_user(self, user_id: str, project_id: str) -> Project:
        """Set and persist the active workspace for a user."""
        project = self.project_repository.get_by_id(project_id)
        if project is None:
            raise ValueError("Workspace not found")
        if project.owner_id != user_id:
            raise ValueError("Workspace does not belong to the user")

        self.user_service.set_active_project_id(user_id, project.id)
        return project

    def set_active_workspace_project_for_user(
        self,
        user_id: str,
        *,
        workspace_id: str,
        project_id: str,
    ) -> WorkspaceProject:
        """Set and persist the active nested project for a workspace."""
        project = self.workspace_project_repository.get_by_id(project_id)
        if project is None:
            raise ValueError("Project not found")
        if project.owner_id != user_id or project.workspace_id != workspace_id:
            raise ValueError("Project does not belong to the workspace")

        self.user_service.set_active_workspace_project_id(user_id, project.id)
        return project

    def create_workspace_for_user(
        self,
        *,
        user_id: str,
        name: str,
        description: str = "",
        set_active: bool = True,
    ) -> Project:
        """Create a new workspace for the user and optionally activate it."""
        project = Project.create(
            project_id=str(uuid4()),
            owner_id=user_id,
            name=name,
            description=description,
        )
        create_fn = getattr(self.project_repository, "create", None)
        if callable(create_fn):
            project = create_fn(project)
        else:
            self.project_repository.save(project)
        if set_active:
            self.user_service.set_active_project_id(user_id, project.id)
        return project

    def create_project_for_workspace(
        self,
        *,
        user_id: str,
        workspace_id: str,
        name: str,
        description: str = "",
        set_active: bool = True,
    ) -> WorkspaceProject:
        """Create a nested project inside a workspace."""
        workspace = self.project_repository.get_by_id(workspace_id)
        if workspace is None or workspace.owner_id != user_id:
            raise ValueError("Workspace does not belong to the user")

        project = WorkspaceProject.create(
            project_id=str(uuid4()),
            workspace_id=workspace_id,
            owner_id=user_id,
            name=name,
            description=description,
        )
        create_fn = getattr(self.workspace_project_repository, "create", None)
        if callable(create_fn):
            project = create_fn(project)
        else:
            self.workspace_project_repository.save(project)
        if set_active:
            self.user_service.set_active_workspace_project_id(user_id, project.id)
        return project

    def list_projects_for_workspace(
        self,
        *,
        user_id: str,
        workspace_id: str,
    ) -> list[WorkspaceProject]:
        """List projects inside a workspace for an owner."""
        workspace = self.project_repository.get_by_id(workspace_id)
        if workspace is None or workspace.owner_id != user_id:
            return []
        return self.workspace_project_repository.list_by_workspace(
            workspace_id,
            owner_id=user_id,
        )

    def rename_project_for_workspace(
        self,
        *,
        user_id: str,
        workspace_id: str,
        project_id: str,
        name: str,
        description: str | None = None,
    ) -> WorkspaceProject:
        """Rename a nested project within a workspace."""
        project = self.workspace_project_repository.get_by_id(project_id)
        if project is None:
            raise ValueError("Project not found")
        if project.owner_id != user_id or project.workspace_id != workspace_id:
            raise ValueError("Project does not belong to the workspace")

        updated = WorkspaceProject(
            id=project.id,
            workspace_id=project.workspace_id,
            owner_id=project.owner_id,
            name=name,
            description=(
                description if description is not None else project.description
            ),
            created_at=project.created_at,
        )
        update_fn = getattr(self.workspace_project_repository, "update", None)
        if callable(update_fn):
            return update_fn(updated)
        self.workspace_project_repository.save(updated)
        return updated

    def delete_project_for_workspace(
        self,
        *,
        user_id: str,
        workspace_id: str,
        project_id: str,
    ) -> bool:
        """Delete a nested project and rotate active project when needed."""
        project = self.workspace_project_repository.get_by_id(project_id)
        if project is None:
            return False
        if project.owner_id != user_id or project.workspace_id != workspace_id:
            raise ValueError("Project does not belong to the workspace")

        projects = self.workspace_project_repository.list_by_workspace(
            workspace_id,
            owner_id=user_id,
        )
        if len(projects) <= 1:
            raise ValueError("Cannot delete the last project")

        deleted = self.workspace_project_repository.delete(project_id)
        if not deleted:
            return False

        active_project_id = self.user_service.get_active_workspace_project_id(user_id)
        if active_project_id == project_id:
            next_project = next(
                (candidate for candidate in projects if candidate.id != project_id),
                None,
            )
            if next_project is not None:
                self.user_service.set_active_workspace_project_id(
                    user_id, next_project.id
                )
        return True

    def rename_workspace_for_user(
        self,
        *,
        user_id: str,
        project_id: str,
        name: str,
        description: str | None = None,
    ) -> Project:
        """Rename a workspace that belongs to the user."""
        existing = self.project_repository.get_by_id(project_id)
        if existing is None:
            raise ValueError("Workspace not found")
        if existing.owner_id != user_id:
            raise ValueError("Workspace does not belong to the user")

        updated = Project(
            id=existing.id,
            owner_id=existing.owner_id,
            name=name,
            description=(
                description if description is not None else existing.description
            ),
            created_at=existing.created_at,
        )
        update_fn = getattr(self.project_repository, "update", None)
        if callable(update_fn):
            return update_fn(updated)
        self.project_repository.save(updated)
        return updated

    def delete_workspace_for_user(self, *, user_id: str, project_id: str) -> bool:
        """Delete a workspace and rotate active selection when required."""
        existing = self.project_repository.get_by_id(project_id)
        if existing is None:
            return False
        if existing.owner_id != user_id:
            raise ValueError("Workspace does not belong to the user")

        workspaces = self.list_projects_for_user(user_id)
        if len(workspaces) <= 1:
            raise ValueError("Cannot delete the last workspace")

        deleted = self.project_repository.delete(project_id)
        if not deleted:
            return False

        active = self.user_service.get_active_project_id(user_id)
        if active == project_id:
            next_workspace = next(
                (workspace for workspace in workspaces if workspace.id != project_id),
                None,
            )
            if next_workspace is not None:
                self.user_service.set_active_project_id(user_id, next_workspace.id)
        return True

    def resolve_request_context(
        self,
        *,
        user_id: str,
        requested_workspace_id: str | None = None,
        requested_project_id: str | None = None,
    ) -> dict[str, str]:
        """Resolve per-request ownership context for authenticated flows."""
        user = self.user_service.get_user(user_id)
        if user is None:
            return {
                "user_id": user_id,
                "workspace_id": "default",
                "project_id": "default",
            }

        if requested_workspace_id:
            try:
                active_workspace = self.set_active_project_for_user(
                    user_id,
                    requested_workspace_id,
                )
            except ValueError:
                active_workspace = self.get_active_project_for_user(user_id)
        else:
            active_workspace = self.get_active_project_for_user(user_id)

        if requested_project_id:
            try:
                active_project = self.set_active_workspace_project_for_user(
                    user_id,
                    workspace_id=active_workspace.id,
                    project_id=requested_project_id,
                )
            except ValueError:
                active_project = self.get_active_workspace_project_for_user(
                    user_id,
                    workspace_id=active_workspace.id,
                )
        else:
            active_project = self.get_active_workspace_project_for_user(
                user_id,
                workspace_id=active_workspace.id,
            )
        return {
            "user_id": user_id,
            "workspace_id": active_workspace.id,
            "project_id": active_project.id,
        }
