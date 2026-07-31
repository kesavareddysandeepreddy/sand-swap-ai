import { useState } from "react";

import { AddKnowledgeSourceDialog } from "../components/knowledge/AddKnowledgeSourceDialog";
import { KnowledgeSourceList } from "../components/knowledge/KnowledgeSourceList";
import { useKnowledgeSources } from "../state/useKnowledgeSources";
import { useAuth } from "../state/useAuth";
import type { KnowledgeSourceType } from "../types/api";

interface KnowledgeSourcesPageProps {
    projectId: string;
}

interface GitHubRepositoryItem {
    repository: string;
    name: string;
    owner: string;
    default_branch: string;
    branches: string[];
    private: boolean;
    updated_at: string;
}

const asString = (value: unknown, fallback = ""): string =>
    typeof value === "string" ? value : fallback;

const asStringArray = (value: unknown): string[] =>
    Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];

const parseGitHubRepositories = (discoverPayload: unknown): GitHubRepositoryItem[] => {
    let items: Array<Record<string, unknown>> = [];
    if (Array.isArray(discoverPayload)) {
        items = discoverPayload.filter(
            (item): item is Record<string, unknown> =>
                Boolean(item) && typeof item === "object"
        );
    } else if (discoverPayload && typeof discoverPayload === "object") {
        const payloadRecord = discoverPayload as Record<string, unknown>;
        if (Array.isArray(payloadRecord.items)) {
            items = payloadRecord.items.filter(
                (item): item is Record<string, unknown> =>
                    Boolean(item) && typeof item === "object"
            );
        } else if (Array.isArray(payloadRecord.repositories)) {
            items = [payloadRecord];
        }
    }

    const repositories: GitHubRepositoryItem[] = [];
    for (const item of items) {
        const rawRepositories = Array.isArray(item.repositories)
            ? item.repositories
            : item.repository
                ? [item]
                : [];
        for (const rawRepository of rawRepositories) {
            if (!rawRepository || typeof rawRepository !== "object") {
                continue;
            }
            const record = rawRepository as Record<string, unknown>;
            const repository = asString(record.repository);
            const name = asString(record.name);
            const owner = asString(record.owner);
            const defaultBranch = asString(record.default_branch, "main");
            if (!repository || !name || !owner) {
                continue;
            }
            repositories.push({
                repository,
                name,
                owner,
                default_branch: defaultBranch,
                branches: asStringArray(record.branches),
                private: Boolean(record.private),
                updated_at: asString(record.updated_at),
            });
        }
    }
    return repositories;
};

const getConfiguredGitHubSelection = (
    connectionConfig: Record<string, unknown>
): { repository: string; branch: string } | null => {
    const rawSelected = connectionConfig.selected_repositories;
    if (!Array.isArray(rawSelected) || rawSelected.length === 0) {
        return null;
    }
    const first = rawSelected[0];
    if (!first || typeof first !== "object") {
        return null;
    }
    const selected = first as Record<string, unknown>;
    const repository = asString(selected.repository);
    if (!repository) {
        return null;
    }
    return {
        repository,
        branch: asString(selected.branch, asString(selected.default_branch, "main")),
    };
};

