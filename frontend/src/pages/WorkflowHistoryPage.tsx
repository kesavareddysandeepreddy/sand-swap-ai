import { useEffect, useState } from "react";

import { workflowsApi } from "../api/workflows";
import type { WorkflowRecord, WorkflowVersionResponse } from "../types/api";

export const WorkflowHistoryPage = () => {
    const [workflows, setWorkflows] = useState<WorkflowRecord[]>([]);
    const [selectedWorkflowId, setSelectedWorkflowId] = useState<string>("");
    const [versions, setVersions] = useState<WorkflowVersionResponse[]>([]);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const load = async () => {
            try {
                const data = await workflowsApi.list();
                setWorkflows(data);
                if (data.length > 0) {
                    setSelectedWorkflowId((previous) => previous || data[0].id);
                }
            } catch (err) {
                setError(err instanceof Error ? err.message : "Failed to load workflows.");
            }
        };
        void load();
    }, []);

    useEffect(() => {
        if (!selectedWorkflowId) {
            setVersions([]);
            return;
        }
        const loadVersions = async () => {
            try {
                const data = await workflowsApi.listVersions(selectedWorkflowId);
                setVersions(data);
            } catch (err) {
                setError(err instanceof Error ? err.message : "Failed to load version history.");
            }
        };
        void loadVersions();
    }, [selectedWorkflowId]);

    return (
        <section className="workflow-page">
            <header className="workflow-page__header">
                <div>
                    <h1>Workflow History</h1>
                    <p>Inspect versioned snapshots and audit workflow changes over time.</p>
                </div>
            </header>
            {error ? <p className="workflow-error">{error}</p> : null}
            <article className="workflow-card">
                <h2>Version Timeline</h2>
                <div className="workflow-form-row">
                    <select
                        value={selectedWorkflowId}
                        onChange={(event) => setSelectedWorkflowId(event.target.value)}
                    >
                        <option value="">Select workflow</option>
                        {workflows.map((workflow) => (
                            <option key={workflow.id} value={workflow.id}>
                                {workflow.name}
                            </option>
                        ))}
                    </select>
                </div>
                <ul className="workflow-version-list">
                    {versions.map((version) => (
                        <li key={version.id}>
                            <strong>v{version.version_number}</strong>
                            <p>{version.change_summary}</p>
                            <small>{new Date(version.created_at).toLocaleString()}</small>
                        </li>
                    ))}
                </ul>
            </article>
        </section>
    );
};
