import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { workflowsApi } from "../api/workflows";
import type { WorkflowEdgeRecord, WorkflowNodeRecord, WorkflowRecord } from "../types/api";

const NODE_WIDTH = 180;
const NODE_HEIGHT = 72;
const GRID_SIZE = 24;

const SUPPORTED_NODE_TYPES = [
    "Start",
    "End",
    "Agent",
    "Condition",
    "Decision",
    "Human Approval",
    "Delay",
    "Memory",
    "Knowledge Search",
    "Python Tool",
    "REST Tool",
    "Filesystem Tool",
    "Merge",
    "Parallel Split",
    "Parallel Join",
    "Loop",
    "Webhook",
    "Scheduler",
];

const toSafeId = (value: string) =>
    value
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "") || "node";

interface ViewportState {
    x: number;
    y: number;
    zoom: number;
}

interface GraphSnapshot {
    nodes: WorkflowNodeRecord[];
    edges: WorkflowEdgeRecord[];
}

interface SelectionBox {
    startX: number;
    startY: number;
    currentX: number;
    currentY: number;
}

type PointerMode = "none" | "pan" | "drag-nodes" | "marquee";

interface PointerState {
    mode: PointerMode;
    pointerId: number;
    startClientX: number;
    startClientY: number;
    startWorldX: number;
    startWorldY: number;
    dragNodeId: string;
    nodeStartPositions: Record<string, { x: number; y: number }>;
    viewportStart: ViewportState;
}

const initialViewport: ViewportState = {
    x: 220,
    y: 160,
    zoom: 1,
};

const cloneNodes = (nodes: WorkflowNodeRecord[]) =>
    nodes.map((node) => ({ ...node, config: { ...(node.config ?? {}) } }));

const cloneEdges = (edges: WorkflowEdgeRecord[]) =>
    edges.map((edge) => ({ ...edge }));

const edgePath = (source: WorkflowNodeRecord, target: WorkflowNodeRecord): string => {
    const x1 = (source.x ?? 0) + NODE_WIDTH;
    const y1 = (source.y ?? 0) + NODE_HEIGHT / 2;
    const x2 = target.x ?? 0;
    const y2 = (target.y ?? 0) + NODE_HEIGHT / 2;
    const dx = Math.max(80, Math.abs(x2 - x1) * 0.5);
    return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
};

const nextZoom = (current: number, delta: number): number => {
    const value = current * (delta > 0 ? 0.9 : 1.1);
    return Math.min(2.4, Math.max(0.35, value));
};

