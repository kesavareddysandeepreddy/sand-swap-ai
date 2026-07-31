import { useMemo, useState } from "react";

import type { KnowledgeSourceType } from "../../types/api";

interface AddKnowledgeSourceDialogProps {
    isOpen: boolean;
    isMutating: boolean;
    onClose: () => void;
    onCreate: (payload: {
        name: string;
        sourceType: KnowledgeSourceType;
        connectionConfig: Record<string, unknown>;
    }) => Promise<void>;
}

const SOURCE_OPTIONS: Array<{ label: string; value: KnowledgeSourceType }> = [
    { label: "Upload Files", value: "Upload" },
    { label: "GitHub Repository", value: "GitHub" },
    { label: "SharePoint", value: "SharePoint" },
    { label: "OneDrive", value: "OneDrive" },
    { label: "Google Drive", value: "GoogleDrive" },
    { label: "Azure DevOps", value: "AzureDevOps" },
    { label: "Jira", value: "Jira" },
    { label: "Confluence", value: "Confluence" },
    { label: "Website", value: "Website" },
    { label: "Database", value: "Database" },
];

export const AddKnowledgeSourceDialog = ({
    isOpen,
    isMutating,
    onClose,
    onCreate,
}: AddKnowledgeSourceDialogProps) => {
    const [name, setName] = useState("");
    const [sourceType, setSourceType] = useState<KnowledgeSourceType>("Upload");
    const [configText, setConfigText] = useState('{"placeholder": true}');
    const [error, setError] = useState<string | null>(null);

    const canSubmit = useMemo(
        () => name.trim().length > 0 && !isMutating,
        [isMutating, name]
    );

    if (!isOpen) {
        return null;
    }

    const submit = async () => {
        setError(null);
        let parsedConfig: Record<string, unknown> = {};
        try {
            parsedConfig = JSON.parse(configText) as Record<string, unknown>;
        } catch {
            setError("Connector configuration must be valid JSON.");
            return;
        }

        await onCreate({
            name: name.trim(),
            sourceType,
            connectionConfig: parsedConfig,
        });

        setName("");
        setSourceType("Upload");
        setConfigText('{"placeholder": true}');
        onClose();
    };

    return (
        <div className="knowledge-dialog-backdrop" role="presentation">
            <section className="knowledge-dialog" role="dialog" aria-modal="true">
                <header className="knowledge-dialog-header">
                    <h3>Add Knowledge Source</h3>
                    <button type="button" className="memory-row-action" onClick={onClose}>
                        Close
                    </button>
                </header>

                <label className="knowledge-field">
                    <span>Name</span>
                    <input
                        value={name}
                        onChange={(event) => setName(event.target.value)}
                        placeholder="Source display name"
                    />
                </label>

                <label className="knowledge-field">
                    <span>Source Type</span>
                    <select
                        value={sourceType}
                        onChange={(event) => setSourceType(event.target.value as KnowledgeSourceType)}
                    >
                        {SOURCE_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>
                                {option.label}
                            </option>
                        ))}
                    </select>
                </label>

                <label className="knowledge-field">
                    <span>Connector Configuration (placeholder JSON)</span>
                    <textarea
                        rows={5}
                        value={configText}
                        onChange={(event) => setConfigText(event.target.value)}
                    />
                </label>

                {error ? (
                    <p className="error-banner" role="alert">
                        <span className="error-icon" aria-hidden="true">!</span>
                        {error}
                    </p>
                ) : null}

                <footer className="knowledge-dialog-actions">
                    <button type="button" className="memory-row-action" onClick={onClose}>
                        Cancel
                    </button>
                    <button
                        type="button"
                        className="memory-button"
                        onClick={() => void submit()}
                        disabled={!canSubmit}
                    >
                        Add Source
                    </button>
                </footer>
            </section>
        </div>
    );
};
