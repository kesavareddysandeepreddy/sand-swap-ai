import { useEffect, useMemo, useState } from "react";

import type { AgentCreateRequest, AgentRecord, AgentUpdateRequest } from "../../types/api";

interface AgentDialogProps {
    isOpen: boolean;
    isSaving: boolean;
    mode: "create" | "edit";
    agent?: AgentRecord | null;
    onClose: () => void;
    onSubmit: (payload: AgentCreateRequest | AgentUpdateRequest) => Promise<void>;
}

const splitList = (value: string): string[] =>
    value.split(",").map((item) => item.trim()).filter(Boolean);

const joinList = (values: string[] | undefined): string => (values ?? []).join(", ");

const DEFAULT_RETRY_POLICY = "{}";

export const AgentDialog = ({
    isOpen,
    isSaving,
    mode,
    agent,
    onClose,
    onSubmit,
}: AgentDialogProps) => {
    const [name, setName] = useState("");
    const [description, setDescription] = useState("");
    const [role, setRole] = useState("");
    const [objective, setObjective] = useState("");
    const [systemPrompt, setSystemPrompt] = useState("");
    const [enabled, setEnabled] = useState(true);
    const [shortTermEnabled, setShortTermEnabled] = useState(true);
    const [longTermEnabled, setLongTermEnabled] = useState(true);
    const [projectMemoryEnabled, setProjectMemoryEnabled] = useState(true);
    const [toolsAllowed, setToolsAllowed] = useState("");
    const [connectorsAllowed, setConnectorsAllowed] = useState("");
    const [approvalRequired, setApprovalRequired] = useState(false);
    const [maxIterations, setMaxIterations] = useState("1");
    const [timeout, setTimeoutValue] = useState("60");
    const [retryPolicy, setRetryPolicy] = useState(DEFAULT_RETRY_POLICY);
    const [tags, setTags] = useState("");
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!isOpen) {
            return;
        }
        setName(agent?.name ?? "");
        setDescription(agent?.description ?? "");
        setRole(agent?.role ?? "");
        setObjective(agent?.objective ?? "");
        setSystemPrompt(agent?.system_prompt ?? "");
        setEnabled(agent?.enabled ?? true);
        setShortTermEnabled(agent?.short_term_enabled ?? true);
        setLongTermEnabled(agent?.long_term_enabled ?? true);
        setProjectMemoryEnabled(agent?.project_memory_enabled ?? true);
        setToolsAllowed(joinList(agent?.tools_allowed));
        setConnectorsAllowed(joinList(agent?.connectors_allowed));
        setApprovalRequired(agent?.approval_required ?? false);
        setMaxIterations(String(agent?.max_iterations ?? 1));
        setTimeoutValue(String(agent?.timeout ?? 60));
        setRetryPolicy(JSON.stringify(agent?.retry_policy ?? {}, null, 2));
        setTags(joinList(agent?.tags));
        setError(null);
    }, [agent, isOpen, mode]);

    const canSubmit = useMemo(
        () =>
            !isSaving
            && name.trim().length > 0
            && role.trim().length > 0
            && objective.trim().length > 0
            && systemPrompt.trim().length > 0,
        [isSaving, name, objective, role, systemPrompt]
    );

    if (!isOpen) {
        return null;
    }

    const submit = async () => {
        setError(null);
        let parsedRetryPolicy: Record<string, unknown> = {};
        try {
            const parsed = JSON.parse(retryPolicy || "{}");
            if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
                throw new Error("Retry policy must be a JSON object.");
            }
            parsedRetryPolicy = parsed as Record<string, unknown>;
        } catch (cause) {
            setError(cause instanceof Error ? cause.message : "Retry policy must be valid JSON.");
            return;
        }

        const payload = {
            name: name.trim(),
            description: description.trim(),
            role: role.trim(),
            objective: objective.trim(),
            system_prompt: systemPrompt.trim(),
            enabled,
            short_term_enabled: shortTermEnabled,
            long_term_enabled: longTermEnabled,
            project_memory_enabled: projectMemoryEnabled,
            tools_allowed: splitList(toolsAllowed),
            connectors_allowed: splitList(connectorsAllowed),
            approval_required: approvalRequired,
            max_iterations: Number(maxIterations),
            timeout: Number(timeout),
            retry_policy: parsedRetryPolicy,
            tags: splitList(tags),
        };

        await onSubmit(payload);
        onClose();
    };

    return (
        <div className="agent-dialog-backdrop" role="presentation">
            <section className="agent-dialog" role="dialog" aria-modal="true" aria-label={mode === "create" ? "Create Agent" : "Edit Agent"}>
                <header className="agent-dialog__header">
                    <div>
                        <p className="agent-dialog__eyebrow">Agent Studio</p>
                        <h3>{mode === "create" ? "Create Agent" : "Edit Agent"}</h3>
                    </div>
                    <button type="button" className="memory-row-action" onClick={onClose}>Close</button>
                </header>

                <div className="agent-dialog__grid">
                    <label className="agent-field">
                        <span>Agent Name</span>
                        <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Data Analyst" />
                    </label>
                    <label className="agent-field">
                        <span>Role</span>
                        <input value={role} onChange={(event) => setRole(event.target.value)} placeholder="Research specialist" />
                    </label>
                    <label className="agent-field agent-field--full">
                        <span>Description</span>
                        <input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Summarizes project materials." />
                    </label>
                    <label className="agent-field agent-field--full">
                        <span>Objective</span>
                        <textarea rows={3} value={objective} onChange={(event) => setObjective(event.target.value)} placeholder="Deliver concise project updates." />
                    </label>
                    <label className="agent-field agent-field--full">
                        <span>System Prompt</span>
                        <textarea rows={5} value={systemPrompt} onChange={(event) => setSystemPrompt(event.target.value)} placeholder="You are..." />
                    </label>
                    <label className="agent-field">
                        <span>Tags</span>
                        <input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="research, internal" />
                    </label>
                    <label className="agent-field">
                        <span>Allowed Tools</span>
                        <input value={toolsAllowed} onChange={(event) => setToolsAllowed(event.target.value)} placeholder="search, browser" />
                    </label>
                    <label className="agent-field">
                        <span>Allowed Connectors</span>
                        <input value={connectorsAllowed} onChange={(event) => setConnectorsAllowed(event.target.value)} placeholder="GitHub, SharePoint" />
                    </label>
                    <label className="agent-field">
                        <span>Retry Policy JSON</span>
                        <textarea rows={4} value={retryPolicy} onChange={(event) => setRetryPolicy(event.target.value)} />
                    </label>
                </div>

                <div className="agent-toggle-grid">
                    <label className="agent-toggle"><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} /> Enabled</label>
                    <label className="agent-toggle"><input type="checkbox" checked={shortTermEnabled} onChange={(event) => setShortTermEnabled(event.target.checked)} /> Short-term memory</label>
                    <label className="agent-toggle"><input type="checkbox" checked={longTermEnabled} onChange={(event) => setLongTermEnabled(event.target.checked)} /> Long-term memory</label>
                    <label className="agent-toggle"><input type="checkbox" checked={projectMemoryEnabled} onChange={(event) => setProjectMemoryEnabled(event.target.checked)} /> Project memory</label>
                    <label className="agent-toggle"><input type="checkbox" checked={approvalRequired} onChange={(event) => setApprovalRequired(event.target.checked)} /> Approval required</label>
                </div>

                <div className="agent-dialog__grid agent-dialog__grid--compact">
                    <label className="agent-field">
                        <span>Max Iterations</span>
                        <input type="number" min={1} max={100} value={maxIterations} onChange={(event) => setMaxIterations(event.target.value)} />
                    </label>
                    <label className="agent-field">
                        <span>Timeout (seconds)</span>
                        <input type="number" min={1} max={3600} value={timeout} onChange={(event) => setTimeoutValue(event.target.value)} />
                    </label>
                </div>

                {error ? (
                    <p className="error-banner" role="alert">
                        <span className="error-icon" aria-hidden="true">!</span>
                        {error}
                    </p>
                ) : null}

                <footer className="agent-dialog__actions">
                    <button type="button" className="memory-row-action" onClick={onClose}>Cancel</button>
                    <button type="button" className="memory-button" onClick={() => void submit()} disabled={!canSubmit}>{mode === "create" ? "Create" : "Save"}</button>
                </footer>
            </section>
        </div>
    );
};
