import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { workflowsApi } from "../api/workflows";
import type {
    WorkflowDashboardResponse,
    WorkflowDebuggerResponse,
    WorkflowNodeDebuggerResponse,
    WorkflowRunRecord,
} from "../types/api";

export const WorkflowMonitorPage = () => {
    const params = useParams<{ runId?: string }>();
    const [runIdInput, setRunIdInput] = useState(params.runId ?? "");
    const [run, setRun] = useState<WorkflowRunRecord | null>(null);
    const [dashboard, setDashboard] = useState<WorkflowDashboardResponse | null>(null);
    const [debuggerData, setDebuggerData] = useState<WorkflowDebuggerResponse | null>(null);
    const [selectedNodeDebug, setSelectedNodeDebug] = useState<WorkflowNodeDebuggerResponse | null>(null);
    const [streamEnabled, setStreamEnabled] = useState(true);
    const [streamEvents, setStreamEvents] = useState<Array<Record<string, unknown>>>([]);
    const [agentRegistry, setAgentRegistry] = useState<Record<string, unknown> | null>(null);
    const [runtimeMessages, setRuntimeMessages] = useState<Array<Record<string, unknown>>>([]);
    const [runtimeTimeline, setRuntimeTimeline] = useState<Array<Record<string, unknown>>>([]);
    const [runtimeArtifacts, setRuntimeArtifacts] = useState<Array<Record<string, unknown>>>([]);
    const [supervisorState, setSupervisorState] = useState<Record<string, unknown> | null>(null);
    const [retryPolicy, setRetryPolicy] = useState("immediate");
    const [retryTaskId, setRetryTaskId] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const canApprove = useMemo(() => run?.status === "waiting_approval", [run]);

    const load = async (runId: string) => {
        if (!runId.trim()) {
            return;
        }
        setIsLoading(true);
        setError(null);
        try {
            const [runData, dashboardData] = await Promise.all([
                workflowsApi.getRun(runId.trim()),
                workflowsApi.getDashboard(),
            ]);
            setRun(runData);
            setDashboard(dashboardData);
            const [
                debug,
                registry,
                messages,
                timeline,
                artifacts,
                supervisor,
            ] = await Promise.all([
                workflowsApi.getRunDebugger(runId.trim()),
                workflowsApi.getRunAgentRegistry(runId.trim()),
                workflowsApi.getRunMessages(runId.trim()),
                workflowsApi.getRunTimeline(runId.trim()),
                workflowsApi.getRunArtifacts(runId.trim()),
                workflowsApi.getRunSupervisor(runId.trim()),
            ]);
            setDebuggerData(debug);
            setAgentRegistry(registry.registry);
            setRuntimeMessages(messages.messages);
            setRuntimeTimeline(timeline.timeline);
            setRuntimeArtifacts(artifacts.artifacts);
            setSupervisorState(supervisor.supervisor);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load run monitor.");
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        if (params.runId) {
            setRunIdInput(params.runId);
            void load(params.runId);
        }
    }, [params.runId]);

    useEffect(() => {
        if (!streamEnabled || !runIdInput.trim()) {
            return;
        }
        const source = new EventSource(workflowsApi.streamRunEventsUrl(runIdInput.trim()));

        const onUpdate = (event: MessageEvent) => {
            try {
                const payload = JSON.parse(event.data) as Record<string, unknown>;
                setStreamEvents((previous) => [...previous.slice(-99), payload]);
                const status = payload.status;
                const currentNodeId = payload.current_node_id;
                const pendingNodeId = payload.pending_node_id;
                if (typeof status === "string") {
                    setRun((previous) =>
                        previous
                            ? {
                                ...previous,
                                status,
                                current_node_id:
                                    typeof currentNodeId === "string"
                                        ? currentNodeId
                                        : previous.current_node_id,
                                pending_node_id:
                                    typeof pendingNodeId === "string"
                                        ? pendingNodeId
                                        : previous.pending_node_id,
                            }
                            : previous
                    );
                }
            } catch {
                // Ignore malformed stream payloads.
            }
        };

        source.addEventListener("workflow_update", onUpdate);
        source.addEventListener("workflow_completed", onUpdate);

        source.onerror = () => {
            setError((previous) => previous ?? "Live stream disconnected.");
        };

        return () => {
            source.close();
        };
    }, [runIdInput, streamEnabled]);

    const setRunFromMutation = (nextRun: WorkflowRunRecord) => {
        setRun(nextRun);
        setRunIdInput(nextRun.id);
    };

    const runAction = async (action: "approve" | "reject") => {
        if (!run) {
            return;
        }
        try {
            const nextRun = await workflowsApi.applyRunAction(run.id, {
                action,
                edited_input: {},
            });
            setRunFromMutation(nextRun);
        } catch (err) {
            setError(err instanceof Error ? err.message : `Failed to ${action} run.`);
        }
    };

    const pauseRun = async () => {
        if (!run) {
            return;
        }
        try {
            const nextRun = await workflowsApi.pauseRun(run.id);
            setRunFromMutation(nextRun);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to pause run.");
        }
    };

    const resumeRun = async () => {
        if (!run) {
            return;
        }
        try {
            const nextRun = await workflowsApi.resumeRun(run.id);
            setRunFromMutation(nextRun);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to resume run.");
        }
    };

    const loadNodeDebug = async (nodeId: string) => {
        if (!run) {
            return;
        }
        try {
            const details = await workflowsApi.getRunNodeDebugger(run.id, nodeId);
            setSelectedNodeDebug(details);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load node debugger.");
        }
    };

    const retryRun = async () => {
        if (!run) {
            return;
        }
        try {
            const nextRun = await workflowsApi.retryRun(run.id, {
                policy: retryPolicy,
                task_id: retryTaskId,
            });
            setRunFromMutation(nextRun);
            void load(nextRun.id);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to retry run.");
        }
    };

    return (
        <section className="workflow-page">
            <header className="workflow-page__header">
                <div>
                    <h1>Execution Monitor</h1>
                    <p>Track node-by-node execution, messages, and run control actions.</p>
                </div>
                <div className="workflow-page__actions">
                    <button type="button" onClick={() => void load(runIdInput)}>
                        Refresh
                    </button>
                    <label className="workflow-inline-check">
                        <input
                            type="checkbox"
                            checked={streamEnabled}
                            onChange={(event) => setStreamEnabled(event.target.checked)}
                        />
                        Live Stream
                    </label>
                </div>
            </header>

            <article className="workflow-card">
                <h2>Run Lookup</h2>
                <div className="workflow-form-row">
                    <input
                        value={runIdInput}
                        onChange={(event) => setRunIdInput(event.target.value)}
                        placeholder="Workflow run id"
                    />
                    <button type="button" onClick={() => void load(runIdInput)}>
                        Load Run
                    </button>
                    <button
                        type="button"
                        onClick={() => run && void workflowsApi.cancelRun(run.id).then(setRunFromMutation)}
                    >
                        Cancel
                    </button>
                    <button type="button" onClick={() => void pauseRun()} disabled={!run}>
                        Pause
                    </button>
                    <button type="button" onClick={() => void resumeRun()} disabled={!run}>
                        Resume
                    </button>
                    <select
                        value={retryPolicy}
                        onChange={(event) => setRetryPolicy(event.target.value)}
                    >
                        <option value="immediate">Retry Immediately</option>
                        <option value="later">Retry Later</option>
                        <option value="different_agent">Retry Different Agent</option>
                        <option value="escalate">Escalate</option>
                        <option value="abort">Abort</option>
                    </select>
                    <input
                        value={retryTaskId}
                        onChange={(event) => setRetryTaskId(event.target.value)}
                        placeholder="Task id (optional)"
                    />
                    <button type="button" onClick={() => void retryRun()} disabled={!run}>
                        Retry
                    </button>
                </div>
            </article>

            {error ? <p className="workflow-error">{error}</p> : null}
            {isLoading ? <p>Loading monitor...</p> : null}

            <div className="workflow-grid">
                <article className="workflow-card">
                    <h2>Run State</h2>
                    {!run ? <p>No run selected.</p> : null}
                    {run ? (
                        <>
                            <p>
                                Status: <strong>{run.status}</strong>
                            </p>
                            <p>Current node: {run.current_node_id || "n/a"}</p>
                            <p>Pending node: {run.pending_node_id || "n/a"}</p>
                            <p>Messages: {run.messages.length}</p>
                            <p>Duration: {Math.round(run.duration_ms)} ms</p>
                            {canApprove ? (
                                <div className="workflow-page__actions">
                                    <button type="button" onClick={() => void runAction("approve")}>
                                        Approve
                                    </button>
                                    <button type="button" onClick={() => void runAction("reject")}>
                                        Reject
                                    </button>
                                </div>
                            ) : null}
                        </>
                    ) : null}
                </article>

                <article className="workflow-card">
                    <h2>Dashboard</h2>
                    {!dashboard ? <p>No dashboard data.</p> : null}
                    {dashboard ? (
                        <ul>
                            <li>Running: {dashboard.running}</li>
                            <li>Queued: {dashboard.queued}</li>
                            <li>Succeeded: {dashboard.succeeded}</li>
                            <li>Failed: {dashboard.failed}</li>
                            <li>Avg runtime: {Math.round(dashboard.average_runtime_ms)} ms</li>
                        </ul>
                    ) : null}
                </article>

                <article className="workflow-card">
                    <h2>Debugger</h2>
                    {!debuggerData ? <p>No debugger payload loaded.</p> : null}
                    {debuggerData ? (
                        <>
                            <p>Timeline events: {debuggerData.timeline.length}</p>
                            <p>Debugger messages: {debuggerData.messages.length}</p>
                            <p>Node snapshots: {Object.keys(debuggerData.nodes).length}</p>
                        </>
                    ) : null}
                    {selectedNodeDebug ? (
                        <div>
                            <h3>Node Detail: {selectedNodeDebug.node_id}</h3>
                            <p>Status: {selectedNodeDebug.record.status}</p>
                            <p>Logs: {selectedNodeDebug.logs.length}</p>
                        </div>
                    ) : null}
                </article>

                <article className="workflow-card">
                    <h2>Supervisor</h2>
                    {!supervisorState ? <p>No supervisor state.</p> : null}
                    {supervisorState ? (
                        <pre>{JSON.stringify(supervisorState, null, 2)}</pre>
                    ) : null}
                </article>
            </div>

            <article className="workflow-card">
                <h2>Agent Registry</h2>
                {!agentRegistry ? <p>No registry data.</p> : null}
                {agentRegistry ? <pre>{JSON.stringify(agentRegistry, null, 2)}</pre> : null}
            </article>

            <article className="workflow-card">
                <h2>Node Timeline</h2>
                <ul className="workflow-version-list">
                    {run?.node_records.map((record) => (
                        <li key={`${record.node_id}-${record.started_at}`}>
                            <strong>{record.node_name}</strong>
                            <p>
                                {record.node_type} · {record.status} · {Math.round(record.duration_ms)} ms
                            </p>
                            {record.error ? <p>{record.error}</p> : null}
                            <button type="button" onClick={() => void loadNodeDebug(record.node_id)}>
                                Inspect Node
                            </button>
                        </li>
                    )) ?? <li>No node records yet.</li>}
                </ul>
            </article>

            <article className="workflow-card">
                <h2>Inter-Agent Messages</h2>
                <ul className="workflow-version-list">
                    {run?.messages.map((message) => (
                        <li key={`${message.timestamp}-${message.sender}-${message.receiver}`}>
                            <strong>
                                {(message.sender_agent || message.sender)} → {message.receiver_agent || message.receiver}
                            </strong>
                            <p>
                                {message.message_type || "StatusUpdate"}
                                {message.task_id ? ` · task ${message.task_id}` : ""}
                            </p>
                            <p>{message.reasoning_summary || message.reasoning || "No reasoning provided."}</p>
                            {message.thought ? <p>{message.thought}</p> : null}
                            <small>{new Date(message.timestamp).toLocaleString()}</small>
                        </li>
                    )) ?? <li>No messages yet.</li>}
                </ul>
            </article>

            <article className="workflow-card">
                <h2>Runtime Message Stream</h2>
                <div className="workflow-execution-events" role="log" aria-live="polite">
                    {runtimeMessages.length === 0 ? <p>No runtime messages yet.</p> : null}
                    {runtimeMessages.map((message, index) => (
                        <pre key={`${String(message.message_id ?? "msg")}-${index}`}>
                            {JSON.stringify(message, null, 2)}
                        </pre>
                    ))}
                </div>
            </article>

            <article className="workflow-card">
                <h2>Runtime Timeline</h2>
                <div className="workflow-execution-events" role="log" aria-live="polite">
                    {runtimeTimeline.length === 0 ? <p>No runtime timeline events yet.</p> : null}
                    {runtimeTimeline.map((event, index) => (
                        <pre key={`${String(event.timestamp ?? "timeline")}-${index}`}>
                            {JSON.stringify(event, null, 2)}
                        </pre>
                    ))}
                </div>
            </article>

            <article className="workflow-card">
                <h2>Artifact Explorer</h2>
                <div className="workflow-execution-events" role="log" aria-live="polite">
                    {runtimeArtifacts.length === 0 ? <p>No artifacts available.</p> : null}
                    {runtimeArtifacts.map((artifact, index) => (
                        <pre key={`${String(artifact.artifact_id ?? "artifact")}-${index}`}>
                            {JSON.stringify(artifact, null, 2)}
                        </pre>
                    ))}
                </div>
            </article>

            <article className="workflow-card">
                <h2>Live Events</h2>
                <div className="workflow-page__actions">
                    <button type="button" onClick={() => setStreamEvents([])}>
                        Clear
                    </button>
                </div>
                <div className="workflow-execution-events" role="log" aria-live="polite">
                    {streamEvents.length === 0 ? <p>No live events yet.</p> : null}
                    {streamEvents.map((event, index) => (
                        <pre key={`${String(event.run_id ?? "run")}-${index}`}>
                            {JSON.stringify(event, null, 2)}
                        </pre>
                    ))}
                </div>
            </article>
        </section>
    );
};
