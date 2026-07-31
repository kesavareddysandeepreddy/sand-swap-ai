import { useCallback, useEffect, useMemo, useState } from "react";

import { agentsApi } from "../api/agents";
import { ApiError } from "../api/client";
import type { AgentCreateRequest, AgentRecord, AgentUpdateRequest } from "../types/api";

export const useAgents = (scopeKey: string) => {
    const [agents, setAgents] = useState<AgentRecord[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [isMutating, setIsMutating] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    const refresh = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const items = await agentsApi.list();
            setAgents(items);
            return items;
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Failed to load agents.");
            return [];
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        setAgents([]);
        setError(null);
        void refresh();
    }, [refresh, scopeKey]);

    const mutate = useCallback(async <T,>(operation: () => Promise<T>): Promise<T> => {
        setIsMutating(true);
        setError(null);
        try {
            const result = await operation();
            await refresh();
            return result;
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Agent operation failed.");
            throw err;
        } finally {
            setIsMutating(false);
        }
    }, [refresh]);

    const createAgent = useCallback((payload: AgentCreateRequest) => mutate(() => agentsApi.create(payload)), [mutate]);
    const updateAgent = useCallback((id: string, payload: AgentUpdateRequest) => mutate(() => agentsApi.update(id, payload)), [mutate]);
    const deleteAgent = useCallback((id: string) => mutate(() => agentsApi.deleteOne(id)), [mutate]);
    const enableAgent = useCallback((id: string) => mutate(() => agentsApi.enable(id)), [mutate]);
    const disableAgent = useCallback((id: string) => mutate(() => agentsApi.disable(id)), [mutate]);

    const enabledCount = useMemo(
        () => agents.filter((agent) => agent.enabled).length,
        [agents]
    );

    return {
        agents,
        enabledCount,
        isLoading,
        isMutating,
        error,
        refresh,
        createAgent,
        updateAgent,
        deleteAgent,
        enableAgent,
        disableAgent,
    };
};
