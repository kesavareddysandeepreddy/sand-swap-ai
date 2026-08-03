import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { workflowsApi } from "../api/workflows";
import type { WorkflowRecord, WorkflowRunRecord } from "../types/api";

export const WorkflowRunsPage = () => {
    const navigate = useNavigate();
    const [workflows, setWorkflows] = useState<WorkflowRecord[]>([]);
    const [selectedWorkflowId, setSelectedWorkflowId] = useState<string>("");
    const [runs, setRuns] = useState<WorkflowRunRecord[]>([]);
    const [inputPayload, setInputPayload] = useState('{"topic":"release"}');
    const [waitForCompletion, setWaitForCompletion] = useState(true);
    const [isLoading, setIsLoading] = useState(false);
    const [isExecuting, setIsExecuting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const selectedWorkflow = useMemo(
        () => workflows.find((item) => item.id === selectedWorkflowId) ?? null,
        [selectedWorkflowId, workflows]
    );

    const loadWorkflows = useCallback(async () => {
        try {
            const data = await workflowsApi.list();
            setWorkflows(data);
            if (!selectedWorkflowId && data.length > 0) {
                setSelectedWorkflowId(data[0].id);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load workflows.");
        }
    }, [selectedWorkflowId]);

    const loadRuns = async (workflowId: string) => {
        setIsLoading(true);
        setError(null);
        try {
            const data = workflowId
                ? await workflowsApi.listRuns(workflowId)
                : await workflowsApi.listRecentRuns(40);
            setRuns(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load runs.");
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        void loadWorkflows();
    }, [loadWorkflows]);

    useEffect(() => {
        void loadRuns(selectedWorkflowId);
    }, [selectedWorkflowId]);

    const executeWorkflow = async () => {
        if (!selectedWorkflow) {
            return;
        }
        setIsExecuting(true);
        setError(null);
        try {
            const parsed = JSON.parse(inputPayload) as Record<string, unknown>;
            const response = await workflowsApi.execute(selectedWorkflow.id, {
                input_payload: parsed,
                wait_for_completion: waitForCompletion,
            });
            await loadRuns(selectedWorkflow.id);
            navigate(`/workflows/monitor/${response.run_id}`);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to execute workflow.");
        } finally {
            setIsExecuting(false);
        }
    };

    const cancelRun = async (runId: string) => {
        setError(null);
        try {
            await workflowsApi.cancelRun(runId);
            await loadRuns(selectedWorkflowId);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to cancel run.");
        }
    };

    return (
        <section className="workflow-page">
            <header className="workflow-page__header">
                <div>
                    <h1>Workflow Runs</h1>
                    <p>Launch runs and inspect execution states in real time.</p>
                </div>
                <div className="workflow-page__actions">
                    <button type="button" onClick={() => loadRuns(selectedWorkflowId)}>
                        Refresh
                    </button>
                </div>
            </header>

            {error ? <p className="workflow-error">{error}</p> : null}

            <article className="workflow-card">
                <h2>Execute</h2>
                <div className="workflow-form-row">
                    <select
                        value={selectedWorkflowId}
                        onChange={(event) => setSelectedWorkflowId(event.target.value)}
                    >
                        <option value="">All workflows</option>
                        {workflows.map((workflow) => (
                            <option key={workflow.id} value={workflow.id}>
                                {workflow.name}
                            </option>
                        ))}
                    </select>
                    <label className="workflow-inline-check">
                        <input
                            type="checkbox"
                            checked={waitForCompletion}
                            onChange={(event) => setWaitForCompletion(event.target.checked)}
                        />
                        Wait for completion
                    </label>
                    <button
                        type="button"
                        onClick={executeWorkflow}
                        disabled={!selectedWorkflow || isExecuting}
                    >
                        Run Workflow
                    </button>
                </div>
                <textarea
                    value={inputPayload}
                    onChange={(event) => setInputPayload(event.target.value)}
                    rows={5}
                    aria-label="Workflow input payload"
                />
            </article>

            <article className="workflow-card">
                <h2>Run History</h2>
                {isLoading ? <p>Loading runs...</p> : null}
                <ul className="workflow-run-list">
                    {runs.map((run) => (
                        <li key={run.id}>
                            <div>
                                <strong>{run.status}</strong>
                                <p>
                                    {run.id} · {run.workflow_id}
                                </p>
                            </div>
                            <div className="workflow-run-list__actions">
                                <button
                                    type="button"
                                    onClick={() => navigate(`/workflows/monitor/${run.id}`)}
                                >
                                    Monitor
                                </button>
                                <button
                                    type="button"
                                    onClick={() => void cancelRun(run.id)}
                                    disabled={run.status === "succeeded" || run.status === "failed"}
                                >
                                    Cancel
                                </button>
                            </div>
                        </li>
                    ))}
                </ul>
            </article>
        </section>
    );
};
