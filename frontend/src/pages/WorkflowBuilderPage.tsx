import { useCallback, useEffect, useMemo, useState } from "react";

import { workflowsApi } from "../api/workflows";
import type { WorkflowEdgeRecord, WorkflowNodeRecord, WorkflowRecord } from "../types/api";

const DEFAULT_NODE_TYPES = [
    "Start",
    "Agent",
    "Condition",
    "Human Approval",
    "Merge",
    "Parallel Split",
    "Loop",
    "End",
];

const toSafeId = (value: string) =>
    value
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "") || "node";

export const WorkflowBuilderPage = () => {
    const [workflows, setWorkflows] = useState<WorkflowRecord[]>([]);
    const [selectedWorkflowId, setSelectedWorkflowId] = useState<string>("");
    const [draftName, setDraftName] = useState("Draft Workflow");
    const [draftDescription, setDraftDescription] = useState("Graph builder draft");
    const [nodes, setNodes] = useState<WorkflowNodeRecord[]>([]);
    const [edges, setEdges] = useState<WorkflowEdgeRecord[]>([]);
    const [newNodeName, setNewNodeName] = useState("Research");
    const [newNodeType, setNewNodeType] = useState("Agent");
    const [newNodeAgentId, setNewNodeAgentId] = useState("agent-1");
    const [newEdgeSource, setNewEdgeSource] = useState("");
    const [newEdgeTarget, setNewEdgeTarget] = useState("");
    const [isSaving, setIsSaving] = useState(false);
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

    useEffect(() => {
        void loadWorkflows();
    }, [loadWorkflows]);

    useEffect(() => {
        if (!selectedWorkflow) {
            setNodes([]);
            setEdges([]);
            return;
        }
        setDraftName(selectedWorkflow.name);
        setDraftDescription(selectedWorkflow.description);
        setNodes(selectedWorkflow.nodes);
        setEdges(selectedWorkflow.edges);
    }, [selectedWorkflow]);

    const addNode = () => {
        const nodeId = `${toSafeId(newNodeName)}-${nodes.length + 1}`;
        const nextNode: WorkflowNodeRecord = {
            id: nodeId,
            name: newNodeName,
            node_type: newNodeType,
            agent_id: newNodeType === "Agent" ? newNodeAgentId : null,
            x: 120 + (nodes.length % 4) * 180,
            y: 90 + Math.floor(nodes.length / 4) * 120,
            config: {},
        };
        setNodes((previous) => [...previous, nextNode]);
        if (!newEdgeSource) {
            setNewEdgeSource(nodeId);
        }
        if (!newEdgeTarget) {
            setNewEdgeTarget(nodeId);
        }
    };

    const removeNode = (nodeId: string) => {
        setNodes((previous) => previous.filter((node) => node.id !== nodeId));
        setEdges((previous) =>
            previous.filter(
                (edge) => edge.source_node_id !== nodeId && edge.target_node_id !== nodeId
            )
        );
    };

    const addEdge = () => {
        if (!newEdgeSource || !newEdgeTarget || newEdgeSource === newEdgeTarget) {
            return;
        }
        const nextEdge: WorkflowEdgeRecord = {
            id: `edge-${newEdgeSource}-${newEdgeTarget}-${edges.length + 1}`,
            source_node_id: newEdgeSource,
            target_node_id: newEdgeTarget,
            label: "",
            condition: "",
        };
        setEdges((previous) => [...previous, nextEdge]);
    };

    const saveWorkflow = async () => {
        setError(null);
        setIsSaving(true);
        try {
            if (selectedWorkflowId) {
                await workflowsApi.update(selectedWorkflowId, {
                    name: draftName,
                    description: draftDescription,
                    nodes,
                    edges,
                });
            } else {
                const created = await workflowsApi.create({
                    name: draftName,
                    description: draftDescription,
                    enabled: true,
                    nodes,
                    edges,
                });
                setSelectedWorkflowId(created.id);
            }
            await loadWorkflows();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to save workflow.");
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <section className="workflow-page">
            <header className="workflow-page__header">
                <div>
                    <h1>Workflow Builder</h1>
                    <p>Compose multi-agent graphs with node and edge editing.</p>
                </div>
                <div className="workflow-page__actions">
                    <select
                        value={selectedWorkflowId}
                        onChange={(event) => setSelectedWorkflowId(event.target.value)}
                    >
                        <option value="">New workflow</option>
                        {workflows.map((workflow) => (
                            <option key={workflow.id} value={workflow.id}>
                                {workflow.name}
                            </option>
                        ))}
                    </select>
                    <button type="button" onClick={saveWorkflow} disabled={isSaving}>
                        {selectedWorkflowId ? "Save" : "Create"}
                    </button>
                </div>
            </header>

            {error ? <p className="workflow-error">{error}</p> : null}

            <article className="workflow-card">
                <h2>Definition</h2>
                <div className="workflow-form-row">
                    <input value={draftName} onChange={(event) => setDraftName(event.target.value)} />
                    <input
                        value={draftDescription}
                        onChange={(event) => setDraftDescription(event.target.value)}
                    />
                </div>
            </article>

            <div className="workflow-grid">
                <article className="workflow-card">
                    <h2>Nodes</h2>
                    <div className="workflow-form-row">
                        <input
                            value={newNodeName}
                            onChange={(event) => setNewNodeName(event.target.value)}
                            placeholder="Node name"
                        />
                        <select
                            value={newNodeType}
                            onChange={(event) => setNewNodeType(event.target.value)}
                        >
                            {DEFAULT_NODE_TYPES.map((nodeType) => (
                                <option key={nodeType} value={nodeType}>
                                    {nodeType}
                                </option>
                            ))}
                        </select>
                        <input
                            value={newNodeAgentId}
                            onChange={(event) => setNewNodeAgentId(event.target.value)}
                            placeholder="Agent ID"
                        />
                        <button type="button" onClick={addNode}>
                            Add Node
                        </button>
                    </div>
                    <ul className="workflow-list">
                        {nodes.map((node) => (
                            <li key={node.id}>
                                <div className="workflow-node-row">
                                    <span>
                                        {node.name} · {node.node_type}
                                    </span>
                                    <button type="button" onClick={() => removeNode(node.id)}>
                                        Remove
                                    </button>
                                </div>
                            </li>
                        ))}
                    </ul>
                </article>

                <article className="workflow-card">
                    <h2>Edges</h2>
                    <div className="workflow-form-row">
                        <select
                            value={newEdgeSource}
                            onChange={(event) => setNewEdgeSource(event.target.value)}
                        >
                            <option value="">Source</option>
                            {nodes.map((node) => (
                                <option key={node.id} value={node.id}>
                                    {node.name}
                                </option>
                            ))}
                        </select>
                        <select
                            value={newEdgeTarget}
                            onChange={(event) => setNewEdgeTarget(event.target.value)}
                        >
                            <option value="">Target</option>
                            {nodes.map((node) => (
                                <option key={node.id} value={node.id}>
                                    {node.name}
                                </option>
                            ))}
                        </select>
                        <button type="button" onClick={addEdge}>
                            Add Edge
                        </button>
                    </div>
                    <ul className="workflow-list">
                        {edges.map((edge) => (
                            <li key={edge.id}>
                                {edge.source_node_id} → {edge.target_node_id}
                            </li>
                        ))}
                    </ul>
                </article>
            </div>

            <article className="workflow-card">
                <h2>Graph Preview</h2>
                <div className="workflow-canvas" role="img" aria-label="Workflow graph preview">
                    {nodes.map((node) => (
                        <div
                            key={node.id}
                            className="workflow-canvas__node"
                            style={{ left: `${node.x ?? 0}px`, top: `${node.y ?? 0}px` }}
                        >
                            <strong>{node.name}</strong>
                            <span>{node.node_type}</span>
                        </div>
                    ))}
                </div>
            </article>
        </section>
    );
};
