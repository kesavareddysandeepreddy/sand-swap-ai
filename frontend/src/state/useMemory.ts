import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError } from "../api/client";
import { memoryApi } from "../api/memory";
import type { MemoryRecord, MemoryUpdateRequest } from "../types/api";

interface Filters {
    search: string;
    category: string;
    minImportance: number;
}

const DEFAULT_PAGE_SIZE = 25;

export const useMemory = () => {
    const [records, setRecords] = useState<MemoryRecord[]>([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
    const [filters, setFilters] = useState<Filters>({
        search: "",
        category: "",
        minImportance: 0,
    });
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const refresh = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const response = await memoryApi.list({
                page,
                pageSize,
                search: filters.search || undefined,
                category: filters.category || undefined,
                minImportance: filters.minImportance,
            });
            setRecords(response.items);
            setTotal(response.total);
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Failed to load memories.");
        } finally {
            setIsLoading(false);
        }
    }, [filters.category, filters.minImportance, filters.search, page, pageSize]);

    useEffect(() => {
        void refresh();
    }, [refresh]);

    const update = useCallback(
        async (id: string, payload: MemoryUpdateRequest) => {
            setError(null);
            try {
                const updated = await memoryApi.update(id, payload);
                setRecords((previous) =>
                    previous.map((record) => (record.id === id ? updated : record))
                );
            } catch (err) {
                setError(err instanceof ApiError ? err.message : "Failed to update memory.");
                throw err;
            }
        },
        []
    );

    const deleteOne = useCallback(async (id: string) => {
        setError(null);
        try {
            await memoryApi.deleteOne(id);
            setRecords((previous) => previous.filter((record) => record.id !== id));
            setTotal((previous) => Math.max(0, previous - 1));
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Failed to delete memory.");
            throw err;
        }
    }, []);

    const deleteAll = useCallback(async () => {
        setError(null);
        try {
            await memoryApi.deleteAll();
            setRecords([]);
            setTotal(0);
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Failed to delete memories.");
            throw err;
        }
    }, []);

    const categories = useMemo(
        () => Array.from(new Set(records.map((record) => record.category))).sort(),
        [records]
    );

    return {
        records,
        total,
        page,
        pageSize,
        setPage,
        setPageSize,
        filters,
        setFilters,
        categories,
        isLoading,
        error,
        refresh,
        update,
        deleteOne,
        deleteAll,
    };
};
