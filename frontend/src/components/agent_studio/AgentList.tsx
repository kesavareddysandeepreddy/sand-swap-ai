import type { AgentRecord } from "../../types/api";
import { formatTimestamp } from "../../utils/date";

interface AgentListProps {
    agents: AgentRecord[];
    selectedAgentId: string | null;
    onSelect: (agentId: string) => void;
    onEdit: (agentId: string) => void;
    onDelete: (agentId: string) => void;
    onEnable: (agentId: string) => void;
    onDisable: (agentId: string) => void;
}

export const AgentList = ({
    agents,
    selectedAgentId,
    onSelect,
    onEdit,
    onDelete,
    onEnable,
    onDisable,
}: AgentListProps) => {
    if (agents.length === 0) {
        return <p className="agent-studio__empty">No agents created yet.</p>;
    }

    return (
        <div className="agent-table-wrap">
            <table className="agent-table">
                <thead>
                    <tr>
                        <th>Agent Name</th>
                        <th>Role</th>
                        <th>Status</th>
                        <th>Tags</th>
                        <th>Created Date</th>
                        <th>Workspace</th>
                        <th>Project</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {agents.map((agent) => (
                        <tr
                            key={agent.id}
                            className={selectedAgentId === agent.id ? "agent-table__row--selected" : ""}
                            onClick={() => onSelect(agent.id)}
                        >
                            <td>
                                <div className="agent-table__name">{agent.name}</div>
                                <div className="agent-table__subtitle">{agent.description || "No description"}</div>
                            </td>
                            <td>{agent.role}</td>
                            <td>
                                <span className={`agent-status ${agent.enabled ? "agent-status--enabled" : "agent-status--disabled"}`}>
                                    {agent.enabled ? "Enabled" : "Disabled"}
                                </span>
                            </td>
                            <td>
                                <div className="agent-tags">
                                    {agent.tags.length > 0 ? agent.tags.map((tag) => <span key={tag} className="agent-tag">{tag}</span>) : <span className="agent-table__subtitle">-</span>}
                                </div>
                            </td>
                            <td>{formatTimestamp(agent.created_at)}</td>
                            <td>{agent.workspace_id}</td>
                            <td>{agent.project_id}</td>
                            <td>
                                <div className="agent-row-actions">
                                    <button type="button" className="memory-row-action" onClick={(event) => { event.stopPropagation(); onEdit(agent.id); }}>Edit</button>
                                    <button type="button" className="memory-row-action" onClick={(event) => { event.stopPropagation(); onDelete(agent.id); }}>Delete</button>
                                    {agent.enabled ? (
                                        <button type="button" className="memory-row-action" onClick={(event) => { event.stopPropagation(); onDisable(agent.id); }}>Disable</button>
                                    ) : (
                                        <button type="button" className="memory-row-action" onClick={(event) => { event.stopPropagation(); onEnable(agent.id); }}>Enable</button>
                                    )}
                                </div>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};
