import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../api/client";
import { knowledgeSourcesApi } from "../api/knowledgeSources";
import type {
    ConnectorOperationResponse,
    CreateKnowledgeSourceRequest,
    KnowledgeSourceRecord,
    KnowledgeSourcesHealthResponse,
} from "../types/api";

export const useKnowledgeSources = (projectId: string) => {
    const [sources, setSources] = useState<KnowledgeSourceRecord[]>([]);
    const [health, setHealth] = useState<KnowledgeSourcesHealthResponse | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isMutating, setIsMutating] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [connectorDetails, setConnectorDetails] = useState<
        Record<string, { status: string; detail: string; metadata: Record<string, unknown> }>
    >({});

    const refresh = useCallback(async () => {
        if (!projectId) {
            setSources([]);
            setHealth(null);
            return;
        }
        setIsLoading(true);
        setError(null);
        try {
            const [items, healthPayload] = await Promise.all([
                knowledgeSourcesApi.list(projectId),
                knowledgeSourcesApi.health(),
            ]);
            setSources(items);
            setHealth(healthPayload);
        } catch (err) {
            setError(
                err instanceof ApiError ? err.message : "Failed to load knowledge sources."
            );
        } finally {
            setIsLoading(false);
        }
    }, [projectId]);

    useEffect(() => {
        void refresh();
    }, [refresh]);

    const createSource = useCallback(
        async (payload: Omit<CreateKnowledgeSourceRequest, "project_id">) => {
            setIsMutating(true);
            setError(null);
            try {
                const created = await knowledgeSourcesApi.create({
                    ...payload,
                    project_id: projectId,
                });
                setSources((previous) => [created, ...previous]);
                return created;
            } catch (err) {
                setError(
                    err instanceof ApiError
                        ? err.message
                        : "Failed to create knowledge source."
                );
                throw err;
            } finally {
                setIsMutating(false);
            }
        },
        [projectId]
    );

    const enableSource = useCallback(async (id: string) => {
        setIsMutating(true);
        setError(null);
        try {
            const updated = await knowledgeSourcesApi.enable(id);
            setSources((previous) =>
                previous.map((source) => (source.id === id ? updated : source))
            );
            return updated;
        } catch (err) {
            setError(
                err instanceof ApiError ? err.message : "Failed to enable knowledge source."
            );
            throw err;
        } finally {
            setIsMutating(false);
        }
    }, []);

    const disableSource = useCallback(async (id: string) => {
        setIsMutating(true);
        setError(null);
        try {
            const updated = await knowledgeSourcesApi.disable(id);
            setSources((previous) =>
                previous.map((source) => (source.id === id ? updated : source))
            );
            return updated;
        } catch (err) {
            setError(
                err instanceof ApiError
                    ? err.message
                    : "Failed to disable knowledge source."
            );
            throw err;
        } finally {
            setIsMutating(false);
        }
    }, []);

    const removeSource = useCallback(async (id: string) => {
        setIsMutating(true);
        setError(null);
        try {
            await knowledgeSourcesApi.remove(id);
            setSources((previous) => previous.filter((source) => source.id !== id));
        } catch (err) {
            setError(
                err instanceof ApiError ? err.message : "Failed to remove knowledge source."
            );
            throw err;
        } finally {
            setIsMutating(false);
        }
    }, []);

    const connectConnector = useCallback(
        async (
            sourceId: string,
            payload: { connection_config: Record<string, unknown>; metadata?: Record<string, unknown> }
        ) => {
            setIsMutating(true);
            setError(null);
            try {
                const response = await knowledgeSourcesApi.connectConnector(sourceId, payload);
                setConnectorDetails((previous) => ({
                    ...previous,
                    [sourceId]: {
                        status: response.status,
                        detail: response.detail,
                        metadata: response.metadata,
                    },
                }));
                const refreshed = await knowledgeSourcesApi.list(projectId);
                setSources(refreshed);
                return response;
            } catch (err) {
                setError(
                    err instanceof ApiError ? err.message : "Failed to connect connector."
                );
                throw err;
            } finally {
                setIsMutating(false);
            }
        },
        [projectId]
    );

    const discoverConnector = useCallback(async (sourceId: string) => {
        setIsMutating(true);
        setError(null);
        try {
            return await knowledgeSourcesApi.discoverConnector(sourceId);
        } catch (err) {
            setError(
                err instanceof ApiError ? err.message : "Failed to discover connector resources."
            );
            throw err;
        } finally {
            setIsMutating(false);
        }
    }, []);

    const syncConnector = useCallback(async (sourceId: string, incremental = false) => {
        setIsMutating(true);
        setError(null);
        try {
            const updated = await knowledgeSourcesApi.syncConnector(sourceId, incremental);
            setSources((previous) =>
                previous.map((source) => (source.id === sourceId ? updated : source))
            );
            return updated;
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Failed to sync connector.");
            throw err;
        } finally {
            setIsMutating(false);
        }
    }, []);

    const connectorHealth = useCallback(async (sourceId: string) => {
        setIsMutating(true);
        setError(null);
        try {
            const response: ConnectorOperationResponse =
                await knowledgeSourcesApi.connectorHealth(sourceId);
            setConnectorDetails((previous) => ({
                ...previous,
                [sourceId]: {
                    status: response.status,
                    detail: response.detail,
                    metadata: response.metadata,
                },
            }));
            return response;
        } catch (err) {
            setError(
                err instanceof ApiError ? err.message : "Failed to load connector health."
            );
            throw err;
        } finally {
            setIsMutating(false);
        }
    }, []);

    return {
        sources,
        health,
        isLoading,
        isMutating,
        error,
        refresh,
        createSource,
        enableSource,
        disableSource,
        removeSource,
        connectConnector,
        discoverConnector,
        syncConnector,
        connectorHealth,
        connectorDetails,
    };
};
