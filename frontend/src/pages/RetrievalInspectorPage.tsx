import { useMemo, useState } from "react";

import { documentsApi } from "../api/documents";
import type { RetrievedChunk } from "../types/api";

export const RetrievalInspectorPage = () => {
    const [query, setQuery] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [chunks, setChunks] = useState<RetrievedChunk[]>([]);
    const [citations, setCitations] = useState<string[]>([]);

    const hasResults = useMemo(() => chunks.length > 0, [chunks.length]);

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
                                    score={chunk.score.toFixed(4)} source={chunk.document_name} chunk={chunk.chunk_id}
                                </p>
                                <p>{chunk.text}</p>
                                <pre>{JSON.stringify(chunk.metadata, null, 2)}</pre>
                            </article>
                        ))}
                    </div>

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
