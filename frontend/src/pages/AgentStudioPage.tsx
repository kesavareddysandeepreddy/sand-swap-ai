import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { AgentDetailsPanel } from "../components/agent_studio/AgentDetailsPanel";
import { AgentDialog } from "../components/agent_studio/AgentDialog";
import { AgentList } from "../components/agent_studio/AgentList";
import { useAgents } from "../state/useAgents";
import type { ReturnTypeUseAuth } from "../types/auth";

interface AgentStudioPageProps {
    auth: ReturnTypeUseAuth;
}

type StatusFilter = "all" | "enabled" | "disabled";

export const AgentStudioPage = ({ auth }: AgentStudioPageProps) => {
    const navigate = useNavigate();
    const params = useParams<{ agentId?: string }>();
    const scopeKey = `${auth.effectiveUserId}:${auth.activeWorkspaceId ?? "default"}:${auth.activeProjectId ?? "default"}`;
    const {
        agents,
        enabledCount,
        isLoading,
        isMutating,
        error,
        createAgent,
        updateAgent,
        deleteAgent,
        enableAgent,
        disableAgent,
    } = useAgents(scopeKey);

    const [search, setSearch] = useState("");
    const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
    const [createOpen, setCreateOpen] = useState(false);
    const [editOpen, setEditOpen] = useState(false);

    const selectedAgent = useMemo(
        () => agents.find((agent) => agent.id === params.agentId) ?? null,
        [agents, params.agentId]
    );

    useEffect(() => {
        if (!params.agentId && agents.length > 0) {
            navigate(`/agent-studio/${agents[0].id}`, { replace: true });
        }
    }, [agents, navigate, params.agentId]);

    const filteredAgents = useMemo(() => {
        const query = search.trim().toLowerCase();
        return agents.filter((agent) => {
            const matchesSearch =
                !query
                || agent.name.toLowerCase().includes(query)
                || agent.role.toLowerCase().includes(query)
                || agent.tags.some((tag) => tag.toLowerCase().includes(query));
            const matchesStatus =
                statusFilter === "all"
                || (statusFilter === "enabled" && agent.enabled)
                || (statusFilter === "disabled" && !agent.enabled);
            return matchesSearch && matchesStatus;
        });
    }, [agents, search, statusFilter]);

    const openEdit = () => {
        if (!selectedAgent) {
            return;
        }
        setEditOpen(true);
    };

    const handleCreate = async (payload: Parameters<typeof createAgent>[0]) => {
        const agent = await createAgent(payload);
        navigate(`/agent-studio/${agent.id}`);
    };

    const handleEdit = async (payload: Parameters<typeof updateAgent>[1]) => {
        if (!selectedAgent) {
            return;
        }
        await updateAgent(selectedAgent.id, payload);
    };

    const handleDelete = async (agentId: string) => {
        const confirmed = window.confirm("Delete this agent?");
        if (!confirmed) {
            return;
        }
        await deleteAgent(agentId);
        if (params.agentId === agentId) {
            navigate("/agent-studio", { replace: true });
        }
    };

    const handleEnable = async (agentId: string) => {
        await enableAgent(agentId);
    };

    const handleDisable = async (agentId: string) => {
        await disableAgent(agentId);
    };

    return (
        <div className="agent-studio-page">
            <header className="agent-studio-hero">
                <div>
                    <p className="agent-dialog__eyebrow">Agent Studio</p>
                    <h1>Agents</h1>
                    <p className="agent-studio-hero__copy">
                        Create, inspect, and manage isolated agent definitions before execution is introduced.
                    </p>
                </div>
                <div className="agent-studio-hero__stats">
                    <div><strong>{agents.length}</strong><span>Total</span></div>
                    <div><strong>{enabledCount}</strong><span>Enabled</span></div>
                </div>
            </header>

            <section className="agent-studio-toolbar">
                <input
                    className="agent-studio-search"
                    type="search"
                    placeholder="Search agents"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                />
                <select className="agent-studio-filter" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}>
                    <option value="all">All Status</option>
                    <option value="enabled">Enabled</option>
                    <option value="disabled">Disabled</option>
                </select>
                <button type="button" className="memory-button" onClick={() => setCreateOpen(true)}>
                    Create
                </button>
            </section>

            {error ? (
                <p className="error-banner" role="alert">
                    <span className="error-icon" aria-hidden="true">!</span>
                    {error}
                </p>
            ) : null}

            <div className="agent-studio-grid">
                <section className="agent-studio-list-card">
                    {isLoading ? <p className="agent-studio__empty">Loading agents...</p> : null}
                    {!isLoading ? (
                        <AgentList
                            agents={filteredAgents}
                            selectedAgentId={selectedAgent?.id ?? null}
                            onSelect={(agentId) => navigate(`/agent-studio/${agentId}`)}
                            onEdit={(agentId) => {
                                if (agentId === selectedAgent?.id) {
                                    openEdit();
                                    return;
                                }
                                navigate(`/agent-studio/${agentId}`);
                                setEditOpen(true);
                            }}
                            onDelete={(agentId) => void handleDelete(agentId)}
                            onEnable={(agentId) => void handleEnable(agentId)}
                            onDisable={(agentId) => void handleDisable(agentId)}
                        />
                    ) : null}
                </section>

                <AgentDetailsPanel
                    agent={selectedAgent}
                    onEdit={() => openEdit()}
                    onDelete={(agentId) => void handleDelete(agentId)}
                    onEnable={(agentId) => void handleEnable(agentId)}
                    onDisable={(agentId) => void handleDisable(agentId)}
                />
            </div>

            <AgentDialog
                isOpen={createOpen}
                isSaving={isMutating}
                mode="create"
                onClose={() => setCreateOpen(false)}
                onSubmit={(payload) => handleCreate(payload as Parameters<typeof createAgent>[0])}
            />

            <AgentDialog
                isOpen={editOpen && Boolean(selectedAgent)}
                isSaving={isMutating}
                mode="edit"
                agent={selectedAgent}
                onClose={() => setEditOpen(false)}
                onSubmit={(payload) => handleEdit(payload)}
            />
        </div>
    );
};
