from __future__ import annotations

from backend.agent_orchestration.runtime.autonomous_planner import (
    AutonomousPlanner,
    CapabilityScoringEngine,
    PlannerContext,
)


def test_capability_scoring_ranks_python_agent_higher_for_python_task() -> None:
    engine = CapabilityScoringEngine()
    rankings = engine.score_agents_for_task(
        task_text="Build a Python REST API service",
        task_tools=["python", "rest"],
        task_knowledge=["project_memory", "rag"],
        agents=[
            {
                "id": "python-agent",
                "capabilities": ["python", "api", "general"],
                "tools_allowed": ["python", "rest"],
                "knowledge_sources": ["project_memory", "rag"],
                "tags": ["backend"],
            },
            {
                "id": "general-agent",
                "capabilities": ["general"],
                "tools_allowed": ["knowledge_search"],
                "knowledge_sources": ["project_memory"],
                "tags": ["general"],
            },
        ],
        workload={"python-agent": 1, "general-agent": 1},
        success={"python-agent": 0.9, "general-agent": 0.6},
    )

    assert len(rankings) == 2
    assert rankings[0]["agent_id"] == "python-agent"
    assert rankings[0]["score"] > rankings[1]["score"]


def test_autonomous_planner_generates_task_graph_and_recommendations() -> None:
    planner = AutonomousPlanner()
    plan = planner.plan(
        PlannerContext(
            goal="Analyze our GitHub repository and summarize architecture",
            constraints=["Read-only operations"],
            context={"priority": "high"},
            workflows=[
                {
                    "id": "wf-1",
                    "name": "Repository Analysis Workflow",
                    "description": "Analyze repository and create summary",
                    "nodes": [{"id": "n1", "name": "Analyze", "node_type": "Agent"}],
                }
            ],
            agents=[
                {
                    "id": "repo-agent",
                    "name": "Repository Agent",
                    "capabilities": ["repository", "analysis", "summarization"],
                    "tags": ["repository", "analysis"],
                    "tools_allowed": ["github", "knowledge_search"],
                    "knowledge_sources": ["github", "rag", "project_memory"],
                }
            ],
            agent_workload={"repo-agent": 0},
            agent_success={"repo-agent": 0.93},
        )
    )

    assert isinstance(plan["mission"], dict)
    assert isinstance(plan["objectives"], list)
    assert isinstance(plan["task_graph"], list)
    assert len(plan["task_graph"]) >= 5
    assert isinstance(plan["capability_scores"], list)
    assert isinstance(plan["recommendations"], list)
    assert "workflow_reuse" in plan
    assert "model_routing" in plan
