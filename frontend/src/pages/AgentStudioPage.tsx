import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { agentsApi } from "../api/agents";
import { AgentDialog } from "../components/agent_studio/AgentDialog";
import { useAgents } from "../state/useAgents";
import type {
    AgentDashboardResponse,
    AgentRecord,
    AgentTestRunResponse,
    AgentVersionCompareResponse,
    AgentVersionResponse,
} from "../types/api";
import type { ReturnTypeUseAuth } from "../types/auth";

interface AgentStudioPageProps {
    auth: ReturnTypeUseAuth;
}

type StatusFilter = "all" | "enabled" | "disabled";
type DraftField = keyof AgentRecord;

const PAGE_SIZE = 6;
const DEFAULT_TEST_PROMPT = "Audit the current configuration and recommend the next action.";

const joinList = (values: string[]) => values.join(", ");

const parseList = (value: string) =>
    value.split(",").map((item) => item.trim()).filter(Boolean);

const parseJsonObject = (value: string): Record<string, boolean> => {
    if (!value.trim()) {
        return {};
    }
    const parsed = JSON.parse(value) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("Tool permissions must be a JSON object.");
    }
    return parsed as Record<string, boolean>;
};

const formatCurrency = (value: number) => `${value.toFixed(1)} ms`;

const formatVersionLabel = (version: AgentVersionResponse) =>
    `v${version.version_number} · ${new Date(version.created_at).toLocaleString()}`;

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
        refresh,
    } = useAgents(scopeKey);

    const [search, setSearch] = useState("");
    const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
    const [page, setPage] = useState(1);
    const [createOpen, setCreateOpen] = useState(false);
    const [draft, setDraft] = useState<AgentRecord | null>(null);
    const [draftError, setDraftError] = useState<string | null>(null);
    const [savingDraft, setSavingDraft] = useState(false);

    const [dashboard, setDashboard] = useState<AgentDashboardResponse | null>(null);
    const [versions, setVersions] = useState<AgentVersionResponse[]>([]);
    const [compareResult, setCompareResult] = useState<AgentVersionCompareResponse | null>(null);
    const [compareLeft, setCompareLeft] = useState("");
    const [compareRight, setCompareRight] = useState("");
    const [testRuns, setTestRuns] = useState<AgentTestRunResponse[]>([]);
    const [testPrompt, setTestPrompt] = useState(DEFAULT_TEST_PROMPT);
    const [testRun, setTestRun] = useState<AgentTestRunResponse | null>(null);
    const [isLoadingStudio, setIsLoadingStudio] = useState(false);
    const [studioError, setStudioError] = useState<string | null>(null);
    const [versionError, setVersionError] = useState<string | null>(null);
    const [testError, setTestError] = useState<string | null>(null);
    const [runningTest, setRunningTest] = useState(false);
    const [restoringVersionId, setRestoringVersionId] = useState<string | null>(null);

    const selectedAgent = useMemo(
        () => agents.find((agent) => agent.id === params.agentId) ?? null,
        [agents, params.agentId]
    );

    useEffect(() => {
        if (!params.agentId && agents.length > 0) {
            navigate(`/agent-studio/${agents[0].id}`, { replace: true });
        }
    }, [agents, navigate, params.agentId]);

    useEffect(() => {
        setPage(1);
    }, [search, statusFilter]);

    const filteredAgents = useMemo(() => {
        const query = search.trim().toLowerCase();
        return agents.filter((agent) => {
            const matchesSearch =
                !query
                || agent.name.toLowerCase().includes(query)
                || agent.role.toLowerCase().includes(query)
                || agent.goal.toLowerCase().includes(query)
                || agent.capabilities.some((capability) => capability.toLowerCase().includes(query))
                || agent.tags.some((tag) => tag.toLowerCase().includes(query));
            const matchesStatus =
                statusFilter === "all"
                || (statusFilter === "enabled" && agent.enabled)
                || (statusFilter === "disabled" && !agent.enabled);
            return matchesSearch && matchesStatus;
        });
    }, [agents, search, statusFilter]);

    const totalPages = Math.max(1, Math.ceil(filteredAgents.length / PAGE_SIZE));
    const paginatedAgents = filteredAgents.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

    useEffect(() => {
        if (page > totalPages) {
            setPage(totalPages);
        }
    }, [page, totalPages]);

    useEffect(() => {
        setDraft(selectedAgent);
        setStudioError(null);
        setDraftError(null);
    }, [selectedAgent]);

    useEffect(() => {
        if (!selectedAgent) {
            setDashboard(null);
            setVersions([]);
            setTestRuns([]);
            setCompareResult(null);
            setCompareLeft("");
            setCompareRight("");
            setTestRun(null);
            return;
        }

        let ignore = false;
        setIsLoadingStudio(true);
        setStudioError(null);
        setVersionError(null);
        setTestError(null);
        setCompareResult(null);
        setTestRun(null);

        void Promise.all([
            agentsApi.getDashboard(selectedAgent.id),
            agentsApi.listVersions(selectedAgent.id),
            agentsApi.listTestRuns(selectedAgent.id),
        ])
            .then(([dashboardResult, versionResult, runResult]) => {
                if (ignore) {
                    return;
                }
                setDashboard(dashboardResult);
                setVersions(versionResult);
                setTestRuns(runResult);
                if (versionResult.length >= 2) {
                    setCompareLeft(String(versionResult[0].version_number));
                    setCompareRight(String(versionResult[1].version_number));
                } else if (versionResult.length === 1) {
                    setCompareLeft(String(versionResult[0].version_number));
                    setCompareRight(String(versionResult[0].version_number));
                }
            })
            .catch((error: unknown) => {
                if (!ignore) {
                    setStudioError(error instanceof Error ? error.message : "Failed to load agent studio data.");
                }
            })
            .finally(() => {
                if (!ignore) {
                    setIsLoadingStudio(false);
                }
            });

        return () => {
            ignore = true;
        };
    }, [selectedAgent]);

    const updateDraft = (field: DraftField, value: AgentRecord[DraftField]) => {
        setDraft((current) => (current ? { ...current, [field]: value } : current));
    };

    const handleCreate = async (payload: Parameters<typeof createAgent>[0]) => {
        const agent = await createAgent(payload);
        navigate(`/agent-studio/${agent.id}`);
    };

    const handleSaveDraft = async () => {
        if (!selectedAgent || !draft) {
            return;
        }
        setSavingDraft(true);
        setDraftError(null);
        try {
            await updateAgent(selectedAgent.id, {
                ...draft,
                objective: draft.goal,
                short_term_enabled: draft.conversation_memory_enabled,
                long_term_enabled: draft.long_term_memory_enabled,
            });
        } catch (error) {
            setDraftError(error instanceof Error ? error.message : "Failed to save agent.");
        } finally {
            setSavingDraft(false);
        }
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

    const handleRunTest = async () => {
        if (!selectedAgent) {
            return;
        }
        setRunningTest(true);
        setTestError(null);
        try {
            const result = await agentsApi.runTestPrompt(selectedAgent.id, { prompt: testPrompt.trim() });
            setTestRun(result);
            setTestRuns((current) => [result, ...current.filter((item) => item.id !== result.id)]);
        } catch (error) {
            setTestError(error instanceof Error ? error.message : "Failed to run the test prompt.");
        } finally {
            setRunningTest(false);
        }
    };

    const handleCompare = async () => {
        if (!selectedAgent || !compareLeft || !compareRight) {
            return;
        }
        setVersionError(null);
        try {
            const result = await agentsApi.compareVersions(
                selectedAgent.id,
                Number(compareLeft),
                Number(compareRight)
            );
            setCompareResult(result);
        } catch (error) {
            setVersionError(error instanceof Error ? error.message : "Failed to compare versions.");
        }
    };

    const handleRestoreVersion = async (versionId: string) => {
        if (!selectedAgent) {
            return;
        }
        setRestoringVersionId(versionId);
        setVersionError(null);
        try {
            await agentsApi.restoreVersion(selectedAgent.id, versionId);
            await refresh();
        } catch (error) {
            setVersionError(error instanceof Error ? error.message : "Failed to restore version.");
        } finally {
            setRestoringVersionId(null);
        }
    };

    const capabilitiesText = draft ? joinList(draft.capabilities) : "";
    const toolsText = draft ? joinList(draft.tools_allowed) : "";
    const connectorsText = draft ? joinList(draft.connectors_allowed) : "";
    const knowledgeText = draft ? joinList(draft.knowledge_source_ids) : "";
    const connectedAgentsText = draft ? joinList(draft.connected_agent_ids) : "";
    const toolPermissionsText = draft ? JSON.stringify(draft.tool_permissions, null, 2) : "{}";

    return (
        <div className="agent-studio-page">
            <header className="studio-hero">
                <div className="studio-hero__copy">
                    <p className="agent-dialog__eyebrow">Agent Studio</p>
                    <h1>Visual Agent Builder</h1>
                    <p>
                        Design the agent, wire its memory and knowledge, validate tool access, and review test runs and version history in one workspace.
                    </p>
                </div>
                <div className="studio-hero__metrics">
                    <article>
                        <strong>{agents.length}</strong>
                        <span>Total agents</span>
                    </article>
                    <article>
                        <strong>{enabledCount}</strong>
                        <span>Enabled</span>
                    </article>
                    <article>
                        <strong>{versions.length}</strong>
                        <span>Versions</span>
                    </article>
                    <article>
                        <strong>{testRuns.length}</strong>
                        <span>Test runs</span>
                    </article>
                </div>
            </header>

            <section className="studio-toolbar">
                <input
                    className="studio-input"
                    type="search"
                    placeholder="Search by name, role, goal, capability"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                />
                <select className="studio-input" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}>
                    <option value="all">All statuses</option>
                    <option value="enabled">Enabled</option>
                    <option value="disabled">Disabled</option>
                </select>
                <button type="button" className="memory-button" onClick={() => setCreateOpen(true)}>
                    New Agent
                </button>
            </section>

            {(error ?? studioError) ? (
                <p className="studio-alert" role="alert">
                    <span aria-hidden="true">!</span>
                    {error ?? studioError}
                </p>
            ) : null}

            <div className="studio-grid">
                <aside className="studio-library">
                    <div className="studio-panel__header">
                        <div>
                            <p className="agent-dialog__eyebrow">Library</p>
                            <h2>Agents</h2>
                        </div>
                        <span>{filteredAgents.length} matches</span>
                    </div>

                    {isLoading ? <p className="studio-empty">Loading agents...</p> : null}
                    {!isLoading && paginatedAgents.length === 0 ? (
                        <p className="studio-empty">No agents match the current filter.</p>
                    ) : null}

                    <div className="studio-library__list">
                        {paginatedAgents.map((agent) => {
                            const isActive = selectedAgent?.id === agent.id;
                            return (
                                <button
                                    key={agent.id}
                                    type="button"
                                    className={`studio-library__item ${isActive ? "studio-library__item--active" : ""}`}
                                    onClick={() => navigate(`/agent-studio/${agent.id}`)}
                                >
                                    <div className="studio-library__item-top">
                                        <strong>{agent.name}</strong>
                                        <span className={`agent-status ${agent.enabled ? "agent-status--enabled" : "agent-status--disabled"}`}>
                                            {agent.enabled ? "Enabled" : "Disabled"}
                                        </span>
                                    </div>
                                    <p>{agent.goal || agent.objective || agent.description || "No goal defined"}</p>
                                    <div className="studio-chip-row">
                                        {agent.capabilities.slice(0, 3).map((item) => (
                                            <span key={item} className="agent-tag">{item}</span>
                                        ))}
                                    </div>
                                </button>
                            );
                        })}
                    </div>

                    <div className="studio-pagination">
                        <button type="button" className="memory-row-action" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={page <= 1}>
                            Previous
                        </button>
                        <span>
                            Page {page} of {totalPages}
                        </span>
                        <button type="button" className="memory-row-action" onClick={() => setPage((current) => Math.min(totalPages, current + 1))} disabled={page >= totalPages}>
                            Next
                        </button>
                    </div>
                </aside>

                <main className="studio-designer">
                    <section className="studio-panel">
                        <div className="studio-panel__header">
                            <div>
                                <p className="agent-dialog__eyebrow">Designer</p>
                                <h2>{selectedAgent ? selectedAgent.name : "Select an agent"}</h2>
                            </div>
                            <div className="studio-panel__actions">
                                {selectedAgent ? (
                                    <>
                                        <button type="button" className="memory-row-action" onClick={() => void handleDelete(selectedAgent.id)}>
                                            Delete
                                        </button>
                                        <button type="button" className="memory-row-action" onClick={() => void (selectedAgent.enabled ? handleDisable(selectedAgent.id) : handleEnable(selectedAgent.id))}>
                                            {selectedAgent.enabled ? "Disable" : "Enable"}
                                        </button>
                                        <button type="button" className="memory-button" onClick={() => void handleSaveDraft()} disabled={savingDraft || !draft}>
                                            {savingDraft ? "Saving..." : "Save changes"}
                                        </button>
                                    </>
                                ) : null}
                            </div>
                        </div>

                        {!selectedAgent || !draft ? (
                            <div className="studio-empty studio-empty--large">
                                <h3>Choose an agent to edit</h3>
                                <p>The designer becomes active as soon as you select an agent from the library.</p>
                            </div>
                        ) : (
                            <div className="studio-form-grid">
                                <section className="studio-form-card">
                                    <h3>Agent Designer</h3>
                                    <div className="studio-form-grid--compact">
                                        <label className="agent-field">
                                            <span>Name</span>
                                            <input className="studio-input" value={draft.name} onChange={(event) => updateDraft("name", event.target.value)} />
                                        </label>
                                        <label className="agent-field">
                                            <span>Role</span>
                                            <input className="studio-input" value={draft.role} onChange={(event) => updateDraft("role", event.target.value)} />
                                        </label>
                                        <label className="agent-field agent-field--full">
                                            <span>Description</span>
                                            <input className="studio-input" value={draft.description} onChange={(event) => updateDraft("description", event.target.value)} />
                                        </label>
                                        <label className="agent-field agent-field--full">
                                            <span>Instructions</span>
                                            <textarea className="studio-input" rows={4} value={draft.instructions} onChange={(event) => updateDraft("instructions", event.target.value)} />
                                        </label>
                                        <label className="agent-field agent-field--full">
                                            <span>System Prompt</span>
                                            <textarea className="studio-input" rows={6} value={draft.system_prompt} onChange={(event) => updateDraft("system_prompt", event.target.value)} />
                                        </label>
                                        <label className="agent-field">
                                            <span>Goal</span>
                                            <textarea className="studio-input" rows={3} value={draft.goal} onChange={(event) => updateDraft("goal", event.target.value)} />
                                        </label>
                                        <label className="agent-field">
                                            <span>Expected output</span>
                                            <textarea className="studio-input" rows={3} value={draft.expected_output} onChange={(event) => updateDraft("expected_output", event.target.value)} />
                                        </label>
                                        <label className="agent-field">
                                            <span>Model</span>
                                            <input className="studio-input" value={draft.model} onChange={(event) => updateDraft("model", event.target.value)} />
                                        </label>
                                        <label className="agent-field">
                                            <span>Temperature</span>
                                            <input className="studio-input" type="number" min="0" max="2" step="0.1" value={draft.temperature} onChange={(event) => updateDraft("temperature", Number(event.target.value))} />
                                        </label>
                                    </div>
                                </section>

                                <section className="studio-form-card">
                                    <h3>Capabilities</h3>
                                    <div className="studio-form-grid--compact">
                                        <label className="agent-field">
                                            <span>Capabilities</span>
                                            <textarea className="studio-input" rows={4} value={capabilitiesText} onChange={(event) => updateDraft("capabilities", parseList(event.target.value))} />
                                        </label>
                                        <label className="agent-field">
                                            <span>Tags</span>
                                            <textarea className="studio-input" rows={3} value={joinList(draft.tags)} onChange={(event) => updateDraft("tags", parseList(event.target.value))} />
                                        </label>
                                        <label className="agent-field">
                                            <span>Icon</span>
                                            <input className="studio-input" value={draft.icon} onChange={(event) => updateDraft("icon", event.target.value)} />
                                        </label>
                                        <label className="agent-field">
                                            <span>Color</span>
                                            <input className="studio-input" type="color" value={draft.color} onChange={(event) => updateDraft("color", event.target.value)} />
                                        </label>
                                    </div>
                                </section>

                                <section className="studio-form-card">
                                    <h3>Memory Configuration</h3>
                                    <div className="studio-toggle-grid">
                                        <label className="agent-toggle"><input type="checkbox" checked={draft.agent_memory_enabled} onChange={(event) => updateDraft("agent_memory_enabled", event.target.checked)} /> Agent memory</label>
                                        <label className="agent-toggle"><input type="checkbox" checked={draft.project_memory_enabled} onChange={(event) => updateDraft("project_memory_enabled", event.target.checked)} /> Project memory</label>
                                        <label className="agent-toggle"><input type="checkbox" checked={draft.long_term_memory_enabled} onChange={(event) => updateDraft("long_term_memory_enabled", event.target.checked)} /> Long-term memory</label>
                                        <label className="agent-toggle"><input type="checkbox" checked={draft.conversation_memory_enabled} onChange={(event) => updateDraft("conversation_memory_enabled", event.target.checked)} /> Conversation memory</label>
                                    </div>
                                    <div className="studio-form-grid--compact">
                                        <label className="agent-field">
                                            <span>Memory scope</span>
                                            <select className="studio-input" value={draft.memory_scope} onChange={(event) => updateDraft("memory_scope", event.target.value)}>
                                                <option value="project">Project</option>
                                                <option value="workspace">Workspace</option>
                                                <option value="global">Global</option>
                                            </select>
                                        </label>
                                        <label className="agent-field">
                                            <span>Memory importance</span>
                                            <input className="studio-input" type="number" min="0" max="1" step="0.1" value={draft.memory_importance} onChange={(event) => updateDraft("memory_importance", Number(event.target.value))} />
                                        </label>
                                    </div>
                                </section>

                                <section className="studio-form-card">
                                    <h3>Knowledge Configuration</h3>
                                    <div className="studio-form-grid--compact">
                                        <label className="agent-field">
                                            <span>Knowledge sources</span>
                                            <textarea className="studio-input" rows={3} value={knowledgeText} onChange={(event) => updateDraft("knowledge_source_ids", parseList(event.target.value))} />
                                        </label>
                                        <label className="agent-field">
                                            <span>Document libraries</span>
                                            <textarea className="studio-input" rows={3} value={joinList(draft.document_library_ids)} onChange={(event) => updateDraft("document_library_ids", parseList(event.target.value))} />
                                        </label>
                                        <label className="agent-field">
                                            <span>GitHub repositories</span>
                                            <textarea className="studio-input" rows={3} value={joinList(draft.github_repositories)} onChange={(event) => updateDraft("github_repositories", parseList(event.target.value))} />
                                        </label>
                                        <label className="agent-field">
                                            <span>SharePoint sites</span>
                                            <textarea className="studio-input" rows={3} value={joinList(draft.sharepoint_sites)} onChange={(event) => updateDraft("sharepoint_sites", parseList(event.target.value))} />
                                        </label>
                                    </div>
                                    <label className="agent-toggle">
                                        <input type="checkbox" checked={draft.project_knowledge_enabled} onChange={(event) => updateDraft("project_knowledge_enabled", event.target.checked)} /> Project knowledge enabled
                                    </label>
                                </section>

                                <section className="studio-form-card">
                                    <h3>Tool Configuration</h3>
                                    <div className="studio-form-grid--compact">
                                        <label className="agent-field">
                                            <span>Allowed tools</span>
                                            <textarea className="studio-input" rows={3} value={toolsText} onChange={(event) => updateDraft("tools_allowed", parseList(event.target.value))} />
                                        </label>
                                        <label className="agent-field">
                                            <span>Allowed connectors</span>
                                            <textarea className="studio-input" rows={3} value={connectorsText} onChange={(event) => updateDraft("connectors_allowed", parseList(event.target.value))} />
                                        </label>
                                        <label className="agent-field agent-field--full">
                                            <span>Tool permissions JSON</span>
                                            <textarea className="studio-input" rows={5} value={toolPermissionsText} onChange={(event) => {
                                                try {
                                                    updateDraft("tool_permissions", parseJsonObject(event.target.value));
                                                    setDraftError(null);
                                                } catch (error) {
                                                    setDraftError(error instanceof Error ? error.message : "Tool permissions must be valid JSON.");
                                                }
                                            }} />
                                        </label>
                                        <label className="agent-field">
                                            <span>Connected agents</span>
                                            <textarea className="studio-input" rows={3} value={connectedAgentsText} onChange={(event) => updateDraft("connected_agent_ids", parseList(event.target.value))} />
                                        </label>
                                    </div>
                                </section>

                                <section className="studio-form-card">
                                    <h3>Execution Settings</h3>
                                    <div className="studio-form-grid--compact">
                                        <label className="agent-field">
                                            <span>Execution mode</span>
                                            <select className="studio-input" value={draft.execution_mode} onChange={(event) => updateDraft("execution_mode", event.target.value as AgentRecord["execution_mode"])}>
                                                <option value="sequential">Sequential</option>
                                                <option value="parallel">Parallel</option>
                                            </select>
                                        </label>
                                        <label className="agent-field">
                                            <span>Max iterations</span>
                                            <input className="studio-input" type="number" min="1" max="100" value={draft.max_iterations} onChange={(event) => updateDraft("max_iterations", Number(event.target.value))} />
                                        </label>
                                        <label className="agent-field">
                                            <span>Timeout (seconds)</span>
                                            <input className="studio-input" type="number" min="1" max="3600" value={draft.timeout} onChange={(event) => updateDraft("timeout", Number(event.target.value))} />
                                        </label>
                                        <label className="agent-field">
                                            <span>Retry count</span>
                                            <input className="studio-input" type="number" min="0" max="20" value={draft.retry_count} onChange={(event) => updateDraft("retry_count", Number(event.target.value))} />
                                        </label>
                                        <label className="agent-field agent-field--full">
                                            <span>Retry policy JSON</span>
                                            <textarea className="studio-input" rows={4} value={JSON.stringify(draft.retry_policy, null, 2)} onChange={(event) => {
                                                try {
                                                    const parsed = JSON.parse(event.target.value) as Record<string, unknown>;
                                                    updateDraft("retry_policy", parsed);
                                                    setDraftError(null);
                                                } catch (error) {
                                                    setDraftError(error instanceof Error ? error.message : "Retry policy must be valid JSON.");
                                                }
                                            }} />
                                        </label>
                                    </div>
                                </section>

                                {draftError ? <p className="studio-alert" role="alert"><span aria-hidden="true">!</span>{draftError}</p> : null}
                            </div>
                        )}
                    </section>
                </main>

                <aside className="studio-rail">
                    <section className="studio-panel">
                        <div className="studio-panel__header">
                            <div>
                                <p className="agent-dialog__eyebrow">Dashboard</p>
                                <h2>Live metrics</h2>
                            </div>
                            <span>{isLoadingStudio ? "Loading..." : dashboard ? dashboard.status : "Idle"}</span>
                        </div>

                        {dashboard ? (
                            <div className="studio-metric-grid">
                                <article><strong>{dashboard.success_rate.toFixed(0)}%</strong><span>Success rate</span></article>
                                <article><strong>{formatCurrency(dashboard.average_runtime_ms)}</strong><span>Avg runtime</span></article>
                                <article><strong>{dashboard.knowledge_source_count}</strong><span>Knowledge sources</span></article>
                                <article><strong>{dashboard.connected_agent_count}</strong><span>Connected agents</span></article>
                                <article><strong>{dashboard.total_versions}</strong><span>Versions</span></article>
                                <article><strong>{dashboard.last_run_at ? new Date(dashboard.last_run_at).toLocaleString() : "-"}</strong><span>Last run</span></article>
                            </div>
                        ) : (
                            <p className="studio-empty">Select an agent to load live metrics.</p>
                        )}
                    </section>

                    <section className="studio-panel">
                        <div className="studio-panel__header">
                            <div>
                                <p className="agent-dialog__eyebrow">Testing</p>
                                <h2>Prompt runner</h2>
                            </div>
                        </div>
                        <label className="agent-field">
                            <span>Test prompt</span>
                            <textarea className="studio-input" rows={5} value={testPrompt} onChange={(event) => setTestPrompt(event.target.value)} />
                        </label>
                        <button type="button" className="memory-button" onClick={() => void handleRunTest()} disabled={runningTest || !selectedAgent}>
                            {runningTest ? "Running..." : "Run test"}
                        </button>
                        {testError ? <p className="studio-alert" role="alert"><span aria-hidden="true">!</span>{testError}</p> : null}
                        {testRun ? (
                            <div className="studio-run-card">
                                <h3>{testRun.success ? "Successful run" : "Run failed"}</h3>
                                <p>{testRun.final_answer}</p>
                                <details>
                                    <summary>Reasoning</summary>
                                    <p>{testRun.reasoning}</p>
                                </details>
                                <details>
                                    <summary>Tool calls</summary>
                                    <ul>
                                        {testRun.tool_calls.map((toolCall) => (
                                            <li key={`${toolCall.tool_name}-${toolCall.duration_ms}`}>
                                                {toolCall.tool_name} - {toolCall.success ? "ok" : toolCall.error ?? "failed"}
                                            </li>
                                        ))}
                                    </ul>
                                </details>
                            </div>
                        ) : null}
                        <div className="studio-history">
                            {testRuns.slice(0, 3).map((run) => (
                                <article key={run.id} className="studio-history__item">
                                    <strong>{run.success ? "Pass" : "Fail"}</strong>
                                    <p>{run.prompt}</p>
                                    <span>{new Date(run.created_at).toLocaleString()}</span>
                                </article>
                            ))}
                        </div>
                    </section>

                    <section className="studio-panel">
                        <div className="studio-panel__header">
                            <div>
                                <p className="agent-dialog__eyebrow">Version History</p>
                                <h2>Snapshots</h2>
                            </div>
                        </div>
                        <div className="studio-version-compare">
                            <select className="studio-input" value={compareLeft} onChange={(event) => setCompareLeft(event.target.value)}>
                                {versions.map((version) => (
                                    <option key={version.id} value={version.version_number}>{formatVersionLabel(version)}</option>
                                ))}
                            </select>
                            <select className="studio-input" value={compareRight} onChange={(event) => setCompareRight(event.target.value)}>
                                {versions.map((version) => (
                                    <option key={version.id} value={version.version_number}>{formatVersionLabel(version)}</option>
                                ))}
                            </select>
                            <button type="button" className="memory-row-action" onClick={() => void handleCompare()} disabled={!selectedAgent || versions.length < 2}>
                                Compare
                            </button>
                        </div>
                        {versionError ? <p className="studio-alert" role="alert"><span aria-hidden="true">!</span>{versionError}</p> : null}
                        {compareResult ? (
                            <div className="studio-diff-list">
                                {compareResult.differences.length > 0 ? compareResult.differences.map((difference) => (
                                    <article key={difference.field} className="studio-diff-item">
                                        <strong>{difference.field}</strong>
                                        <p>{String(difference.before ?? "-")} → {String(difference.after ?? "-")}</p>
                                    </article>
                                )) : <p className="studio-empty">No differences between these versions.</p>}
                            </div>
                        ) : null}
                        <div className="studio-version-list">
                            {versions.map((version) => (
                                <article key={version.id} className="studio-version-card">
                                    <div>
                                        <strong>{formatVersionLabel(version)}</strong>
                                        <p>{version.change_summary}</p>
                                    </div>
                                    <button type="button" className="memory-row-action" onClick={() => void handleRestoreVersion(version.id)} disabled={restoringVersionId === version.id}>
                                        {restoringVersionId === version.id ? "Restoring..." : "Restore"}
                                    </button>
                                </article>
                            ))}
                            {versions.length === 0 ? <p className="studio-empty">No saved versions yet.</p> : null}
                        </div>
                    </section>
                </aside>
            </div>

            <AgentDialog
                isOpen={createOpen}
                isSaving={isMutating}
                mode="create"
                onClose={() => setCreateOpen(false)}
                onSubmit={(payload) => handleCreate(payload as Parameters<typeof createAgent>[0])}
            />
        </div>
    );
};
