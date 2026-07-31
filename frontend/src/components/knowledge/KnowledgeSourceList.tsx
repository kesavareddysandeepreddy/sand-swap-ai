import type { KnowledgeSourceRecord } from "../../types/api";
import { KnowledgeSourceCard } from "./KnowledgeSourceCard";

interface KnowledgeSourceListProps {
    sources: KnowledgeSourceRecord[];
    isMutating: boolean;
    onEnable: (id: string) => void;
    onDisable: (id: string) => void;
    onRemove: (id: string) => void;
}

export const KnowledgeSourceList = ({
    sources,
    isMutating,
    onEnable,
    onDisable,
    onRemove,
}: KnowledgeSourceListProps) => {
    if (sources.length === 0) {
        return <p className="memory-status">No knowledge sources configured for this project.</p>;
    }

    return (
        <section className="knowledge-source-list">
            {sources.map((source) => (
                <KnowledgeSourceCard
                    key={source.id}
                    source={source}
                    isMutating={isMutating}
                    onEnable={onEnable}
                    onDisable={onDisable}
                    onRemove={onRemove}
                />
            ))}
        </section>
    );
};
