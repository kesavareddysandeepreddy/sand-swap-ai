"""Knowledge object registry for relationship mapping and discovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from backend.knowledge.knowledge_models import KnowledgeObject


class KnowledgeAnalyzer(Protocol):
    """Extension-point contract for future domain analyzers."""

    def analyze(self, knowledge_object: KnowledgeObject) -> dict[str, object]:
        """Analyze a knowledge object and return structured diagnostics."""
        ...


@dataclass(slots=True)
class AnalyzerRegistry:
    """Container for future analyzer extension points."""

    engineering: KnowledgeAnalyzer | None = None
    nutrition: KnowledgeAnalyzer | None = None
    medical: KnowledgeAnalyzer | None = None
    finance: KnowledgeAnalyzer | None = None
    workflow: KnowledgeAnalyzer | None = None


class KnowledgeRegistry:
    """Maintain mappings between knowledge objects and runtime scopes."""

    def __init__(self) -> None:
        self._conversation_map: dict[str, set[str]] = {}
        self._workspace_map: dict[str, set[str]] = {}
        self._project_map: dict[str, set[str]] = {}
        self._document_map: dict[str, set[str]] = {}
        self._agent_map: dict[str, set[str]] = {}
        self._knowledge_ids: set[str] = set()
        self.analyzers = AnalyzerRegistry()

    def register(self, knowledge_object: KnowledgeObject) -> None:
        """Register a knowledge object across all known mappings."""
        self._knowledge_ids.add(knowledge_object.id)

        if knowledge_object.conversation_id:
            self._conversation_map.setdefault(
                knowledge_object.conversation_id, set()
            ).add(knowledge_object.id)
        if knowledge_object.workspace_id:
            self._workspace_map.setdefault(knowledge_object.workspace_id, set()).add(
                knowledge_object.id
            )
        if knowledge_object.project_id:
            self._project_map.setdefault(knowledge_object.project_id, set()).add(
                knowledge_object.id
            )
        if knowledge_object.document_id:
            self._document_map.setdefault(knowledge_object.document_id, set()).add(
                knowledge_object.id
            )

    def map_to_agent(self, agent_id: str, knowledge_id: str) -> None:
        """Register a future agent to knowledge-object relation."""
        self._agent_map.setdefault(agent_id, set()).add(knowledge_id)

    def by_conversation(self, conversation_id: str) -> list[str]:
        return sorted(self._conversation_map.get(conversation_id, set()))

    def by_workspace(self, workspace_id: str) -> list[str]:
        return sorted(self._workspace_map.get(workspace_id, set()))

    def by_project(self, project_id: str) -> list[str]:
        return sorted(self._project_map.get(project_id, set()))

    def by_document(self, document_id: str) -> list[str]:
        return sorted(self._document_map.get(document_id, set()))

    def by_agent(self, agent_id: str) -> list[str]:
        return sorted(self._agent_map.get(agent_id, set()))

    def all_ids(self) -> list[str]:
        return sorted(self._knowledge_ids)
