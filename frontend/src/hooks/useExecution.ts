import { useCallback, useRef, useState } from "react";

import { apiClient, ApiError } from "../api/client";
import type { ExecutionTraceDetail, ExecutionTraceSummary } from "../types/api";

export const useExecution = () => {
    const [recent, setRecent] = useState<ExecutionTraceSummary[]>([]);
    const [isLoadingRecent, setIsLoadingRecent] = useState(false);
    const [recentError, setRecentError] = useState<string | null>(null);

    const [selectedTrace, setSelectedTrace] = useState<ExecutionTraceDetail | null>(null);
    const [isLoadingTrace, setIsLoadingTrace] = useState(false);
    const [traceError, setTraceError] = useState<string | null>(null);
    const [hasLoadedRecent, setHasLoadedRecent] = useState(false);

    const traceCacheRef = useRef<Record<string, ExecutionTraceDetail>>({});
    const traceRequestRef = useRef<Record<string, Promise<ExecutionTraceDetail>>>({});

    const loadRecent = useCallback(async (force = false) => {
        if (hasLoadedRecent && !force) {
            return recent;
        }

        setIsLoadingRecent(true);
        setRecentError(null);
        try {
            const traces = await apiClient.listRecentExecutionTraces();
            setRecent(traces);
            setHasLoadedRecent(true);
            if (traces.length === 0) {
                setSelectedTrace(null);
            }
            return traces;
        } catch (error) {
            setRecent([]);
            setSelectedTrace(null);
            setRecentError(
                error instanceof ApiError
                    ? error.message
                    : "Failed to load execution traces."
            );
            return [];
        } finally {
            setIsLoadingRecent(false);
        }
    }, [hasLoadedRecent, recent]);

    const loadTrace = useCallback(async (traceId: string) => {
        if (selectedTrace?.trace_id === traceId) {
            return selectedTrace;
        }

        const cached = traceCacheRef.current[traceId];
        if (cached) {
            setSelectedTrace(cached);
            return cached;
        }

        if (traceRequestRef.current[traceId]) {
            return traceRequestRef.current[traceId];
        }

        setIsLoadingTrace(true);
        setTraceError(null);

        const request = apiClient
            .getExecutionTrace(traceId)
            .then((detail) => {
                traceCacheRef.current[traceId] = detail;
                setSelectedTrace(detail);
                return detail;
            })
            .catch((error: unknown) => {
                setTraceError(
                    error instanceof ApiError
                        ? error.message
                        : "Failed to load trace detail."
                );
                throw error;
            })
            .finally(() => {
                delete traceRequestRef.current[traceId];
                setIsLoadingTrace(false);
            });

        traceRequestRef.current[traceId] = request;
        return request;
    }, [selectedTrace]);

    const selectTrace = useCallback(async (traceId: string) => {
        try {
            await loadTrace(traceId);
        } catch {
            // Error state handled in loadTrace.
        }
    }, [loadTrace]);

    const ensureFirstTraceLoaded = useCallback(async () => {
        try {
            if (selectedTrace) {
                return;
            }
            const traces = await loadRecent(false);
            if (traces.length === 0) {
                return;
            }
            await loadTrace(traces[0].trace_id);
        } catch {
            // Error state handled by loadRecent/loadTrace.
        }
    }, [selectedTrace, loadRecent, loadTrace]);

    const refreshAfterChatCompletion = useCallback(async () => {
        const traces = await loadRecent(true);
        if (traces.length === 0) {
            return;
        }
        await loadTrace(traces[0].trace_id);
    }, [loadRecent, loadTrace]);

    return {
        recent,
        selectedTrace,
        isLoadingRecent,
        isLoadingTrace,
        recentError,
        traceError,
        hasLoadedRecent,
        selectTrace,
        ensureFirstTraceLoaded,
        refreshAfterChatCompletion,
    };
};
