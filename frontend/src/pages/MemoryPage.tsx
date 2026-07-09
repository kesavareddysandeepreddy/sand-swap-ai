import { useMemo, useState } from "react";

import { useMemory } from "../state/useMemory";
import type { MemoryRecord } from "../types/api";
import { formatTimestamp } from "../utils/date";

interface EditableValues {
    category: string;
    key: string;
    value: string;
    importance: number;
}

const toEditable = (record: MemoryRecord): EditableValues => ({
    category: record.category,
    key: record.key,
    value: record.value,
    importance: record.importance,
});

export const MemoryPage = () => {
    const {
        records,
        total,
        page,
        pageSize,
        setPage,
        filters,
        setFilters,
        categories,
        isLoading,
        error,
        refresh,
        update,
        deleteOne,
        deleteAll,
    } = useMemory();

    const [selected, setSelected] = useState<MemoryRecord | null>(null);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editingValues, setEditingValues] = useState<EditableValues | null>(null);
    const [isMutating, setIsMutating] = useState(false);

    const totalPages = Math.max(1, Math.ceil(total / pageSize));

    const selectedRecord = useMemo(
        () => records.find((record) => record.id === selected?.id) ?? selected,
        [records, selected]
    );

    const beginEdit = (record: MemoryRecord) => {
        setEditingId(record.id);
        setEditingValues(toEditable(record));
    };

    const cancelEdit = () => {
        setEditingId(null);
        setEditingValues(null);
    };

    const commitEdit = async (record: MemoryRecord) => {
        if (!editingValues) {
            return;
        }

        setIsMutating(true);
        try {
            await update(record.id, {
                category: editingValues.category,
                key: editingValues.key,
                value: editingValues.value,
                importance: editingValues.importance,
            });
            setEditingId(null);
            setEditingValues(null);
            await refresh();
        } finally {
            setIsMutating(false);
        }
    };

    const handleDelete = async (record: MemoryRecord) => {
        const confirmed = window.confirm(`Delete memory "${record.key}"?`);
        if (!confirmed) {
            return;
        }

        setIsMutating(true);
        try {
            await deleteOne(record.id);
            if (selected?.id === record.id) {
                setSelected(null);
            }
            await refresh();
        } finally {
            setIsMutating(false);
        }
    };

    const handleDeleteAll = async () => {
        const confirmed = window.confirm("Delete all memories? This cannot be undone.");
        if (!confirmed) {
            return;
        }

        setIsMutating(true);
        try {
            await deleteAll();
            setSelected(null);
            await refresh();
        } finally {
            setIsMutating(false);
        }
    };

    return (
        <div className="memory-page">
            <section className="memory-toolbar">
                <div className="memory-controls">
                    <input
                        className="memory-search"
                        type="search"
                        placeholder="Search memory key/value"
                        value={filters.search}
                        onChange={(event) =>
                            setFilters((previous) => ({
                                ...previous,
                                search: event.target.value,
                            }))
                        }
                    />
                    <select
                        className="memory-category"
                        value={filters.category}
                        onChange={(event) =>
                            setFilters((previous) => ({
                                ...previous,
                                category: event.target.value,
                            }))
                        }
                    >
                        <option value="">All categories</option>
                        {categories.map((category) => (
                            <option key={category} value={category}>
                                {category}
                            </option>
                        ))}
                    </select>
                    <label className="memory-importance-filter">
                        <span>Min Importance: {filters.minImportance.toFixed(2)}</span>
                        <input
                            type="range"
                            min={0}
                            max={1}
                            step={0.05}
                            value={filters.minImportance}
                            onChange={(event) =>
                                setFilters((previous) => ({
                                    ...previous,
                                    minImportance: Number(event.target.value),
                                }))
                            }
                        />
                    </label>
                </div>
                <div className="memory-actions">
                    <button
                        type="button"
                        className="memory-button"
                        onClick={() => void refresh()}
                        disabled={isLoading || isMutating}
                    >
                        Refresh
                    </button>
                    <button
                        type="button"
                        className="memory-button memory-button--danger"
                        onClick={() => void handleDeleteAll()}
                        disabled={isLoading || isMutating || total === 0}
                    >
                        Delete All
                    </button>
                </div>
            </section>

            {error ? (
                <p className="error-banner" role="alert">
                    <span className="error-icon" aria-hidden="true">!</span>
                    {error}
                </p>
            ) : null}

            <div className="memory-content">
                <section className="memory-table-card">
                    {isLoading ? <p className="memory-status">Loading memories...</p> : null}
                    {!isLoading && records.length === 0 ? (
                        <p className="memory-status">No memories found for the selected filters.</p>
                    ) : null}

                    {records.length > 0 ? (
                        <table className="memory-table">
                            <thead>
                                <tr>
                                    <th>Category</th>
                                    <th>Key</th>
                                    <th>Value</th>
                                    <th>Importance</th>
                                    <th>Confidence</th>
                                    <th>Created</th>
                                    <th>Updated</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {records.map((record) => {
                                    const rowEditingValues =
                                        editingId === record.id ? editingValues : null;
                                    return (
                                        <tr key={record.id}>
                                            <td>
                                                {rowEditingValues ? (
                                                    <input
                                                        value={rowEditingValues.category}
                                                        onChange={(event) =>
                                                            setEditingValues((previous) =>
                                                                previous
                                                                    ? {
                                                                        ...previous,
                                                                        category: event.target.value,
                                                                    }
                                                                    : previous
                                                            )
                                                        }
                                                    />
                                                ) : (
                                                    record.category
                                                )}
                                            </td>
                                            <td>
                                                {rowEditingValues ? (
                                                    <input
                                                        value={rowEditingValues.key}
                                                        onChange={(event) =>
                                                            setEditingValues((previous) =>
                                                                previous
                                                                    ? {
                                                                        ...previous,
                                                                        key: event.target.value,
                                                                    }
                                                                    : previous
                                                            )
                                                        }
                                                    />
                                                ) : (
                                                    record.key
                                                )}
                                            </td>
                                            <td>
                                                {rowEditingValues ? (
                                                    <input
                                                        value={rowEditingValues.value}
                                                        onChange={(event) =>
                                                            setEditingValues((previous) =>
                                                                previous
                                                                    ? {
                                                                        ...previous,
                                                                        value: event.target.value,
                                                                    }
                                                                    : previous
                                                            )
                                                        }
                                                    />
                                                ) : (
                                                    record.value
                                                )}
                                            </td>
                                            <td>
                                                {rowEditingValues ? (
                                                    <input
                                                        type="number"
                                                        min={0}
                                                        max={1}
                                                        step={0.01}
                                                        value={rowEditingValues.importance}
                                                        onChange={(event) =>
                                                            setEditingValues((previous) =>
                                                                previous
                                                                    ? {
                                                                        ...previous,
                                                                        importance: Number(event.target.value),
                                                                    }
                                                                    : previous
                                                            )
                                                        }
                                                    />
                                                ) : (
                                                    record.importance.toFixed(2)
                                                )}
                                            </td>
                                            <td>{record.confidence.toFixed(2)}</td>
                                            <td>{formatTimestamp(record.created_at)}</td>
                                            <td>{formatTimestamp(record.updated_at)}</td>
                                            <td>
                                                <div className="memory-row-actions">
                                                    <button
                                                        type="button"
                                                        className="memory-row-action"
                                                        onClick={() => setSelected(record)}
                                                    >
                                                        View
                                                    </button>
                                                    {rowEditingValues ? (
                                                        <>
                                                            <button
                                                                type="button"
                                                                className="memory-row-action"
                                                                onClick={() => void commitEdit(record)}
                                                                disabled={isMutating}
                                                            >
                                                                Save
                                                            </button>
                                                            <button
                                                                type="button"
                                                                className="memory-row-action"
                                                                onClick={cancelEdit}
                                                                disabled={isMutating}
                                                            >
                                                                Cancel
                                                            </button>
                                                        </>
                                                    ) : (
                                                        <button
                                                            type="button"
                                                            className="memory-row-action"
                                                            onClick={() => beginEdit(record)}
                                                        >
                                                            Edit
                                                        </button>
                                                    )}
                                                    <button
                                                        type="button"
                                                        className="memory-row-action memory-row-action--danger"
                                                        onClick={() => void handleDelete(record)}
                                                        disabled={isMutating}
                                                    >
                                                        Delete
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    ) : null}

                    <footer className="memory-pagination">
                        <span>
                            Page {page} of {totalPages}
                        </span>
                        <div>
                            <button
                                type="button"
                                className="memory-button"
                                onClick={() => setPage(Math.max(1, page - 1))}
                                disabled={page <= 1}
                            >
                                Previous
                            </button>
                            <button
                                type="button"
                                className="memory-button"
                                onClick={() => setPage(Math.min(totalPages, page + 1))}
                                disabled={page >= totalPages}
                            >
                                Next
                            </button>
                        </div>
                    </footer>
                </section>

                <aside className={`memory-drawer ${selectedRecord ? "memory-drawer--open" : ""}`}>
                    {selectedRecord ? (
                        <>
                            <header className="memory-drawer-header">
                                <h2>Memory Detail</h2>
                                <button
                                    type="button"
                                    className="memory-row-action"
                                    onClick={() => setSelected(null)}
                                >
                                    Close
                                </button>
                            </header>
                            <dl className="memory-detail-list">
                                <dt>Category</dt>
                                <dd>{selectedRecord.category}</dd>
                                <dt>Key</dt>
                                <dd>{selectedRecord.key}</dd>
                                <dt>Value</dt>
                                <dd>{selectedRecord.value}</dd>
                                <dt>Importance</dt>
                                <dd>{selectedRecord.importance.toFixed(2)}</dd>
                                <dt>Confidence</dt>
                                <dd>{selectedRecord.confidence.toFixed(2)}</dd>
                                <dt>Created</dt>
                                <dd>{formatTimestamp(selectedRecord.created_at)}</dd>
                                <dt>Updated</dt>
                                <dd>{formatTimestamp(selectedRecord.updated_at)}</dd>
                                <dt>Metadata</dt>
                                <dd>
                                    <pre>{JSON.stringify(selectedRecord.metadata, null, 2)}</pre>
                                </dd>
                                <dt>Tags</dt>
                                <dd>{selectedRecord.tags.join(", ") || "None"}</dd>
                            </dl>
                        </>
                    ) : (
                        <p className="memory-status">Select a memory to view details.</p>
                    )}
                </aside>
            </div>
        </div>
    );
};
