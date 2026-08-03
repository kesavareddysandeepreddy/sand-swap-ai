import { useCallback, useEffect, useMemo, useState } from "react";

import { workflowsApi } from "../api/workflows";
import type {
    WorkflowRecord,
    WorkflowValidationResponse,
    WorkflowVersionResponse,
} from "../types/api";

export const WorkflowsPage = () => {
    const [workflows, setWorkflows] = useState<WorkflowRecord[]>([]);
    const [selectedWorkflowId, setSelectedWorkflowId] = useState<string>("");
    const [versions, setVersions] = useState<WorkflowVersionResponse[]>([]);
    const [validation, setValidation] = useState<WorkflowValidationResponse | null>(null);
    const [name, setName] = useState("New Workflow");
    const [description, setDescription] = useState("Orchestrates planner agent");
    const [isLoading, setIsLoading] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const selectedWorkflow = useMemo(
        () => workflows.find((item) => item.id === selectedWorkflowId) ?? null,
        [selectedWorkflowId, workflows]
    );

    const loadWorkflows = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const data = await workflowsApi.list();
            setWorkflows(data);
            if (!selectedWorkflowId && data.length > 0) {
                setSelectedWorkflowId(data[0].id);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load workflows.");
        } finally {
            setIsLoading(false);
        }
    }, [selectedWorkflowId]);

    useEffect(() => {
        void loadWorkflows();
    }, [loadWorkflows]);

    useEffect(() => {
        if (!selectedWorkflowId) {
            setVersions([]);
            setValidation(null);
            return;
        }
        const loadDetails = async () => {
            try {
                const [nextVersions, nextValidation] = await Promise.all([
                    workflowsApi.listVersions(selectedWorkflowId),
                    workflowsApi.validate(selectedWorkflowId),
                ]);
                setVersions(nextVersions);
                setValidation(nextValidation);
            } catch {
                setVersions([]);
                setValidation(null);
            }
        };
        void loadDetails();
    }, [selectedWorkflowId]);

    const createWorkflow = async () => {
        setIsSaving(true);
        setError(null);
        try {
            const created = await workflowsApi.create({
                name,
                description,
                enabled: true,
                nodes: [
                    { id: "start", node_type: "Start", name: "Start" },
                    {
                        id: "agent",
                        node_type: "Agent",
                        name: "Planner",
                        agent_id: "agent-1",
                        x: 280,
                        y: 140,
                    },
                    { id: "end", node_type: "End", name: "End", x: 520, y: 140 },
                ],
                edges: [
                    { id: "edge-start-agent", source_node_id: "start", target_node_id: "agent" },
                    { id: "edge-agent-end", source_node_id: "agent", target_node_id: "end" },
                ],
            });
            await loadWorkflows();
            setSelectedWorkflowId(created.id);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to create workflow.");
        } finally {
            setIsSaving(false);
        }
    };

    const deleteWorkflow = async () => {
        if (!selectedWorkflow) {
            return;
        }
        const confirmed = window.confirm(`Delete workflow "${selectedWorkflow.name}"?`);
        if (!confirmed) {
            return;
        }
        setError(null);
        try {
            await workflowsApi.deleteOne(selectedWorkflow.id);
            setSelectedWorkflowId("");
            await loadWorkflows();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to delete workflow.");
        }
    };

    return (
        <section className="workflow-page">
            <header className="workflow-page__header">
                <div>
                    <h1>Workflows</h1>
                    <p>Manage orchestration pipelines and inspect graph validity.</p>
                </div>
                <div className="workflow-page__actions">
                    <button type="button" onClick={loadWorkflows} disabled={isLoading}>
                        Refresh
                    </button>
                    <button type="button" onClick={deleteWorkflow} disabled={!selectedWorkflow}>
                        Delete
                    </button>
                </div>
            </header>

            <article className="workflow-page__create">
                <h2>Create Workflow</h2>
                <div className="workflow-form-row">
                    <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Name" />
                    <input
                        value={description}
                        onChange={(event) => setDescription(event.target.value)}
                        placeholder="Description"
                    />
                    <button type="button" onClick={createWorkflow} disabled={isSaving}>
                        Create
                    </button>
                </div>
            </article>

            {error ? <p className="workflow-error">{error}</p> : null}

            <div className="workflow-grid">
                <article className="workflow-card">
                    <h2>Catalog</h2>
                    {isLoading ? <p>Loading workflows...</p> : null}
                    <ul className="workflow-list">
                        {workflows.map((workflow) => (
                            <li key={workflow.id}>
                                <button
                                    type="button"
                                    onClick={() => setSelectedWorkflowId(workflow.id)}
                                    className={workflow.id === selectedWorkflowId ? "workflow-list__active" : ""}
                                >
                                    <strong>{workflow.name}</strong>
                                    <span>
                                        v{workflow.version} · {workflow.enabled ? "enabled" : "disabled"}
                                    </span>
                                </button>
                            </li>
                        ))}
                    </ul>
                </article>

                <article className="workflow-card">
                    <h2>Selected Workflow</h2>
                    {!selectedWorkflow ? <p>Select a workflow to inspect details.</p> : null}
                    {selectedWorkflow ? (
                        <>
                            <p>{selectedWorkflow.description}</p>
                            <p>
                                Nodes: {selectedWorkflow.nodes.length} · Edges: {selectedWorkflow.edges.length}
                            </p>
                            <p>
                                Workspace: {selectedWorkflow.workspace_id} · Project: {selectedWorkflow.project_id}
                            </p>
                        </>
                    ) : null}
                    <h3>Validation</h3>
                    {!validation ? <p>No validation results yet.</p> : null}
                    {validation ? (
                        <div>
                            <p>{validation.valid ? "Valid graph" : "Invalid graph"}</p>
                            {validation.errors.length > 0 ? (
                                <ul>
                                    {validation.errors.map((item) => (
                                        <li key={item}>{item}</li>
                                    ))}
                                </ul>
                            ) : null}
                            {validation.warnings.length > 0 ? (
                                <ul>
                                    {validation.warnings.map((item) => (
                                        <li key={item}>{item}</li>
                                    ))}
                                </ul>
                            ) : null}
                        </div>
                    ) : null}
                    <h3>Version History</h3>
                    <ul>
                        {versions.map((version) => (
                            <li key={version.id}>
                                v{version.version_number} · {version.change_summary}
                            </li>
                        ))}
                    </ul>
                </article>
            </div>
        </section>
    );
};