export const KnowledgeSourcesPage = ({ projectId }: KnowledgeSourcesPageProps) => {
    const auth = useAuth();
    console.log("AUTH", auth);
    const {
        sources,
        health,
        isLoading,
        isMutating,
        error,
        refresh,
        createSource,
        enableSource,
        disableSource,
        removeSource,
        connectConnector,
        discoverConnector,
        syncConnector,
        connectorHealth,
        connectorDetails,
    } = useKnowledgeSources(projectId);

    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const [selectedSourceId, setSelectedSourceId] = useState<string>("");
    const [authToken, setAuthToken] = useState<string>("");
    const [sharepointToken, setSharepointToken] = useState<string>("");
    const [sharepointTenant, setSharepointTenant] = useState<string>("");
    const [githubRepositories, setGithubRepositories] = useState<GitHubRepositoryItem[]>([]);
    const [selectedRepository, setSelectedRepository] = useState<string>("");
    const [selectedBranch, setSelectedBranch] = useState<string>("");
    const uploadConnectorStatus = health?.connectors?.Upload ?? "unknown";
    const connectorEntries = health ? Object.entries(health.connectors) : [];

    const create = async (payload: {
        name: string;
        sourceType: KnowledgeSourceType;
        connectionConfig: Record<string, unknown>;
    }) => {
        await createSource({
            name: payload.name,
            source_type: payload.sourceType,
            connection_config: payload.connectionConfig,
            metadata: { placeholder_ui: true },
        });
    };

    const onRemove = async (id: string) => {
        const confirmed = window.confirm("Remove this knowledge source?");
        if (!confirmed) {
            return;
        }
        await removeSource(id);
    };

    const selectedSource = sources.find((source) => source.id === selectedSourceId) ?? null;
    const selectedConnectorDetail = selectedSourceId
        ? connectorDetails[selectedSourceId]
        : undefined;
    const configuredGitHubSelection =
        selectedSource?.source_type === "GitHub"
            ? getConfiguredGitHubSelection(selectedSource.connection_config)
            : null;

    const selectedRepositoryRecord = githubRepositories.find(
        (repository) => repository.repository === selectedRepository
    );
    const selectedRepositoryBranches = selectedRepositoryRecord
        ? selectedRepositoryRecord.branches.length > 0
            ? selectedRepositoryRecord.branches
            : [selectedRepositoryRecord.default_branch]
        : [];

    const runConnect = async () => {
        if (!selectedSource) {
            return;
        }
        if (selectedSource.source_type === "GitHub") {
            if (!selectedRepository || !selectedBranch) {
                return;
            }
            const repositoryRecord = githubRepositories.find(
                (repository) => repository.repository === selectedRepository
            );
            if (!repositoryRecord) {
                return;
            }
            const tokenFromConfig =
                typeof selectedSource.connection_config.token === "string"
                    ? selectedSource.connection_config.token
                    : "";
            const effectiveToken = authToken.trim() || tokenFromConfig.trim();
            await connectConnector(selectedSource.id, {
                connection_config: {
                    token: effectiveToken,
                    selected_repositories: [
                        {
                            repository: repositoryRecord.repository,
                            name: repositoryRecord.name,
                            owner: repositoryRecord.owner,
                            default_branch: repositoryRecord.default_branch,
                            branch: selectedBranch,
                        },
                    ],
                    project_id: selectedSource.project_id,
                    workspace_id: auth.activeWorkspaceId ?? "default",
                    owner_id: auth.effectiveUserId,
                },
            });
            setAuthToken("");
            return;
        }
        if (selectedSource.source_type === "SharePoint") {
            await connectConnector(selectedSource.id, {
                connection_config: {
                    access_token: sharepointToken,
                    tenant_id: sharepointTenant,
                    selected_folders: selectedSource.connection_config.selected_folders ?? [],
                    project_id: selectedSource.project_id,
                    workspace_id: auth.activeWorkspaceId ?? "default",
                    owner_id: auth.effectiveUserId,
                },
            });
        }
    };

    const runDiscover = async () => {
        if (!selectedSource) {
            return;
        }

        if (selectedSource.source_type === "GitHub") {
            const tokenFromConfig =
                typeof selectedSource.connection_config.token === "string"
                    ? selectedSource.connection_config.token
                    : "";
            const enteredToken = authToken.trim();

            // Browse depends on persisted connector config, so persist entered token first.
            if (enteredToken && enteredToken !== tokenFromConfig.trim()) {
                await connectConnector(selectedSource.id, {
                    connection_config: {
                        ...selectedSource.connection_config,
                        token: enteredToken,
                        project_id: selectedSource.project_id,
                        workspace_id: auth.activeWorkspaceId ?? "default",
                        owner_id: auth.effectiveUserId,
                    },
                });
                setAuthToken("");
            }
        }

        const payload = await discoverConnector(selectedSource.id);
        const payloadRecord = payload as unknown as Record<string, unknown>;
        console.debug("KnowledgeSources Browse payload", payload);
        console.debug("KnowledgeSources Browse payload.items", payloadRecord.items);
        if (selectedSource.source_type === "GitHub") {
            const repositories = parseGitHubRepositories(payload);
            console.debug("KnowledgeSources Browse parsed repositories", repositories);
            console.debug(
                "KnowledgeSources Browse githubRepositories.length",
                repositories.length
            );
            setGithubRepositories(repositories);
            if (repositories.length > 0) {
                const configuredRepository = configuredGitHubSelection?.repository;
                const fallbackRepository = repositories[0];
                const selected =
                    repositories.find(
                        (repository) => repository.repository === configuredRepository
                    ) ?? fallbackRepository;
                setSelectedRepository(selected.repository);
                setSelectedBranch(
                    configuredGitHubSelection?.branch || selected.default_branch
                );
            } else {
                setSelectedRepository("");
                setSelectedBranch("");
            }
        }
    };

    const runSync = async (incremental = false) => {
        if (!selectedSource) {
            return;
        }
        await syncConnector(selectedSource.id, incremental);
        await connectorHealth(selectedSource.id);
    };

    return (
        <div className="knowledge-page">
            <section className="knowledge-toolbar">
                <h2>Knowledge Sources</h2>
                <div className="memory-actions">
                    <button
                        type="button"
                        className="memory-button"
                        onClick={() => void refresh()}
                        disabled={isLoading || isMutating}
                    >
                        Refresh
                    </button>
                    <button
                        type="button"
                        className="memory-button"
                        onClick={() => setIsDialogOpen(true)}
                        disabled={isMutating}
                    >
                        Add Source
                    </button>
                </div>
            </section>

            {health ? (
                <section className="knowledge-health">
                    <p>
                        Health: <strong>{health.status}</strong>
                    </p>
                    <p>Registered connectors: {health.connectors_total}</p>
                    <p>
                        Upload Connector: <strong>{uploadConnectorStatus}</strong>
                    </p>
                    {connectorEntries.length > 0 ? (
                        <p>
                            Connector Statuses:{" "}
                            {connectorEntries
                                .map(([name, status]) => `${name}=${status}`)
                                .join(" | ")}
                        </p>
                    ) : null}
                </section>
            ) : null}

            {error ? (
                <p className="error-banner" role="alert">
                    <span className="error-icon" aria-hidden="true">!</span>
                    {error}
                </p>
            ) : null}

            {isLoading ? <p className="memory-status">Loading knowledge sources...</p> : null}

            <KnowledgeSourceList
                sources={sources}
                isMutating={isMutating}
                onEnable={(id) => void enableSource(id)}
                onDisable={(id) => void disableSource(id)}
                onRemove={(id) => void onRemove(id)}
            />

            <section className="knowledge-health">
                <p>
                    <strong>Enterprise Connectors</strong>
                </p>
                <label className="knowledge-field">
                    <span>Select Source</span>
                    <select
                        value={selectedSourceId}
                        onChange={(event) => {
                            const nextSourceId = event.target.value;
                            setSelectedSourceId(nextSourceId);
                            setGithubRepositories([]);
                            setSelectedRepository("");
                            setSelectedBranch("");
                        }}
                    >
                        <option value="">Choose a source</option>
                        {sources
                            .filter(
                                (source) =>
                                    source.source_type === "GitHub" ||
                                    source.source_type === "SharePoint"
                            )
                            .map((source) => (
                                <option key={source.id} value={source.id}>
                                    {source.name} ({source.source_type})
                                </option>
                            ))}
                    </select>
                </label>

                {selectedSource?.source_type === "GitHub" ? (
                    <>
                        <label className="knowledge-field">
                            <span>GitHub Personal Access Token</span>
                            <input
                                type="password"
                                value={authToken}
                                onChange={(event) => setAuthToken(event.target.value)}
                                placeholder="ghp_..."
                            />
                        </label>

                        {githubRepositories.length > 0 ? (
                            <section className="knowledge-health" aria-label="GitHub repository browser">
                                <p>
                                    <strong>Repository Discovery</strong>
                                </p>
                                {githubRepositories.map((repository) => {
                                    const isSelected = selectedRepository === repository.repository;
                                    const visibility = repository.private ? "Private" : "Public";
                                    return (
                                        <article key={repository.repository} className="memory-card">
                                            <p>
                                                <strong>{repository.name}</strong>
                                            </p>
                                            <p>Owner: {repository.owner}</p>
                                            <p>{visibility}</p>
                                            <p>Default Branch: {repository.default_branch}</p>
                                            <p>Last Updated: {repository.updated_at || "Unknown"}</p>
                                            <button
                                                type="button"
                                                className="memory-button"
                                                onClick={() => {
                                                    setSelectedRepository(repository.repository);
                                                    setSelectedBranch(repository.default_branch);
                                                }}
                                                disabled={isMutating}
                                            >
                                                {isSelected ? "Selected" : "Select"}
                                            </button>
                                        </article>
                                    );
                                })}
                            </section>
                        ) : null}

                        {selectedRepository ? (
                            <label className="knowledge-field">
                                <span>Branch</span>
                                <select
                                    value={selectedBranch || selectedRepositoryRecord?.default_branch || "main"}
                                    onChange={(event) => setSelectedBranch(event.target.value)}
                                >
                                    {selectedRepositoryBranches.map((branch) => (
                                        <option key={branch} value={branch}>
                                            {branch}
                                        </option>
                                    ))}
                                </select>
                            </label>
                        ) : null}
                    </>
                ) : null}

                {selectedSource?.source_type === "SharePoint" ? (
                    <>
                        <label className="knowledge-field">
                            <span>SharePoint Access Token</span>
                            <input
                                type="password"
                                value={sharepointToken}
                                onChange={(event) => setSharepointToken(event.target.value)}
                                placeholder="Bearer token"
                            />
                        </label>
                        <label className="knowledge-field">
                            <span>Tenant ID</span>
                            <input
                                value={sharepointTenant}
                                onChange={(event) => setSharepointTenant(event.target.value)}
                                placeholder="tenant.onmicrosoft.com or GUID"
                            />
                        </label>
                    </>
                ) : null}

                <div className="memory-actions">
                    <button
                        type="button"
                        className="memory-button"
                        disabled={
                            !selectedSource ||
                            isMutating ||
                            (
                                selectedSource.source_type === "GitHub" &&
                                (!selectedRepository || !selectedBranch)
                            )
                        }
                        onClick={() => void runConnect()}
                    >
                        {selectedSource?.source_type === "GitHub" ? "Save Selection" : "Connect"}
                    </button>
                    <button
                        type="button"
                        className="memory-button"
                        disabled={!selectedSource || isMutating}
                        onClick={() => void runDiscover()}
                    >
                        Browse
                    </button>
                    <button
                        type="button"
                        className="memory-button"
                        disabled={!selectedSource || isMutating}
                        onClick={() => void runSync(false)}
                    >
                        Sync
                    </button>
                    <button
                        type="button"
                        className="memory-button"
                        disabled={!selectedSource || isMutating}
                        onClick={() => void runSync(true)}
                    >
                        Incremental Sync
                    </button>
                </div>

                {selectedSource && selectedConnectorDetail ? (
                    <p>
                        Connector Status: <strong>{selectedConnectorDetail.status}</strong> ({selectedConnectorDetail.detail})
                    </p>
                ) : null}

                {selectedSource ? (
                    <p>
                        Indexed files: <strong>{selectedSource.file_count}</strong> | Last sync: <strong>{selectedSource.last_sync ?? "Never"}</strong>
                    </p>
                ) : null}

                {selectedSource?.source_type === "GitHub" && configuredGitHubSelection ? (
                    <section className="knowledge-health" aria-label="GitHub connector summary">
                        <p>
                            <strong>GitHub</strong>
                        </p>
                        <p>
                            Repository
                            <br />
                            <strong>{configuredGitHubSelection.repository.split("/").pop() || configuredGitHubSelection.repository}</strong>
                        </p>
                        <p>
                            Branch
                            <br />
                            <strong>{configuredGitHubSelection.branch || "main"}</strong>
                        </p>
                        <p>
                            Status
                            <br />
                            <strong>Connected</strong>
                        </p>
                        <p>
                            Last Sync
                            <br />
                            <strong>{selectedSource.last_sync ?? "Never"}</strong>
                        </p>
                        <p>
                            Indexed Files
                            <br />
                            <strong>{selectedSource.file_count}</strong>
                        </p>
                        <p>
                            Health
                            <br />
                            <strong>{selectedConnectorDetail?.status ?? "unknown"}</strong>
                        </p>
                    </section>
                ) : null}
            </section>

            <AddKnowledgeSourceDialog
                isOpen={isDialogOpen}
                isMutating={isMutating}
                onClose={() => setIsDialogOpen(false)}
                onCreate={create}
            />
        </div>
    );
};
