"""Base agent interfaces and default general chat agent."""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.agents.context import AgentExecutionContext
from backend.agents.models import AgentExecutionPlan
from backend.core.logging.logger import LoggerFactory
from backend.llm.client import OllamaClient


class BaseAgent(ABC):
    """Base contract for runtime agents."""

    @abstractmethod
    def name(self) -> str:
        """Return stable runtime identifier."""
        raise NotImplementedError

    @abstractmethod
    def description(self) -> str:
        """Return short human-readable purpose."""
        raise NotImplementedError

    @abstractmethod
    def can_handle(self, context: AgentExecutionContext) -> bool:
        """Return whether this agent can handle current context."""
        raise NotImplementedError

    @abstractmethod
    def plan(self, context: AgentExecutionContext) -> AgentExecutionPlan:
        """Return an agent-specific execution plan."""
        raise NotImplementedError

    @abstractmethod
    def execute(self, context: AgentExecutionContext) -> str:
        """Execute using provided context and return response text."""
        raise NotImplementedError

    @abstractmethod
    def health(self) -> dict[str, object]:
        """Return health information for diagnostics."""
        raise NotImplementedError


class EngineeringAgent(BaseAgent):
    """Extension point for future engineering agent."""


class NutritionAgent(BaseAgent):
    """Extension point for future nutrition agent."""


class MedicalAgent(BaseAgent):
    """Extension point for future medical agent."""


class FinanceAgent(BaseAgent):
    """Extension point for future finance agent."""


class WorkflowAgent(BaseAgent):
    """Extension point for future workflow agent."""


class GeneralChatAgent(BaseAgent):
    """Default chat agent preserving current LLM behavior."""

    def __init__(self, ollama_client: OllamaClient) -> None:
        self.ollama_client = ollama_client
        self.logger = LoggerFactory.get_logger("GeneralChatAgent")

    def name(self) -> str:
        return "general_chat_agent"

    def description(self) -> str:
        return "Default general-purpose chat execution agent."

    def can_handle(self, context: AgentExecutionContext) -> bool:
        _ = context
        return True

    def plan(self, context: AgentExecutionContext) -> AgentExecutionPlan:
        _ = context
        return AgentExecutionPlan(
            selected_agent=self.name(),
            rationale="Fallback/default chat handling path.",
            steps=[],
        )

    def execute(self, context: AgentExecutionContext) -> str:
        self.logger.info(
            "LLM_REQUEST query=%r owner_id=%s workspace_id=%s project_id=%s chunks_retrieved=%s chunks_in_prompt=%s",
            context.user_prompt,
            context.metadata.get("owner_id"),
            context.workspace_id,
            context.project_id,
            len(context.rag_context),
            len(context.rag_context),
        )
        return str(
            self.ollama_client.generate(
                prompt=context.prompt,
                model=context.model,
                system=context.system_prompt,
                temperature=float(context.metadata.get("temperature", 0.2)),
            )
        )

    def health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "agent": self.name(),
            "model": getattr(self.ollama_client, "model", "unknown"),
        }
