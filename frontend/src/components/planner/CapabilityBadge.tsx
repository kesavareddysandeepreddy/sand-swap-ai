interface CapabilityBadgeProps {
    capability: string;
}

const CAPABILITY_LABELS: Record<string, string> = {
    filesystem: "Filesystem",
    vision: "Vision",
    python: "Python",
    rest: "REST",
    rag: "RAG",
    memory: "Memory",
    workflow: "Workflow",
    mcp: "MCP",
    document: "Documents",
};

export const CapabilityBadge = ({ capability }: CapabilityBadgeProps) => {
    const normalized = capability.toLowerCase();
    const label = CAPABILITY_LABELS[normalized] ?? capability;

    return <span className="plan-capability-badge">{label}</span>;
};