export const WorkflowBuilderPage = () => {
    const [workflows, setWorkflows] = useState<WorkflowRecord[]>([]);
    const [selectedWorkflowId, setSelectedWorkflowId] = useState<string>("");
    const [draftName, setDraftName] = useState("Enterprise Workflow");
    const [draftDescription, setDraftDescription] = useState("Interactive orchestration canvas");
    const [nodes, setNodes] = useState<WorkflowNodeRecord[]>([]);
    const [edges, setEdges] = useState<WorkflowEdgeRecord[]>([]);
    const [newNodeName, setNewNodeName] = useState("Research");
    const [newNodeType, setNewNodeType] = useState("Agent");
    const [newNodeAgentId, setNewNodeAgentId] = useState("agent-1");
    const [selectedNodeIds, setSelectedNodeIds] = useState<string[]>([]);
    const [selectedEdgeIds, setSelectedEdgeIds] = useState<string[]>([]);
    const [edgeDraftSourceId, setEdgeDraftSourceId] = useState<string>("");
    const [snapToGrid, setSnapToGrid] = useState(true);
    const [showGrid, setShowGrid] = useState(true);
    const [showMinimap, setShowMinimap] = useState(true);
    const [inspectorOpen, setInspectorOpen] = useState(true);
    const [executionPanelOpen, setExecutionPanelOpen] = useState(true);
    const [viewport, setViewport] = useState<ViewportState>(initialViewport);
    const [marquee, setMarquee] = useState<SelectionBox | null>(null);
    const [history, setHistory] = useState<GraphSnapshot[]>([]);
    const [future, setFuture] = useState<GraphSnapshot[]>([]);
    const [clipboard, setClipboard] = useState<GraphSnapshot | null>(null);
    const [pointer, setPointer] = useState<PointerState | null>(null);
    const [recentRuns, setRecentRuns] = useState<string[]>([]);
    const [activeRunId, setActiveRunId] = useState<string>("");
    const [liveEvents, setLiveEvents] = useState<Array<Record<string, unknown>>>([]);
    const [isSaving, setIsSaving] = useState(false);
    const [isExecuting, setIsExecuting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const canvasRef = useRef<HTMLDivElement | null>(null);
    const eventSourceRef = useRef<EventSource | null>(null);

    const selectedWorkflow = useMemo(
        () => workflows.find((item) => item.id === selectedWorkflowId) ?? null,
        [selectedWorkflowId, workflows]
    );

    const nodeById = useMemo(() => {
        const mapping = new Map<string, WorkflowNodeRecord>();
        for (const node of nodes) {
            mapping.set(node.id, node);
        }
        return mapping;
    }, [nodes]);

    const selectedSingleNode = useMemo(() => {
        if (selectedNodeIds.length !== 1) {
            return null;
        }
        return nodeById.get(selectedNodeIds[0]) ?? null;
    }, [nodeById, selectedNodeIds]);

    const pushHistory = useCallback(
        (currentNodes: WorkflowNodeRecord[], currentEdges: WorkflowEdgeRecord[]) => {
            setHistory((previous) => [
                ...previous.slice(Math.max(0, previous.length - 49)),
                { nodes: cloneNodes(currentNodes), edges: cloneEdges(currentEdges) },
            ]);
            setFuture([]);
        },
        []
    );

    const applyGraph = useCallback(
        (
            nextNodes: WorkflowNodeRecord[],
            nextEdges: WorkflowEdgeRecord[],
            options: { trackHistory?: boolean } = {}
        ) => {
            if (options.trackHistory ?? true) {
                pushHistory(nodes, edges);
            }
            setNodes(nextNodes);
            setEdges(nextEdges);
        },
        [edges, nodes, pushHistory]
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
        setSelectedNodeIds([]);
        setSelectedEdgeIds([]);
        setHistory([]);
        setFuture([]);
        setLiveEvents([]);
        setActiveRunId("");
    }, [selectedWorkflow]);

    useEffect(() => {
        if (!selectedWorkflowId) {
            return;
        }
        const loadRuns = async () => {
            try {
                const runs = await workflowsApi.listRuns(selectedWorkflowId);
                setRecentRuns(runs.map((item) => item.id));
            } catch {
                setRecentRuns([]);
            }
        };
        void loadRuns();
    }, [selectedWorkflowId]);

    const toWorldPoint = useCallback(
        (clientX: number, clientY: number) => {
            const rect = canvasRef.current?.getBoundingClientRect();
            if (!rect) {
                return { x: 0, y: 0 };
            }
            return {
                x: (clientX - rect.left - viewport.x) / viewport.zoom,
                y: (clientY - rect.top - viewport.y) / viewport.zoom,
            };
        },
        [viewport.x, viewport.y, viewport.zoom]
    );

    const clearSelection = useCallback(() => {
        setSelectedNodeIds([]);
        setSelectedEdgeIds([]);
    }, []);

    const addNode = () => {
        pushHistory(nodes, edges);
        const nodeId = `${toSafeId(newNodeName)}-${nodes.length + 1}`;
        const baseX = 120 + (nodes.length % 5) * (NODE_WIDTH + 44);
        const baseY = 80 + Math.floor(nodes.length / 5) * (NODE_HEIGHT + 64);
        const nextNode: WorkflowNodeRecord = {
            id: nodeId,
            name: newNodeName,
            node_type: newNodeType,
            agent_id: newNodeType === "Agent" ? newNodeAgentId : null,
            x: baseX,
            y: baseY,
            config: {},
        };
        setNodes((previous) => [...previous, nextNode]);
        setSelectedNodeIds([nodeId]);
        setSelectedEdgeIds([]);
    };

    const removeNode = (nodeId: string) => {
        const nextNodes = nodes.filter((node) => node.id !== nodeId);
        const nextEdges = edges.filter(
            (edge) => edge.source_node_id !== nodeId && edge.target_node_id !== nodeId
        );
        applyGraph(nextNodes, nextEdges);
        setSelectedNodeIds((previous) => previous.filter((item) => item !== nodeId));
    };

    const addEdge = (sourceId: string, targetId: string) => {
        if (!sourceId || !targetId || sourceId === targetId) {
            return;
        }
        if (
            edges.some(
                (edge) =>
                    edge.source_node_id === sourceId && edge.target_node_id === targetId
            )
        ) {
            return;
        }
        pushHistory(nodes, edges);
        const nextEdge: WorkflowEdgeRecord = {
            id: `edge-${sourceId}-${targetId}-${edges.length + 1}`,
            source_node_id: sourceId,
            target_node_id: targetId,
            label: "",
            condition: "",
        };
        setEdges((previous) => [...previous, nextEdge]);
    };

    const autoLayout = () => {
        const nextNodes = nodes.map((node, index) => {
            const column = index % 6;
            const row = Math.floor(index / 6);
            return {
                ...node,
                x: 140 + column * (NODE_WIDTH + 80),
                y: 100 + row * (NODE_HEIGHT + 84),
            };
        });
        applyGraph(nextNodes, cloneEdges(edges));
    };

    const copySelection = useCallback(() => {
        if (selectedNodeIds.length === 0) {
            return;
        }
        const selectedNodes = nodes.filter((node) => selectedNodeIds.includes(node.id));
        const selectedEdges = edges.filter(
            (edge) =>
                selectedNodeIds.includes(edge.source_node_id)
                && selectedNodeIds.includes(edge.target_node_id)
        );
        setClipboard({ nodes: cloneNodes(selectedNodes), edges: cloneEdges(selectedEdges) });
    }, [edges, nodes, selectedNodeIds]);

    const pasteSelection = useCallback(() => {
        if (!clipboard || clipboard.nodes.length === 0) {
            return;
        }
        pushHistory(nodes, edges);
        const idMap = new Map<string, string>();
        const pastedNodes = clipboard.nodes.map((node, index) => {
            const newId = `${node.id}-copy-${Date.now()}-${index}`;
            idMap.set(node.id, newId);
            return {
                ...node,
                id: newId,
                x: (node.x ?? 0) + 40,
                y: (node.y ?? 0) + 40,
            };
        });
        const pastedEdges = clipboard.edges
            .map((edge, index) => {
                const sourceId = idMap.get(edge.source_node_id);
                const targetId = idMap.get(edge.target_node_id);
                if (!sourceId || !targetId) {
                    return null;
                }
                return {
                    ...edge,
                    id: `${edge.id}-copy-${Date.now()}-${index}`,
                    source_node_id: sourceId,
                    target_node_id: targetId,
                };
            })
            .filter((edge): edge is WorkflowEdgeRecord => edge !== null);

        setNodes((previous) => [...previous, ...pastedNodes]);
        setEdges((previous) => [...previous, ...pastedEdges]);
        setSelectedNodeIds(pastedNodes.map((node) => node.id));
        setSelectedEdgeIds([]);
    }, [clipboard, edges, nodes, pushHistory]);

    const duplicateSelection = useCallback(() => {
        copySelection();
        setTimeout(() => {
            pasteSelection();
        }, 0);
    }, [copySelection, pasteSelection]);

    const deleteSelection = useCallback(() => {
        if (selectedNodeIds.length === 0 && selectedEdgeIds.length === 0) {
            return;
        }
        const nextNodes = nodes.filter((node) => !selectedNodeIds.includes(node.id));
        const nextEdges = edges.filter(
            (edge) =>
                !selectedEdgeIds.includes(edge.id)
                && !selectedNodeIds.includes(edge.source_node_id)
                && !selectedNodeIds.includes(edge.target_node_id)
        );
        applyGraph(nextNodes, nextEdges);
        clearSelection();
    }, [applyGraph, clearSelection, edges, nodes, selectedEdgeIds, selectedNodeIds]);

    const undo = useCallback(() => {
        if (history.length === 0) {
            return;
        }
        const previous = history[history.length - 1];
        const remaining = history.slice(0, -1);
        setFuture((items) => [...items, { nodes: cloneNodes(nodes), edges: cloneEdges(edges) }]);
        setHistory(remaining);
        setNodes(cloneNodes(previous.nodes));
        setEdges(cloneEdges(previous.edges));
        clearSelection();
    }, [clearSelection, edges, history, nodes]);

    const redo = useCallback(() => {
        if (future.length === 0) {
            return;
        }
        const next = future[future.length - 1];
        const remaining = future.slice(0, -1);
        setHistory((items) => [...items, { nodes: cloneNodes(nodes), edges: cloneEdges(edges) }]);
        setFuture(remaining);
        setNodes(cloneNodes(next.nodes));
        setEdges(cloneEdges(next.edges));
        clearSelection();
    }, [clearSelection, edges, future, nodes]);

    const selectAll = useCallback(() => {
        setSelectedNodeIds(nodes.map((node) => node.id));
        setSelectedEdgeIds(edges.map((edge) => edge.id));
    }, [edges, nodes]);

    const executeWorkflow = async () => {
        if (!selectedWorkflowId) {
            return;
        }
        setIsExecuting(true);
        setError(null);
        try {
            const run = await workflowsApi.execute(selectedWorkflowId, {
                input_payload: {
                    source: "workflow-builder",
                    selected_nodes: selectedNodeIds,
                },
                conversation_id: "",
                shared_variables: {},
                wait_for_completion: false,
            });
            setActiveRunId(run.run_id);
            setRecentRuns((previous) => [run.run_id, ...previous.filter((item) => item !== run.run_id)]);
            setLiveEvents([]);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to start workflow run.");
        } finally {
            setIsExecuting(false);
        }
    };

    useEffect(() => {
        if (!activeRunId) {
            return;
        }
        eventSourceRef.current?.close();
        const source = new EventSource(workflowsApi.streamRunEventsUrl(activeRunId));
        eventSourceRef.current = source;

        const onUpdate = (event: MessageEvent) => {
            try {
                const payload = JSON.parse(event.data) as Record<string, unknown>;
                setLiveEvents((previous) => [...previous.slice(-79), payload]);
            } catch {
                // Ignore malformed stream event payloads.
            }
        };

        source.addEventListener("workflow_update", onUpdate);
        source.addEventListener("workflow_completed", onUpdate);
        source.addEventListener("error", onUpdate as EventListener);

        return () => {
            source.close();
        };
    }, [activeRunId]);

    useEffect(() => {
        const onKeyDown = (event: KeyboardEvent) => {
            const key = event.key.toLowerCase();
            const withMeta = event.metaKey || event.ctrlKey;

            if (withMeta && key === "z") {
                event.preventDefault();
                undo();
                return;
            }
            if (withMeta && key === "y") {
                event.preventDefault();
                redo();
                return;
            }
            if (withMeta && key === "a") {
                event.preventDefault();
                selectAll();
                return;
            }
            if (withMeta && key === "c") {
                event.preventDefault();
                copySelection();
                return;
            }
            if (withMeta && key === "v") {
                event.preventDefault();
                pasteSelection();
                return;
            }
            if (withMeta && key === "d") {
                event.preventDefault();
                duplicateSelection();
                return;
            }
            if (event.key === "Delete" || event.key === "Backspace") {
                event.preventDefault();
                deleteSelection();
                return;
            }
            if (event.key === "Escape") {
                setEdgeDraftSourceId("");
                clearSelection();
                return;
            }
            if (event.key === "+" || event.key === "=") {
                event.preventDefault();
                setViewport((previous) => ({ ...previous, zoom: Math.min(2.4, previous.zoom * 1.1) }));
                return;
            }
            if (event.key === "-") {
                event.preventDefault();
                setViewport((previous) => ({ ...previous, zoom: Math.max(0.35, previous.zoom * 0.9) }));
            }
        };

        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, [
        clearSelection,
        copySelection,
        deleteSelection,
        duplicateSelection,
        pasteSelection,
        redo,
        selectAll,
        undo,
    ]);

    const onCanvasWheel = (event: React.WheelEvent<HTMLDivElement>) => {
        event.preventDefault();
        const worldBefore = toWorldPoint(event.clientX, event.clientY);
        const zoom = nextZoom(viewport.zoom, event.deltaY);
        const rect = canvasRef.current?.getBoundingClientRect();
        if (!rect) {
            return;
        }
        const x = event.clientX - rect.left - worldBefore.x * zoom;
        const y = event.clientY - rect.top - worldBefore.y * zoom;
        setViewport({ x, y, zoom });
    };

    const onCanvasPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
        if ((event.target as HTMLElement).closest(".workflow-canvas-node")) {
            return;
        }

        const world = toWorldPoint(event.clientX, event.clientY);
        if (event.button === 1 || event.button === 2 || event.shiftKey) {
            setPointer({
                mode: "pan",
                pointerId: event.pointerId,
                startClientX: event.clientX,
                startClientY: event.clientY,
                startWorldX: world.x,
                startWorldY: world.y,
                dragNodeId: "",
                nodeStartPositions: {},
                viewportStart: viewport,
            });
            return;
        }

        setPointer({
            mode: "marquee",
            pointerId: event.pointerId,
            startClientX: event.clientX,
            startClientY: event.clientY,
            startWorldX: world.x,
            startWorldY: world.y,
            dragNodeId: "",
            nodeStartPositions: {},
            viewportStart: viewport,
        });
        setMarquee({
            startX: world.x,
            startY: world.y,
            currentX: world.x,
            currentY: world.y,
        });
        if (!event.metaKey && !event.ctrlKey) {
            clearSelection();
        }
    };

    const onNodePointerDown = (
        event: React.PointerEvent<HTMLDivElement>,
        nodeId: string
    ) => {
        event.stopPropagation();
        const world = toWorldPoint(event.clientX, event.clientY);
        const alreadySelected = selectedNodeIds.includes(nodeId);
        let selection = selectedNodeIds;
        if (!alreadySelected) {
            if (event.metaKey || event.ctrlKey) {
                selection = [...selectedNodeIds, nodeId];
            } else {
                selection = [nodeId];
            }
            setSelectedNodeIds(selection);
            setSelectedEdgeIds([]);
        } else if (event.metaKey || event.ctrlKey) {
            const next = selectedNodeIds.filter((item) => item !== nodeId);
            setSelectedNodeIds(next);
            return;
        }

        const nodeStartPositions: Record<string, { x: number; y: number }> = {};
        for (const node of nodes) {
            if (selection.includes(node.id)) {
                nodeStartPositions[node.id] = {
                    x: node.x ?? 0,
                    y: node.y ?? 0,
                };
            }
        }

        setPointer({
            mode: "drag-nodes",
            pointerId: event.pointerId,
            startClientX: event.clientX,
            startClientY: event.clientY,
            startWorldX: world.x,
            startWorldY: world.y,
            dragNodeId: nodeId,
            nodeStartPositions,
            viewportStart: viewport,
        });
    };

    const onCanvasPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
        if (!pointer || pointer.pointerId !== event.pointerId) {
            return;
        }
        if (pointer.mode === "pan") {
            const dx = event.clientX - pointer.startClientX;
            const dy = event.clientY - pointer.startClientY;
            setViewport({
                ...pointer.viewportStart,
                x: pointer.viewportStart.x + dx,
                y: pointer.viewportStart.y + dy,
            });
            return;
        }

        const world = toWorldPoint(event.clientX, event.clientY);
        if (pointer.mode === "marquee") {
            setMarquee((previous) =>
                previous
                    ? {
                        ...previous,
                        currentX: world.x,
                        currentY: world.y,
                    }
                    : previous
            );
            return;
        }

        if (pointer.mode === "drag-nodes") {
            const dx = world.x - pointer.startWorldX;
            const dy = world.y - pointer.startWorldY;
            const nextNodes = nodes.map((node) => {
                const base = pointer.nodeStartPositions[node.id];
                if (!base) {
                    return node;
                }
                const rawX = base.x + dx;
                const rawY = base.y + dy;
                const x = snapToGrid ? Math.round(rawX / GRID_SIZE) * GRID_SIZE : rawX;
                const y = snapToGrid ? Math.round(rawY / GRID_SIZE) * GRID_SIZE : rawY;
                return { ...node, x, y };
            });
            setNodes(nextNodes);
        }
    };

    const onCanvasPointerUp = (event: React.PointerEvent<HTMLDivElement>) => {
        if (!pointer || pointer.pointerId !== event.pointerId) {
            return;
        }

        if (pointer.mode === "drag-nodes") {
            const moved = nodes.some((node) => {
                const base = pointer.nodeStartPositions[node.id];
                if (!base) {
                    return false;
                }
                return (node.x ?? 0) !== base.x || (node.y ?? 0) !== base.y;
            });
            if (moved) {
                setHistory((previous) => [
                    ...previous.slice(Math.max(0, previous.length - 49)),
                    {
                        nodes: cloneNodes(nodes.map((node) => {
                            const base = pointer.nodeStartPositions[node.id];
                            if (!base) {
                                return node;
                            }
                            return { ...node, x: base.x, y: base.y };
                        })), edges: cloneEdges(edges)
                    },
                ]);
                setFuture([]);
            }
        }

        if (pointer.mode === "marquee" && marquee) {
            const minX = Math.min(marquee.startX, marquee.currentX);
            const maxX = Math.max(marquee.startX, marquee.currentX);
            const minY = Math.min(marquee.startY, marquee.currentY);
            const maxY = Math.max(marquee.startY, marquee.currentY);
            const selected = nodes
                .filter((node) => {
                    const nodeX = node.x ?? 0;
                    const nodeY = node.y ?? 0;
                    return (
                        nodeX >= minX
                        && nodeX + NODE_WIDTH <= maxX
                        && nodeY >= minY
                        && nodeY + NODE_HEIGHT <= maxY
                    );
                })
                .map((node) => node.id);
            setSelectedNodeIds(selected);
            setSelectedEdgeIds([]);
        }

        setMarquee(null);
        setPointer(null);
    };

    const onCanvasPointerLeave = (event: React.PointerEvent<HTMLDivElement>) => {
        if (pointer && pointer.pointerId === event.pointerId) {
            setPointer(null);
            setMarquee(null);
        }
    };

    const onNodeClick = (nodeId: string) => {
        if (edgeDraftSourceId && edgeDraftSourceId !== nodeId) {
            addEdge(edgeDraftSourceId, nodeId);
            setEdgeDraftSourceId("");
            return;
        }
        setSelectedNodeIds([nodeId]);
        setSelectedEdgeIds([]);
    };

    const onEdgeClick = (edgeId: string) => {
        setSelectedEdgeIds([edgeId]);
        setSelectedNodeIds([]);
    };

    const updateSelectedNode = (
        key: "name" | "node_type" | "agent_id",
        value: string
    ) => {
        if (!selectedSingleNode) {
            return;
        }
        const nextNodes = nodes.map((node) =>
            node.id === selectedSingleNode.id
                ? {
                    ...node,
                    [key]: value,
                }
                : node
        );
        setNodes(nextNodes);
    };

    const updateSelectedNodeConfig = (value: string) => {
        if (!selectedSingleNode) {
            return;
        }
        try {
            const config = JSON.parse(value) as Record<string, unknown>;
            const nextNodes = nodes.map((node) =>
                node.id === selectedSingleNode.id
                    ? {
                        ...node,
                        config,
                    }
                    : node
            );
            setNodes(nextNodes);
            setError(null);
        } catch {
            setError("Node config must be valid JSON.");
        }
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

    const canvasStyle = {
        transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})`,
        transformOrigin: "0 0",
    } as const;

    const graphBounds = useMemo(() => {
        if (nodes.length === 0) {
            return { minX: 0, minY: 0, maxX: 1, maxY: 1 };
        }
        const minX = Math.min(...nodes.map((node) => node.x ?? 0));
        const minY = Math.min(...nodes.map((node) => node.y ?? 0));
        const maxX = Math.max(...nodes.map((node) => (node.x ?? 0) + NODE_WIDTH));
        const maxY = Math.max(...nodes.map((node) => (node.y ?? 0) + NODE_HEIGHT));
        return { minX, minY, maxX, maxY };
    }, [nodes]);

    const minimapScale = 220 / Math.max(1, graphBounds.maxX - graphBounds.minX + 80);

    const viewRect = useMemo(() => {
        const rect = canvasRef.current?.getBoundingClientRect();
        if (!rect) {
            return null;
        }
        const width = rect.width / viewport.zoom;
        const height = rect.height / viewport.zoom;
        const worldX = -viewport.x / viewport.zoom;
        const worldY = -viewport.y / viewport.zoom;
        return { x: worldX, y: worldY, width, height };
    }, [viewport.x, viewport.y, viewport.zoom]);

    return (
        <section className="workflow-page">
            <header className="workflow-page__header">
                <div>
                    <h1>Workflow Builder</h1>
                    <p>
                        Enterprise orchestration canvas with drag and drop, keyboard shortcuts,
                        minimap, and live execution streaming.
                    </p>
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
                    <button type="button" onClick={autoLayout}>Auto Layout</button>
                    <button type="button" onClick={undo} disabled={history.length === 0}>Undo</button>
                    <button type="button" onClick={redo} disabled={future.length === 0}>Redo</button>
                    <button type="button" onClick={executeWorkflow} disabled={!selectedWorkflowId || isExecuting}>
                        Run
                    </button>
                </div>
            </header>

            {error ? <p className="workflow-error">{error}</p> : null}

            <article className="workflow-card">
                <h2>Definition and Canvas Controls</h2>
                <div className="workflow-form-row">
                    <input value={draftName} onChange={(event) => setDraftName(event.target.value)} />
                    <input
                        value={draftDescription}
                        onChange={(event) => setDraftDescription(event.target.value)}
                    />
                    <label className="workflow-inline-check">
                        <input
                            type="checkbox"
                            checked={showGrid}
                            onChange={(event) => setShowGrid(event.target.checked)}
                        />
                        Grid
                    </label>
                    <label className="workflow-inline-check">
                        <input
                            type="checkbox"
                            checked={snapToGrid}
                            onChange={(event) => setSnapToGrid(event.target.checked)}
                        />
                        Snap
                    </label>
                    <label className="workflow-inline-check">
                        <input
                            type="checkbox"
                            checked={showMinimap}
                            onChange={(event) => setShowMinimap(event.target.checked)}
                        />
                        Minimap
                    </label>
                    <button
                        type="button"
                        onClick={() => setInspectorOpen((open) => !open)}
                    >
                        {inspectorOpen ? "Hide Inspector" : "Show Inspector"}
                    </button>
                    <button
                        type="button"
                        onClick={() => setExecutionPanelOpen((open) => !open)}
                    >
                        {executionPanelOpen ? "Hide Execution" : "Show Execution"}
                    </button>
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
                            {SUPPORTED_NODE_TYPES.map((nodeType) => (
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
                                    <div className="workflow-node-row-actions">
                                        <button
                                            type="button"
                                            onClick={() => setEdgeDraftSourceId(node.id)}
                                        >
                                            Connect
                                        </button>
                                        <button type="button" onClick={() => removeNode(node.id)}>
                                            Remove
                                        </button>
                                    </div>
                                </div>
                            </li>
                        ))}
                    </ul>
                </article>

                {inspectorOpen ? (
                    <article className="workflow-card workflow-card--inspector">
                        <h2>Properties</h2>
                        <p>
                            Selected nodes: {selectedNodeIds.length} · Selected edges:{" "}
                            {selectedEdgeIds.length}
                        </p>
                        {!selectedSingleNode ? (
                            <p>Select a single node to edit properties.</p>
                        ) : (
                            <>
                                <div className="workflow-form-row">
                                    <input
                                        value={selectedSingleNode.name}
                                        onChange={(event) =>
                                            updateSelectedNode("name", event.target.value)
                                        }
                                        placeholder="Node name"
                                    />
                                    <select
                                        value={selectedSingleNode.node_type}
                                        onChange={(event) =>
                                            updateSelectedNode("node_type", event.target.value)
                                        }
                                    >
                                        {SUPPORTED_NODE_TYPES.map((nodeType) => (
                                            <option key={nodeType} value={nodeType}>
                                                {nodeType}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                                <div className="workflow-form-row">
                                    <input
                                        value={selectedSingleNode.agent_id ?? ""}
                                        onChange={(event) =>
                                            updateSelectedNode("agent_id", event.target.value)
                                        }
                                        placeholder="Agent Studio reference"
                                    />
                                </div>
                                <textarea
                                    rows={8}
                                    value={JSON.stringify(selectedSingleNode.config ?? {}, null, 2)}
                                    onChange={(event) => updateSelectedNodeConfig(event.target.value)}
                                />
                            </>
                        )}
                        <h3>Canvas Shortcuts</h3>
                        <p>
                            Ctrl/Cmd+C Copy · Ctrl/Cmd+V Paste · Ctrl/Cmd+D Duplicate · Delete
                            Remove · Ctrl/Cmd+Z Undo · Ctrl/Cmd+Y Redo · +/- Zoom · Shift+Drag
                            Pan
                        </p>
                    </article>
                ) : null}
            </div>

            <article className="workflow-card workflow-card--canvas">
                <h2>Orchestration Canvas</h2>
                <div
                    ref={canvasRef}
                    className={`workflow-canvas workflow-canvas--interactive ${showGrid ? "workflow-canvas--grid" : ""}`}
                    role="img"
                    aria-label="Workflow orchestration canvas"
                    onWheel={onCanvasWheel}
                    onPointerDown={onCanvasPointerDown}
                    onPointerMove={onCanvasPointerMove}
                    onPointerUp={onCanvasPointerUp}
                    onPointerLeave={onCanvasPointerLeave}
                >
                    <div className="workflow-canvas__world" style={canvasStyle}>
                        <svg className="workflow-canvas__edges" width={5000} height={5000}>
                            <defs>
                                <marker
                                    id="workflow-arrow"
                                    markerWidth="10"
                                    markerHeight="10"
                                    refX="9"
                                    refY="5"
                                    orient="auto"
                                >
                                    <path d="M0,0 L10,5 L0,10 z" fill="currentColor" />
                                </marker>
                            </defs>
                            {edges.map((edge) => {
                                const source = nodeById.get(edge.source_node_id);
                                const target = nodeById.get(edge.target_node_id);
                                if (!source || !target) {
                                    return null;
                                }
                                const selected = selectedEdgeIds.includes(edge.id);
                                return (
                                    <g
                                        key={edge.id}
                                        className={`workflow-canvas__edge ${selected ? "workflow-canvas__edge--selected" : ""}`}
                                        onClick={(event) => {
                                            event.stopPropagation();
                                            onEdgeClick(edge.id);
                                        }}
                                    >
                                        <path
                                            d={edgePath(source, target)}
                                            markerEnd="url(#workflow-arrow)"
                                        />
                                        {edge.condition ? (
                                            <text
                                                x={((source.x ?? 0) + (target.x ?? 0)) / 2 + NODE_WIDTH * 0.2}
                                                y={((source.y ?? 0) + (target.y ?? 0)) / 2 + 18}
                                            >
                                                {edge.condition}
                                            </text>
                                        ) : null}
                                    </g>
                                );
                            })}
                        </svg>

                        {nodes.map((node) => {
                            const isSelected = selectedNodeIds.includes(node.id);
                            const isEdgeSource = edgeDraftSourceId === node.id;
                            return (
                                <div
                                    key={node.id}
                                    className={`workflow-canvas-node ${isSelected ? "workflow-canvas-node--selected" : ""} ${isEdgeSource ? "workflow-canvas-node--edge-source" : ""}`}
                                    style={{
                                        left: `${node.x ?? 0}px`,
                                        top: `${node.y ?? 0}px`,
                                        width: `${NODE_WIDTH}px`,
                                        height: `${NODE_HEIGHT}px`,
                                    }}
                                    onPointerDown={(event) => onNodePointerDown(event, node.id)}
                                    onClick={(event) => {
                                        event.stopPropagation();
                                        onNodeClick(node.id);
                                    }}
                                >
                                    <strong>{node.name}</strong>
                                    <span>{node.node_type}</span>
                                </div>
                            );
                        })}

                        {marquee ? (
                            <div
                                className="workflow-canvas__marquee"
                                style={{
                                    left: `${Math.min(marquee.startX, marquee.currentX)}px`,
                                    top: `${Math.min(marquee.startY, marquee.currentY)}px`,
                                    width: `${Math.abs(marquee.currentX - marquee.startX)}px`,
                                    height: `${Math.abs(marquee.currentY - marquee.startY)}px`,
                                }}
                            />
                        ) : null}
                    </div>

                    {showMinimap ? (
                        <aside className="workflow-minimap">
                            <svg width={240} height={160}>
                                <rect x={0} y={0} width={240} height={160} className="workflow-minimap__bg" />
                                {nodes.map((node) => {
                                    const x = ((node.x ?? 0) - graphBounds.minX + 20) * minimapScale;
                                    const y = ((node.y ?? 0) - graphBounds.minY + 20) * minimapScale;
                                    const width = NODE_WIDTH * minimapScale;
                                    const height = NODE_HEIGHT * minimapScale;
                                    return (
                                        <rect
                                            key={node.id}
                                            x={x}
                                            y={y}
                                            width={width}
                                            height={height}
                                            className={`workflow-minimap__node ${selectedNodeIds.includes(node.id) ? "workflow-minimap__node--selected" : ""}`}
                                        />
                                    );
                                })}
                                {viewRect ? (
                                    <rect
                                        className="workflow-minimap__viewport"
                                        x={(viewRect.x - graphBounds.minX + 20) * minimapScale}
                                        y={(viewRect.y - graphBounds.minY + 20) * minimapScale}
                                        width={viewRect.width * minimapScale}
                                        height={viewRect.height * minimapScale}
                                    />
                                ) : null}
                            </svg>
                        </aside>
                    ) : null}
                </div>
            </article>

            {executionPanelOpen ? (
                <article className="workflow-card workflow-card--execution">
                    <h2>Live Execution Panel</h2>
                    <div className="workflow-form-row">
                        <select
                            value={activeRunId}
                            onChange={(event) => setActiveRunId(event.target.value)}
                        >
                            <option value="">Select run</option>
                            {recentRuns.map((runId) => (
                                <option key={runId} value={runId}>
                                    {runId}
                                </option>
                            ))}
                        </select>
                        <button type="button" onClick={() => setLiveEvents([])}>Clear Events</button>
                    </div>
                    <div className="workflow-execution-events" role="log" aria-live="polite">
                        {liveEvents.length === 0 ? <p>No streamed events yet.</p> : null}
                        {liveEvents.map((item, index) => (
                            <pre key={`${String(item.run_id ?? "run")}-${index}`}>
                                {JSON.stringify(item, null, 2)}
                            </pre>
                        ))}
                    </div>
                </article>
            ) : null}
        </section>
    );
};
