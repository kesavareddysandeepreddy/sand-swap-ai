import { useCallback, useEffect, useMemo, useState } from "react";

import { workflowsApi } from "../api/workflows";
import type {
    AutonomousMissionRecord,
    MissionControlDashboard,
    MissionTemplateRecord,
} from "../types/api";

const parseConstraints = (value: string): string[] =>
    value
        .split("\n")
        .map((item) => item.trim())
        .filter((item) => item.length > 0);

export const MissionControlPage = () => {
    const [goal, setGoal] = useState("Analyze our GitHub repository and propose optimizations");
    const [constraints, setConstraints] = useState("No destructive changes\nPrefer reusable workflows");
    const [missions, setMissions] = useState<AutonomousMissionRecord[]>([]);
    const [selectedMissionId, setSelectedMissionId] = useState("");
    const [selectedMission, setSelectedMission] = useState<AutonomousMissionRecord | null>(null);
    const [templates, setTemplates] = useState<MissionTemplateRecord[]>([]);
    const [dashboard, setDashboard] = useState<MissionControlDashboard | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isLaunching, setIsLaunching] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const selectedMissionPlanner = useMemo(
        () => (selectedMission?.planner_output ?? {}) as Record<string, unknown>,
        [selectedMission]
    );

    const selectedMissionScores = useMemo(() => {
        const entries = selectedMission?.capability_scores ?? [];
        return entries.filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null);
    }, [selectedMission]);

    const load = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const [missionList, missionDashboard, templateList] = await Promise.all([
                workflowsApi.listMissions(50),
                workflowsApi.getMissionDashboard(),
                workflowsApi.listMissionTemplates(),
            ]);
            setMissions(missionList);
            setDashboard(missionDashboard);
            setTemplates(templateList);
            if (!selectedMissionId && missionList.length > 0) {
                setSelectedMissionId(missionList[0].mission_id);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load Mission Control data.");
        } finally {
            setIsLoading(false);
        }
    }, [selectedMissionId]);

    const launchMission = async () => {
        if (!goal.trim()) {
            setError("Mission goal is required.");
            return;
        }
        setIsLaunching(true);
        setError(null);
        try {
            const mission = await workflowsApi.createMission({
                goal: goal.trim(),
                constraints: parseConstraints(constraints),
                context: {},
                auto_execute: true,
                wait_for_completion: false,
            });
            setSelectedMissionId(mission.mission_id);
            await load();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to launch mission.");
        } finally {
            setIsLaunching(false);
        }
    };

    const saveTemplate = async () => {
        if (!selectedMission) {
            return;
        }
        try {
            await workflowsApi.createMissionTemplate({
                name: `Template: ${selectedMission.goal.slice(0, 36)}`,
                description: "Saved from autonomous mission planner output",
                template: selectedMission.planner_output,
            });
            await load();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to save mission template.");
        }
    };

    useEffect(() => {
        void load();
    }, [load]);

    useEffect(() => {
        if (!selectedMissionId) {
            setSelectedMission(null);
            return;
        }
        const next = missions.find((item) => item.mission_id === selectedMissionId) ?? null;
        setSelectedMission(next);
    }, [missions, selectedMissionId]);

    return (
        <section className="workflow-page">
            <header className="workflow-page__header">
                <div>
                    <h1>Mission Control</h1>
                    <p>Autonomous planning, execution reasoning, and enterprise mission oversight.</p>
                </div>
                <div className="workflow-page__actions">
                    <button type="button" onClick={() => void load()}>
                        Refresh
                    </button>
                </div>
            </header>

            {error ? <p className="workflow-error">{error}</p> : null}
            {isLoading ? <p>Loading mission control...</p> : null}

            <article className="workflow-card">
                <h2>Launch Autonomous Mission</h2>
                <div className="workflow-form-row">
                    <input
                        value={goal}
                        onChange={(event) => setGoal(event.target.value)}
                        placeholder="Mission goal"
                    />
                    <button type="button" onClick={() => void launchMission()} disabled={isLaunching}>
                        {isLaunching ? "Launching..." : "Launch Mission"}
                    </button>
                </div>
                <textarea
                    rows={4}
                    value={constraints}
                    onChange={(event) => setConstraints(event.target.value)}
                    placeholder="Constraints, one per line"
                />
            </article>

            <div className="workflow-grid">
                <article className="workflow-card">
                    <h2>Dashboard</h2>
                    {!dashboard ? <p>No mission dashboard data.</p> : null}
                    {dashboard ? (
                        <ul>
                            <li>Running missions: {dashboard.running_missions}</li>
                            <li>Planned missions: {dashboard.planned_missions}</li>
                            <li>Completed missions: {dashboard.completed_missions}</li>
                            <li>Failed missions: {dashboard.failed_missions}</li>
                            <li>Mission success rate: {(dashboard.mission_success_rate * 100).toFixed(1)}%</li>
                            <li>Average planned runtime: {Math.round(dashboard.average_runtime_ms)} ms</li>
                            <li>Active runs: {dashboard.active_runs}</li>
                            <li>Retries: {dashboard.retries}</li>
                        </ul>
                    ) : null}
                </article>

                <article className="workflow-card">
                    <h2>Missions</h2>
                    <div className="workflow-form-row">
                        <select
                            value={selectedMissionId}
                            onChange={(event) => setSelectedMissionId(event.target.value)}
                        >
                            <option value="">Select mission</option>
                            {missions.map((mission) => (
                                <option key={mission.mission_id} value={mission.mission_id}>
                                    {mission.goal.slice(0, 64)} ({mission.status})
                                </option>
                            ))}
                        </select>
                        <button type="button" onClick={() => void saveTemplate()} disabled={!selectedMission}>
                            Save Template
                        </button>
                    </div>
                    <ul className="workflow-version-list">
                        {missions.map((mission) => (
                            <li key={mission.mission_id}>
                                <strong>{mission.goal}</strong>
                                <p>
                                    Status: {mission.status}
                                    {mission.run_id ? ` · Run ${mission.run_id}` : ""}
                                </p>
                            </li>
                        ))}
                    </ul>
                </article>
            </div>

            <article className="workflow-card">
                <h2>Planner Output</h2>
                {!selectedMission ? <p>Select a mission to inspect planner decisions.</p> : null}
                {selectedMission ? (
                    <>
                        <p>
                            Workflow reuse candidate: {selectedMission.selected_workflow_id || "none"}
                        </p>
                        <p>
                            Temporary agents: {selectedMission.temporary_agents.length}
                        </p>
                        <pre>{JSON.stringify(selectedMissionPlanner, null, 2)}</pre>
                    </>
                ) : null}
            </article>

            <article className="workflow-card">
                <h2>Capability Ranking</h2>
                {selectedMissionScores.length === 0 ? <p>No capability scoring data available.</p> : null}
                <ul className="workflow-version-list">
                    {selectedMissionScores.map((entry, index) => (
                        <li key={`${String(entry.task_id ?? "task")}-${index}`}>
                            <strong>{String(entry.task ?? "Task")}</strong>
                            <p>
                                Selected agent: {String(entry.selected_agent_id ?? "none")} · Confidence: {String(entry.confidence ?? "0")}
                            </p>
                            <pre>{JSON.stringify(entry.candidates ?? [], null, 2)}</pre>
                        </li>
                    ))}
                </ul>
            </article>

            <article className="workflow-card">
                <h2>Execution Recommendations</h2>
                {!selectedMission ? <p>No mission selected.</p> : null}
                {selectedMission ? (
                    <ul className="workflow-version-list">
                        {(selectedMission.execution_recommendations ?? []).map((item, index) => (
                            <li key={`${String(item.type ?? "rec")}-${index}`}>
                                <strong>{String(item.type ?? "recommendation")}</strong>
                                <p>{String(item.message ?? "")}</p>
                            </li>
                        ))}
                    </ul>
                ) : null}
            </article>

            <article className="workflow-card">
                <h2>Reusable Templates</h2>
                {templates.length === 0 ? <p>No templates saved yet.</p> : null}
                <ul className="workflow-version-list">
                    {templates.map((template) => (
                        <li key={template.template_id}>
                            <strong>{template.name}</strong>
                            <p>
                                Version {template.version} · {template.description}
                            </p>
                        </li>
                    ))}
                </ul>
            </article>
        </section>
    );
};
