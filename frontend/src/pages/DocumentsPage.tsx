import { useMemo, useState } from "react";

import { useDocuments } from "../state/useDocuments";
import type { DocumentRecord } from "../types/api";
import { formatTimestamp } from "../utils/date";

const formatBytes = (value: number): string => {
    if (value < 1024) {
        return `${value} B`;
    }
    if (value < 1024 * 1024) {
        return `${(value / 1024).toFixed(1)} KB`;
    }
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
};

const getIconForType = (fileType: string): string => {
    if (["pdf"].includes(fileType)) {
        return "[PDF]";
    }
    if (["doc", "docx", "odt", "rtf"].includes(fileType)) {
        return "[DOC]";
    }
    if (["xls", "xlsx", "ods", "csv", "tsv"].includes(fileType)) {
        return "[SHEET]";
    }
    if (["ppt", "pptx", "odp"].includes(fileType)) {
        return "[SLIDE]";
    }
    if (["png", "jpg", "jpeg", "gif", "webp", "tif", "tiff", "bmp", "svg"].includes(fileType)) {
        return "[IMG]";
    }
    if (["zip"].includes(fileType)) {
        return "[ZIP]";
    }
    if (["py", "js", "ts", "tsx", "jsx", "java", "go", "rs"].includes(fileType)) {
        return "[CODE]";
    }
    return "[FILE]";
};

const getNumberMeta = (metadata: Record<string, unknown>, key: string): number => {
    const value = metadata[key];
    if (typeof value === "number" && Number.isFinite(value)) {
        return value;
    }
    if (typeof value === "string") {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : 0;
    }
    return 0;
};

