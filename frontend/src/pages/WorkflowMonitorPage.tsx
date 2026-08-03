import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { workflowsApi } from "../api/workflows";
import type { WorkflowDashboardResponse, WorkflowRunRecord } from "../types/api";

export const WorkflowMonitorPage = () => {
    const params = useParams<{ runId?: string }>();
    const [runIdInput, setRunIdInput] = useState(params.runId ?? "");
    const [run, setRun] = useState<WorkflowRunRecord | null>(null);
    const [dashboard, setDashboard] = useState<WorkflowDashboardResponse | null>(null);
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

    const runAction = async (action: "approve" | "reject") => {
        if (!run) {
            return;
        }
        try {
            const nextRun = await workflowsApi.applyRunAction(run.id, {
                action,
                edited_input: {},
            });
            setRun(nextRun);
        } catch (err) {
            setError(err instanceof Error ? err.message : `Failed to ${action} run.`);
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
                    <button type="button" onClick={() => run && void workflowsApi.cancelRun(run.id)}>
                        Cancel
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
            </div>

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
                                {message.sender} → {message.receiver}
                            </strong>
                            <p>{message.reasoning || "No reasoning provided."}</p>
                            <small>{new Date(message.timestamp).toLocaleString()}</small>
                        </li>
                    )) ?? <li>No messages yet.</li>}
                </ul>
            </article>
        </section>
    );
};
