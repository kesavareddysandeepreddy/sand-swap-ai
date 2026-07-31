import type { KnowledgeSourceRecord } from "../../types/api";
import { formatTimestamp } from "../../utils/date";

interface KnowledgeSourceCardProps {
    source: KnowledgeSourceRecord;
    isMutating: boolean;
    onEnable: (id: string) => void;
    onDisable: (id: string) => void;
    onRemove: (id: string) => void;
}

export const KnowledgeSourceCard = ({
    source,
    isMutating,
    onEnable,
    onDisable,
    onRemove,
}: KnowledgeSourceCardProps) => {
    const selectedRepositories = Array.isArray(source.connection_config.selected_repositories)
        ? source.connection_config.selected_repositories
        : [];
    const firstSelectedRepository =
        selectedRepositories.length > 0 && typeof selectedRepositories[0] === "object"
            ? (selectedRepositories[0] as Record<string, unknown>)
            : null;
    const selectedRepository =
        firstSelectedRepository && typeof firstSelectedRepository.repository === "string"
            ? firstSelectedRepository.repository
            : "Not selected";
    const selectedBranch =
        firstSelectedRepository && typeof firstSelectedRepository.branch === "string"
            ? firstSelectedRepository.branch
            : firstSelectedRepository &&
                typeof firstSelectedRepository.default_branch === "string"
                ? firstSelectedRepository.default_branch
                : "Not selected";

    return (
        <article className="knowledge-source-card">
            <header className="knowledge-source-card-header">
                <div>
                    <h3>{source.name}</h3>
                    <p>
                        <span className="knowledge-chip">{source.source_type}</span>
                        <span className="knowledge-chip">status: {source.status}</span>
                    </p>
                </div>
                <span
                    className={`knowledge-enabled-pill ${source.enabled ? "knowledge-enabled-pill--on" : "knowledge-enabled-pill--off"
                        }`}
                >
                    {source.enabled ? "Enabled" : "Disabled"}
                </span>
            </header>

            <dl className="knowledge-source-stats">
                <div>
                    <dt>Files</dt>
                    <dd>{source.file_count}</dd>
                </div>
                <div>
                    <dt>Chunks</dt>
                    <dd>{source.chunk_count}</dd>
                </div>
                <div>
                    <dt>Embeddings</dt>
                    <dd>{source.embedding_count}</dd>
                </div>
                <div>
                    <dt>Last Sync</dt>
                    <dd>{source.last_sync ? formatTimestamp(source.last_sync) : "Never"}</dd>
                </div>
            </dl>

            {source.source_type === "GitHub" ? (
                <section className="knowledge-connection-preview">
                    <p>
                        Repository: {selectedRepository.includes("/")
                            ? selectedRepository.split("/").pop()
                            : selectedRepository}
                    </p>
                    <p>Branch: {selectedBranch}</p>
                    <p>Status: {source.enabled ? "Connected" : "Disabled"}</p>
                    <p>Indexed Files: {source.file_count}</p>
                    <p>Last Sync: {source.last_sync ? formatTimestamp(source.last_sync) : "Never"}</p>
                </section>
            ) : null}

            <div className="knowledge-source-actions">
                {source.enabled ? (
                    <button
                        type="button"
                        className="memory-row-action"
                        onClick={() => onDisable(source.id)}
                        disabled={isMutating}
                    >
                        Disable
                    </button>
                ) : (
                    <button
                        type="button"
                        className="memory-row-action"
                        onClick={() => onEnable(source.id)}
                        disabled={isMutating}
                    >
                        Enable
                    </button>
                )}
                <button
                    type="button"
                    className="memory-row-action memory-row-action--danger"
                    onClick={() => onRemove(source.id)}
                    disabled={isMutating}
                >
                    Remove
                </button>
            </div>
        </article>
    );
};