export const DocumentsPage = () => {
    const {
        documents,
        selectedDocument,
        selectedChunks,
        categories,
        isLoading,
        isUploading,
        error,
        refresh,
        upload,
        selectDocument,
        deleteOne,
        deleteAll,
    } = useDocuments();

    const [search, setSearch] = useState("");
    const [fileType, setFileType] = useState("");
    const [category, setCategory] = useState("");

    const filtered = useMemo(
        () =>
            documents.filter((document) => {
                const matchesSearch =
                    !search ||
                    document.name.toLowerCase().includes(search.toLowerCase()) ||
                    document.original_filename
                        .toLowerCase()
                        .includes(search.toLowerCase());
                const matchesType = !fileType || document.file_type === fileType;
                const matchesCategory =
                    !category || document.metadata.category === category;
                return matchesSearch && matchesType && matchesCategory;
            }),
        [category, documents, fileType, search]
    );

    const fileTypes = useMemo(
        () => Array.from(new Set(documents.map((document) => document.file_type))).sort(),
        [documents]
    );

    const onFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) {
            return;
        }

        await upload({ file });
        await refresh();
        event.target.value = "";
    };

    const onDelete = async (document: DocumentRecord) => {
        const confirmed = window.confirm(`Delete document "${document.name}"?`);
        if (!confirmed) {
            return;
        }
        await deleteOne(document.id);
        await refresh();
    };

    const onDeleteAll = async () => {
        const confirmed = window.confirm("Delete all documents? This cannot be undone.");
        if (!confirmed) {
            return;
        }
        await deleteAll();
        await refresh();
    };

    return (
        <div className="documents-page">
            <section className="documents-toolbar">
                <div className="documents-upload-wrap">
                    <label className="documents-upload-label" htmlFor="document-upload">
                        {isUploading ? "Uploading..." : "Upload Document"}
                    </label>
                    <input
                        id="document-upload"
                        type="file"
                        className="documents-upload-input"
                        onChange={(event) => void onFileUpload(event)}
                        disabled={isUploading}
                    />
                </div>
                <input
                    className="documents-search"
                    type="search"
                    placeholder="Search documents"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                />
                <select
                    className="documents-filter"
                    value={fileType}
                    onChange={(event) => setFileType(event.target.value)}
                >
                    <option value="">All file types</option>
                    {fileTypes.map((type) => (
                        <option key={type} value={type}>
                            {type}
                        </option>
                    ))}
                </select>
                <select
                    className="documents-filter"
                    value={category}
                    onChange={(event) => setCategory(event.target.value)}
                >
                    <option value="">All categories</option>
                    {categories.map((value) => (
                        <option key={value} value={value}>
                            {value}
                        </option>
                    ))}
                </select>
                <button type="button" className="memory-button" onClick={() => void refresh()}>
                    Refresh
                </button>
                <button
                    type="button"
                    className="memory-button memory-button--danger"
                    onClick={() => void onDeleteAll()}
                    disabled={documents.length === 0}
                >
                    Delete All
                </button>
            </section>

            {error ? (
                <p className="error-banner" role="alert">
                    <span className="error-icon" aria-hidden="true">!</span>
                    {error}
                </p>
            ) : null}

            <div className="documents-content">
                <section className="documents-list-card">
                    {isLoading ? <p className="memory-status">Loading documents...</p> : null}
                    {!isLoading && filtered.length === 0 ? (
                        <p className="memory-status">No documents available for the selected filters.</p>
                    ) : null}

                    {filtered.length > 0 ? (
                        <table className="documents-table">
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Type</th>
                                    <th>Parser</th>
                                    <th>Category</th>
                                    <th>Size</th>
                                    <th>Pages</th>
                                    <th>Tables</th>
                                    <th>Images</th>
                                    <th>Chunks</th>
                                    <th>Processing</th>
                                    <th>Status</th>
                                    <th>Embedding</th>
                                    <th>Index</th>
                                    <th>Updated</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filtered.map((document) => (
                                    <tr key={document.id}>
                                        <td>{getIconForType(document.file_type)} {document.name}</td>
                                        <td>{document.file_type}</td>
                                        <td>{String(document.metadata.parser ?? "-")}</td>
                                        <td>{String(document.metadata.category ?? "-")}</td>
                                        <td>{formatBytes(document.size_bytes)}</td>
                                        <td>{getNumberMeta(document.metadata, "pages") || "-"}</td>
                                        <td>{getNumberMeta(document.metadata, "tables") || "-"}</td>
                                        <td>{getNumberMeta(document.metadata, "images") || "-"}</td>
                                        <td>{document.chunk_count}</td>
                                        <td>
                                            {(() => {
                                                const ms = getNumberMeta(document.metadata, "processing_time_ms");
                                                return ms > 0 ? `${(ms / 1000).toFixed(2)}s` : "-";
                                            })()}
                                        </td>
                                        <td>{String(document.metadata.processing_status ?? "-")}</td>
                                        <td>{document.embedding_status}</td>
                                        <td>{document.index_status}</td>
                                        <td>{formatTimestamp(document.updated_at)}</td>
                                        <td>
                                            <div className="memory-row-actions">
                                                <button
                                                    type="button"
                                                    className="memory-row-action"
                                                    onClick={() => void selectDocument(document)}
                                                >
                                                    View
                                                </button>
                                                <button
                                                    type="button"
                                                    className="memory-row-action memory-row-action--danger"
                                                    onClick={() => void onDelete(document)}
                                                >
                                                    Delete
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    ) : null}
                </section>

                <aside className="documents-viewer-card">
                    {selectedDocument ? (
                        <>
                            <header className="memory-drawer-header">
                                <h2>{selectedDocument.name}</h2>
                                <button
                                    type="button"
                                    className="memory-row-action"
                                    onClick={() => void selectDocument(null)}
                                >
                                    Close
                                </button>
                            </header>
                            <dl className="memory-detail-list">
                                <dt>Document Id</dt>
                                <dd>{selectedDocument.id}</dd>
                                <dt>Original Filename</dt>
                                <dd>{selectedDocument.original_filename}</dd>
                                <dt>Stored Path</dt>
                                <dd>{selectedDocument.stored_path}</dd>
                                <dt>Metadata</dt>
                                <dd>
                                    <pre>{JSON.stringify(selectedDocument.metadata, null, 2)}</pre>
                                </dd>
                            </dl>
                            <h3 className="documents-subtitle">Chunks ({selectedChunks.length})</h3>
                            <div className="documents-chunk-list">
                                {selectedChunks.map((chunk) => (
                                    <article key={chunk.chunk_id} className="documents-chunk-card">
                                        <p className="documents-chunk-meta">
                                            chunk={chunk.chunk_id} section={String(chunk.metadata.section ?? "-")}
                                        </p>
                                        <p>{chunk.text}</p>
                                    </article>
                                ))}
                            </div>
                        </>
                    ) : (
                        <p className="memory-status">Select a document to view metadata and chunks.</p>
                    )}
                </aside>
            </div>
        </div>
    );
};
