"""Base worker interface definitions."""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.agents.context import AgentExecutionContext


class BaseWorker(ABC):
    """Abstract worker contract for execution orchestration."""

    @abstractmethod
    def name(self) -> str:
        """Return a stable worker identifier."""
        raise NotImplementedError

    @abstractmethod
    def description(self) -> str:
        """Return a human-readable worker summary."""
        raise NotImplementedError

    @abstractmethod
    def execute(self, context: AgentExecutionContext) -> str:
        """Execute work for the given context and return final response text."""
        raise NotImplementedError
