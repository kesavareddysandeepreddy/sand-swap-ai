"""Autonomous planning and capability-scoring runtime for Prompt 4 missions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class PlannerContext:
    """Inputs used by the autonomous planner for one mission."""

    goal: str
    constraints: list[str]
    context: dict[str, Any]
    workflows: list[dict[str, Any]]
    agents: list[dict[str, Any]]
    agent_workload: dict[str, int]
    agent_success: dict[str, float]


class CapabilityScoringEngine:
    """Scores agent-task fit across capabilities, knowledge, tools, and reliability."""

    _KEYWORD_CAPABILITIES: dict[str, list[str]] = {
        "python": ["python", "code", "script", "automation", "programming"],
        "api": ["api", "rest", "endpoint", "http", "service"],
        "analysis": ["analyze", "analysis", "insight", "metrics", "report"],
        "summarization": ["summarize", "summary", "brief", "digest"],
        "infrastructure": ["terraform", "azure", "cloud", "kubernetes", "iac"],
        "documentation": ["document", "docs", "readme", "guide"],
        "repository": ["github", "repository", "repo", "pull request", "commit"],
    }

    _KEYWORD_TOOLS: dict[str, list[str]] = {
        "python": ["python", "script", "code"],
        "filesystem": ["file", "folder", "directory", "path", "local"],
        "rest": ["api", "rest", "http", "endpoint", "webhook"],
        "knowledge_search": ["knowledge", "source", "reference", "wiki"],
        "memory": ["memory", "history", "context", "prior"],
        "document_search": ["document", "pdf", "txt", "doc"],
        "github": ["github", "repo", "pull request", "issue", "commit"],
        "sharepoint": ["sharepoint", "site", "m365"],
        "upload_store": ["upload", "ingest", "dataset"],
    }

    _KEYWORD_KNOWLEDGE: dict[str, list[str]] = {
        "project_memory": ["project", "history", "context"],
        "personal_memory": ["personal", "preference", "style"],
        "rag": ["document", "knowledge", "source", "search", "retrieve"],
        "github": ["github", "repository", "commit", "codebase"],
        "sharepoint": ["sharepoint", "site", "intranet"],
        "uploads": ["upload", "files", "documents"],
    }

    def infer_required_capabilities(self, text: str) -> list[str]:
        """Infer required capabilities from goal/task text."""
        lowered = text.lower()
        required: list[str] = []
        for capability, keywords in self._KEYWORD_CAPABILITIES.items():
            if any(keyword in lowered for keyword in keywords):
                required.append(capability)
        if not required:
            required.append("general")
        return required

    def infer_tools(self, text: str) -> list[str]:
        """Infer likely tool choices from task text."""
        lowered = text.lower()
        selected: list[str] = []
        for tool, keywords in self._KEYWORD_TOOLS.items():
            if any(keyword in lowered for keyword in keywords):
                selected.append(tool)
        if not selected:
            selected = ["knowledge_search", "memory"]
        return selected

    def infer_knowledge_sources(self, text: str) -> list[str]:
        """Infer knowledge source classes required for the mission."""
        lowered = text.lower()
        selected: list[str] = []
        for source, keywords in self._KEYWORD_KNOWLEDGE.items():
            if any(keyword in lowered for keyword in keywords):
                selected.append(source)
        if not selected:
            selected = ["project_memory", "rag"]
        return selected

    def infer_memory_modes(self, text: str) -> list[str]:
        """Infer memory scopes required by mission intent."""
        lowered = text.lower()
        modes: list[str] = ["project_memory"]
        if "history" in lowered or "previous" in lowered or "prior" in lowered:
            modes.append("conversation_memory")
        if "preference" in lowered or "style" in lowered:
            modes.append("personal_memory")
        return modes

    def score_agents_for_task(
        self,
        *,
        task_text: str,
        task_tools: list[str],
        task_knowledge: list[str],
        agents: list[dict[str, Any]],
        workload: dict[str, int],
        success: dict[str, float],
    ) -> list[dict[str, Any]]:
        """Return ranked capability scores for candidate agents."""
        required_caps = set(self.infer_required_capabilities(task_text))
        rankings: list[dict[str, Any]] = []
        for agent in agents:
            agent_id = str(agent.get("id", "")).strip()
            if not agent_id:
                continue
            capabilities = {
                str(item).lower() for item in list(agent.get("capabilities", []))
            }
            tools = {str(item).lower() for item in list(agent.get("tools_allowed", []))}
            knowledge = {
                str(item).lower() for item in list(agent.get("knowledge_sources", []))
            }
            tags = {str(item).lower() for item in list(agent.get("tags", []))}

            cap_overlap = len(required_caps.intersection(capabilities or {"general"}))
            cap_score = cap_overlap / max(1, len(required_caps))
            tool_overlap = len(
                {tool.lower() for tool in task_tools}.intersection(tools)
            )
            tool_score = tool_overlap / max(1, len(task_tools))
            knowledge_overlap = len(
                {source.lower() for source in task_knowledge}.intersection(knowledge)
            )
            knowledge_score = knowledge_overlap / max(1, len(task_knowledge))

            workload_penalty = min(
                1.0, max(0.0, float(workload.get(agent_id, 0)) / 10.0)
            )
            workload_score = 1.0 - workload_penalty
            history_score = min(1.0, max(0.0, float(success.get(agent_id, 0.5))))

            bonus = 0.0
            if "general" in capabilities:
                bonus += 0.03
            if required_caps.intersection(tags):
                bonus += 0.05

            score = (
                (0.45 * cap_score)
                + (0.18 * tool_score)
                + (0.12 * knowledge_score)
                + (0.15 * history_score)
                + (0.10 * workload_score)
                + bonus
            )
            score = min(1.0, max(0.0, score))

            rankings.append(
                {
                    "agent_id": agent_id,
                    "score": round(score, 4),
                    "capability_score": round(cap_score, 4),
                    "tool_score": round(tool_score, 4),
                    "knowledge_score": round(knowledge_score, 4),
                    "history_score": round(history_score, 4),
                    "workload_score": round(workload_score, 4),
                    "capabilities": sorted(capabilities),
                    "tags": sorted(tags),
                    "rationale": (
                        "Selected based on capability fit, tool alignment, knowledge alignment, "
                        "historical reliability, and current workload."
                    ),
                }
            )

        rankings.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
        return rankings


class AutonomousPlanner:
    """Builds mission plans, task graphs, and autonomous execution recommendations."""

    def __init__(self) -> None:
        self._scoring = CapabilityScoringEngine()

    def plan(self, context: PlannerContext) -> dict[str, Any]:
        """Generate a full autonomous mission plan from a natural-language goal."""
        goal = context.goal.strip()
        mission = {
            "title": goal if len(goal) <= 120 else f"{goal[:117]}...",
            "created_at": datetime.now(UTC).isoformat(),
        }

        objectives = self._objectives_for_goal(goal)
        risks = self._risks_for_goal(goal)
        constraints = list(context.constraints)
        strategy = self._strategy_for_goal(goal)
        task_graph = self._task_graph(goal)

        capability_scores: list[dict[str, Any]] = []
        selected_agents: list[str] = []
        selected_tools: set[str] = set()
        selected_knowledge: set[str] = set()
        selected_memories: set[str] = set()
        temporary_agents: list[dict[str, Any]] = []
        governance_reasons: list[str] = []

        for task in task_graph:
            task_text = str(task.get("description", ""))
            task_tools = self._scoring.infer_tools(task_text)
            task_knowledge = self._scoring.infer_knowledge_sources(task_text)
            task_memory = self._scoring.infer_memory_modes(task_text)

            selected_tools.update(task_tools)
            selected_knowledge.update(task_knowledge)
            selected_memories.update(task_memory)

            ranking = self._scoring.score_agents_for_task(
                task_text=task_text,
                task_tools=task_tools,
                task_knowledge=task_knowledge,
                agents=context.agents,
                workload=context.agent_workload,
                success=context.agent_success,
            )
            capability_scores.append(
                {
                    "task_id": task.get("task_id", ""),
                    "task": task.get("title", ""),
                    "required_capabilities": self._scoring.infer_required_capabilities(
                        task_text
                    ),
                    "candidates": ranking,
                    "selected_agent_id": ranking[0]["agent_id"] if ranking else "",
                    "confidence": ranking[0]["score"] if ranking else 0.0,
                    "tools": task_tools,
                    "knowledge": task_knowledge,
                    "memory": task_memory,
                }
            )

            if ranking and float(ranking[0].get("score", 0.0)) >= 0.6:
                selected_agents.append(str(ranking[0]["agent_id"]))
            else:
                temporary_agents.append(
                    self._temporary_agent_for_task(
                        task_id=str(task.get("task_id", "")),
                        title=str(task.get("title", "Task")),
                        required_capabilities=list(
                            self._scoring.infer_required_capabilities(task_text)
                        ),
                        tools=task_tools,
                    )
                )

            if any(
                tool in {"rest", "filesystem", "github", "sharepoint"}
                for tool in task_tools
            ):
                governance_reasons.append(
                    f"Task {task.get('task_id', '')} uses external or side-effect tools."
                )

        workflow_decision = self._workflow_reuse(goal, context.workflows)
        requires_approval = bool(governance_reasons)
        average_confidence = self._average_confidence(capability_scores)
        if average_confidence < 0.65:
            governance_reasons.append("Low aggregate confidence in selected agents.")
            requires_approval = True

        estimated_runtime_ms = float(len(task_graph) * 18000)
        estimated_cost = round(len(task_graph) * 0.01, 4)

        recommendations = self._recommendations(
            capability_scores=capability_scores,
            workflow_decision=workflow_decision,
            selected_knowledge=sorted(selected_knowledge),
        )

        return {
            "mission": mission,
            "objectives": objectives,
            "constraints": constraints,
            "risks": risks,
            "execution_strategy": strategy,
            "task_graph": task_graph,
            "dependencies": self._dependencies(task_graph),
            "parallel_opportunities": self._parallel_groups(task_graph),
            "estimated_runtime_ms": estimated_runtime_ms,
            "estimated_cost": estimated_cost,
            "required_approvals": governance_reasons,
            "requires_approval": requires_approval,
            "workflow_reuse": workflow_decision,
            "capability_scores": capability_scores,
            "selected_agents": sorted(set(selected_agents)),
            "selected_tools": sorted(selected_tools),
            "selected_knowledge": sorted(selected_knowledge),
            "selected_memories": sorted(selected_memories),
            "temporary_agents": temporary_agents,
            "model_routing": {
                "planning": "planner",
                "reasoning": "reasoner",
                "coding": "coder",
                "vision": "vision",
                "summarization": "summarizer",
            },
            "recommendations": recommendations,
            "explanation": {
                "approach": "Goal decomposed into lifecycle tasks and matched to best-fit agents.",
                "selection_signals": [
                    "capabilities",
                    "tools",
                    "knowledge_sources",
                    "workload",
                    "historical_success",
                    "confidence",
                    "tags",
                ],
            },
        }

    @staticmethod
    def _objectives_for_goal(goal: str) -> list[str]:
        lowered = goal.lower()
        objectives = [
            "Clarify requirements and constraints",
            "Plan execution strategy",
            "Execute tasks with verifiable artifacts",
            "Validate outputs against mission goal",
            "Deliver final summary with evidence",
        ]
        if "api" in lowered:
            objectives.insert(2, "Design API surface and contract")
        if "summar" in lowered:
            objectives.insert(2, "Extract key points and confidence-weighted insights")
        return objectives

    @staticmethod
    def _risks_for_goal(goal: str) -> list[str]:
        lowered = goal.lower()
        risks = [
            "Ambiguous requirements could produce low-quality execution.",
            "Knowledge gaps may reduce confidence of results.",
        ]
        if any(token in lowered for token in ["terraform", "azure", "deploy"]):
            risks.append("Infrastructure actions can affect external environments.")
        if any(token in lowered for token in ["delete", "write", "modify"]):
            risks.append("Mutation operations may require human approval.")
        return risks

    @staticmethod
    def _strategy_for_goal(goal: str) -> dict[str, Any]:
        return {
            "mode": "autonomous-supervised",
            "high_level": [
                "decompose-goal",
                "rank-agents",
                "choose-tools-and-knowledge",
                "execute-with-retries",
                "validate-and-deliver",
            ],
            "goal": goal,
        }

    def _task_graph(self, goal: str) -> list[dict[str, Any]]:
        phases = [
            "Requirements",
            "Research",
            "Architecture",
            "Implementation",
            "Validation",
            "Documentation",
            "Delivery",
        ]
        tasks: list[dict[str, Any]] = []
        for index, phase in enumerate(phases, start=1):
            task_id = f"task-{index}"
            tasks.append(
                {
                    "task_id": task_id,
                    "title": phase,
                    "description": f"{phase}: {goal}",
                    "depends_on": [] if index == 1 else [f"task-{index - 1}"],
                }
            )

        # Explicitly model a parallel opportunity for research and architecture.
        tasks[2]["depends_on"] = ["task-1"]
        tasks[3]["depends_on"] = ["task-1"]
        tasks[4]["depends_on"] = ["task-2", "task-3"]
        return tasks

    @staticmethod
    def _dependencies(task_graph: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "task_id": str(task.get("task_id", "")),
                "depends_on": [str(item) for item in task.get("depends_on", [])],
            }
            for task in task_graph
        ]

    @staticmethod
    def _parallel_groups(task_graph: list[dict[str, Any]]) -> list[list[str]]:
        groups: dict[str, list[str]] = {}
        for task in task_graph:
            deps = task.get("depends_on", [])
            key = "|".join(sorted(str(dep) for dep in deps))
            groups.setdefault(key, []).append(str(task.get("task_id", "")))
        return [group for group in groups.values() if len(group) > 1]

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        tokens = [piece.strip().lower() for piece in text.replace("-", " ").split()]
        return {token for token in tokens if len(token) >= 3}

    def _workflow_reuse(
        self, goal: str, workflows: list[dict[str, Any]]
    ) -> dict[str, Any]:
        goal_tokens = self._tokenize(goal)
        candidates: list[dict[str, Any]] = []
        for workflow in workflows:
            workflow_id = str(workflow.get("id", ""))
            haystack = " ".join(
                [
                    str(workflow.get("name", "")),
                    str(workflow.get("description", "")),
                    " ".join(
                        str(node.get("name", "")) for node in workflow.get("nodes", [])
                    ),
                ]
            )
            workflow_tokens = self._tokenize(haystack)
            overlap = len(goal_tokens.intersection(workflow_tokens))
            score = overlap / max(1, len(goal_tokens))
            candidates.append(
                {
                    "workflow_id": workflow_id,
                    "score": round(score, 4),
                    "reason": "Keyword overlap between mission goal and workflow semantics.",
                }
            )

        candidates.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
        selected = candidates[0] if candidates else {"workflow_id": "", "score": 0.0}
        return {
            "reuse": bool(float(selected.get("score", 0.0)) >= 0.35),
            "selected_workflow_id": str(selected.get("workflow_id", "")),
            "confidence": float(selected.get("score", 0.0)),
            "alternatives": candidates[:5],
        }

    @staticmethod
    def _temporary_agent_for_task(
        *,
        task_id: str,
        title: str,
        required_capabilities: list[str],
        tools: list[str],
    ) -> dict[str, Any]:
        return {
            "agent_id": f"temp-{task_id}",
            "role": f"Temporary {title} Specialist",
            "lifecycle": "temporary",
            "required_capabilities": required_capabilities,
            "tools_allowed": tools,
            "created_at": datetime.now(UTC).isoformat(),
            "status": "created",
        }

    @staticmethod
    def _average_confidence(capability_scores: list[dict[str, Any]]) -> float:
        if not capability_scores:
            return 0.0
        values = [float(item.get("confidence", 0.0)) for item in capability_scores]
        return sum(values) / max(1, len(values))

    @staticmethod
    def _recommendations(
        *,
        capability_scores: list[dict[str, Any]],
        workflow_decision: dict[str, Any],
        selected_knowledge: list[str],
    ) -> list[dict[str, Any]]:
        recommendations: list[dict[str, Any]] = []

        low_confidence = [
            item
            for item in capability_scores
            if float(item.get("confidence", 0.0)) < 0.65
        ]
        if low_confidence:
            recommendations.append(
                {
                    "type": "missing_agent",
                    "message": "One or more tasks have low-confidence agent matches.",
                    "tasks": [item.get("task_id", "") for item in low_confidence],
                }
            )

        if not bool(workflow_decision.get("reuse", False)):
            recommendations.append(
                {
                    "type": "better_workflow",
                    "message": "No strong workflow match was found. Consider saving this mission as a reusable template.",
                }
            )

        if "rag" not in selected_knowledge:
            recommendations.append(
                {
                    "type": "missing_knowledge",
                    "message": "RAG knowledge is not selected; add relevant documents for stronger grounding.",
                }
            )

        recommendations.append(
            {
                "type": "optimization",
                "message": "Parallelize independent research and architecture tasks to reduce mission runtime.",
            }
        )
        return recommendations
