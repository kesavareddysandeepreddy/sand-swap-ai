"""Agent registry for discovery and health tracking."""

from __future__ import annotations

from backend.agents.base import BaseAgent


class AgentRegistry:
    """Runtime registry for pluggable agents."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.name()] = agent

    def discover(self) -> list[BaseAgent]:
        return [self._agents[name] for name in sorted(self._agents.keys())]

    def lookup(self, agent_name: str) -> BaseAgent | None:
        return self._agents.get(agent_name)

    def health(self) -> dict[str, dict[str, object]]:
        return {name: agent.health() for name, agent in self._agents.items()}
