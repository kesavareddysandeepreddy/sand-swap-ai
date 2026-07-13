import { useMemo, useState, type ReactNode } from "react";

import { documentsApi } from "../api/documents";
import type { DocumentRecord, RetrievedChunk } from "../types/api";

export const RetrievalInspectorPage = () => {
    const [query, setQuery] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [chunks, setChunks] = useState<RetrievedChunk[]>([]);
    const [citations, setCitations] = useState<string[]>([]);
    const [sourceDocument, setSourceDocument] = useState<DocumentRecord | null>(null);
    const [sourceLoading, setSourceLoading] = useState(false);

    const hasResults = useMemo(() => chunks.length > 0, [chunks.length]);

    const queryTerms = useMemo(
        () =>
            query
                .toLowerCase()
                .split(/\s+/)
                .map((term) => term.trim())
                .filter((term) => term.length > 2),
        [query]
    );

    const highlightText = (text: string): ReactNode[] => {
        if (queryTerms.length === 0) {
            return [text];
        }

        const escapedTerms = queryTerms.map((term) =>
            term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
        );
        const pattern = new RegExp(`(${escapedTerms.join("|")})`, "gi");
        const parts = text.split(pattern);
        return parts.map((part, index) => {
            const isMatch = queryTerms.some(
                (term) => part.toLowerCase() === term.toLowerCase()
            );
            if (!isMatch) {
                return part;
            }
            return <mark key={`term-${index}`}>{part}</mark>;
        });
    };

    const getNumericValue = (value: unknown): number | null => {
        if (typeof value === "number" && Number.isFinite(value)) {
            return value;
        }
        if (typeof value === "string") {
            const parsed = Number(value);
            if (Number.isFinite(parsed)) {
                return parsed;
            }
        }
        return null;
    };

    const formatScore = (
        metadata: Record<string, unknown>,
        key: string,
        fallback?: unknown
    ): string => {
        const value = getNumericValue(metadata[key]) ?? getNumericValue(fallback);
        return value === null ? "N/A" : value.toFixed(4);
    };

    const getMatchReason = (chunk: RetrievedChunk): string => {
        const reason = chunk.metadata.match_reason;
        if (typeof reason === "string" && reason.trim().length > 0) {
            return reason;
        }

        const lowerText = chunk.text.toLowerCase();
        const matchedTerms = queryTerms.filter((term) => lowerText.includes(term));
        if (matchedTerms.length > 0) {
            return `Matched terms: ${matchedTerms.slice(0, 6).join(", ")}`;
        }
        return "Semantic similarity to query context";
    };

    const loadSourceDocument = async (documentId: string) => {
        setSourceLoading(true);
        try {
            const document = await documentsApi.getById(documentId);
            setSourceDocument(document);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load source document metadata.");
        } finally {
            setSourceLoading(false);
        }
    };

    const inspect = async () => {
        if (!query.trim()) {
            return;
        }

        setIsLoading(true);
        setError(null);
        try {
            const response = await documentsApi.retrieve({ query, topK: 8 });
            setChunks(response.chunks);
            setCitations(response.citations);
            setSourceDocument(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to run retrieval inspection.");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="inspector-page">
            <section className="inspector-toolbar">
                <input
                    className="documents-search"
                    type="search"
                    placeholder="Ask: What chunks are relevant for this query?"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                />
                <button
                    type="button"
                    className="memory-button"
                    disabled={isLoading || !query.trim()}
                    onClick={() => void inspect()}
                >
                    {isLoading ? "Inspecting..." : "Run Inspector"}
                </button>
            </section>

            {error ? (
                <p className="error-banner" role="alert">
                    <span className="error-icon" aria-hidden="true">!</span>
                    {error}
                </p>
            ) : null}

            {!hasResults && !isLoading ? (
                <p className="memory-status">Run a query to inspect retrieval quality.</p>
            ) : null}

            {hasResults ? (
                <section className="inspector-results">
                    <h2>Retrieved Chunks</h2>
                    <div className="documents-chunk-list">
                        {chunks.map((chunk) => (
                            <article key={chunk.chunk_id} className="documents-chunk-card">
                                <p className="documents-chunk-meta">
                                    semantic={formatScore(chunk.metadata, "semantic_score", chunk.score)} keyword={formatScore(chunk.metadata, "keyword_score", 0)} combined={formatScore(chunk.metadata, "combined_score", chunk.score)} source={chunk.document_name} chunk={chunk.chunk_id}
                                </p>
                                <p>{getMatchReason(chunk)}</p>
                                <p>{highlightText(chunk.text)}</p>
                                <button
                                    type="button"
                                    className="memory-row-action"
                                    onClick={() => void loadSourceDocument(chunk.document_id)}
                                    disabled={sourceLoading}
                                >
                                    {sourceLoading ? "Loading source..." : "View Source Metadata"}
                                </button>
                                <pre>{JSON.stringify(chunk.metadata, null, 2)}</pre>
                            </article>
                        ))}
                    </div>

                    {sourceDocument ? (
                        <section className="documents-viewer-card">
                            <h2>Source Document</h2>
                            <p className="documents-chunk-meta">
                                {sourceDocument.name} parser={String(sourceDocument.metadata.parser ?? "-")} pages={String(sourceDocument.metadata.pages ?? "-")} tables={String(sourceDocument.metadata.tables ?? "-")} images={String(sourceDocument.metadata.images ?? "-")}
                            </p>
                            <pre>{JSON.stringify(sourceDocument.metadata, null, 2)}</pre>
                        </section>
                    ) : null}

                    <h2>Citations</h2>
                    <ul className="inspector-citations">
                        {citations.map((citation) => (
                            <li key={citation}>{citation}</li>
                        ))}
                    </ul>
                </section>
            ) : null}
        </div>
    );
};
