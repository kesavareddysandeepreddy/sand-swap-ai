import type { AgentRecord } from "../../types/api";
import { formatTimestamp } from "../../utils/date";

interface AgentDetailsPanelProps {
    agent: AgentRecord | null;
    onEdit: (agentId: string) => void;
    onDelete: (agentId: string) => void;
    onEnable: (agentId: string) => void;
    onDisable: (agentId: string) => void;
}

export const AgentDetailsPanel = ({
    agent,
    onEdit,
    onDelete,
    onEnable,
    onDisable,
}: AgentDetailsPanelProps) => {
    if (!agent) {
        return <p className="agent-studio__empty">Select an agent to view details.</p>;
    }

    return (
        <section className="agent-details-card">
            <div className="agent-details-card__header">
                <div>
                    <p className="agent-dialog__eyebrow">Agent Details</p>
                    <h3>{agent.name}</h3>
                </div>
                <span className={`agent-status ${agent.enabled ? "agent-status--enabled" : "agent-status--disabled"}`}>
                    {agent.enabled ? "Enabled" : "Disabled"}
                </span>
            </div>

            <dl className="agent-details-list">
                <div><dt>Role</dt><dd>{agent.role}</dd></div>
                <div><dt>Objective</dt><dd>{agent.objective}</dd></div>
                <div><dt>Description</dt><dd>{agent.description || "-"}</dd></div>
                <div><dt>Tags</dt><dd>{agent.tags.join(", ") || "-"}</dd></div>
                <div><dt>Workspace</dt><dd>{agent.workspace_id}</dd></div>
                <div><dt>Project</dt><dd>{agent.project_id}</dd></div>
                <div><dt>Created Date</dt><dd>{formatTimestamp(agent.created_at)}</dd></div>
                <div><dt>Updated Date</dt><dd>{formatTimestamp(agent.updated_at)}</dd></div>
            </dl>

            <div className="agent-details-card__sections">
                <section>
                    <h4>Permissions</h4>
                    <p>Tools: {agent.tools_allowed.join(", ") || "None"}</p>
                    <p>Connectors: {agent.connectors_allowed.join(", ") || "None"}</p>
                    <p>Approval Required: {agent.approval_required ? "Yes" : "No"}</p>
                </section>
                <section>
                    <h4>Memory Settings</h4>
                    <p>Short-term: {agent.short_term_enabled ? "Enabled" : "Disabled"}</p>
                    <p>Long-term: {agent.long_term_enabled ? "Enabled" : "Disabled"}</p>
                    <p>Project memory: {agent.project_memory_enabled ? "Enabled" : "Disabled"}</p>
                </section>
                <section>
                    <h4>Execution</h4>
                    <p>Max iterations: {agent.max_iterations}</p>
                    <p>Timeout: {agent.timeout}s</p>
                    <p>Retry policy: {JSON.stringify(agent.retry_policy)}</p>
                </section>
                <section>
                    <h4>System Prompt</h4>
                    <pre className="agent-details-card__prompt">{agent.system_prompt}</pre>
                </section>
            </div>

            <div className="agent-details-card__actions">
                <button type="button" className="memory-row-action" onClick={() => onEdit(agent.id)}>Edit</button>
                <button type="button" className="memory-row-action" onClick={() => onDelete(agent.id)}>Delete</button>
                {agent.enabled ? (
                    <button type="button" className="memory-row-action" onClick={() => onDisable(agent.id)}>Disable</button>
                ) : (
                    <button type="button" className="memory-row-action" onClick={() => onEnable(agent.id)}>Enable</button>
                )}
            </div>
        </section>
    );
};
