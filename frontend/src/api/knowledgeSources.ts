import { loadAuthSession } from "../state/authStorage";
import type {
    ConnectorDiscoveryResponse,
    ConnectorOperationResponse,
    CreateKnowledgeSourceRequest,
    DeleteKnowledgeSourceResponse,
    KnowledgeSourceRecord,
    KnowledgeSourcesHealthResponse,
} from "../types/api";
import { ApiError } from "./client";

const WORKSPACE_STORAGE_KEY = "sand-swap-active-workspace-v1";
const PROJECT_STORAGE_KEY = "sand-swap-active-project-v1";

const loadWorkspaceId = (): string | null => {
    const value = window.localStorage.getItem(WORKSPACE_STORAGE_KEY);
    if (!value) {
        return null;
    }
    const normalized = value.trim();
    return normalized || null;
};

const loadProjectId = (): string | null => {
    const value = window.localStorage.getItem(PROJECT_STORAGE_KEY);
    if (!value) {
        return null;
    }
    const normalized = value.trim();
    return normalized || null;
};

const getBaseUrl = (): string => {
    const raw = (import.meta.env.VITE_API_BASE_URL ?? "").trim().replace(/\/$/, "");
    if (!raw) {
        throw new ApiError("VITE_API_BASE_URL is not configured.", 0);
    }
    const isAbsolute = /^https?:\/\//i.test(raw);
    const isRelative = raw.startsWith("/");

    if (!isAbsolute && !isRelative) {
        throw new ApiError(
            "VITE_API_BASE_URL must be an absolute URL or '/api'.",
            0,
        );
    }
    return raw;
};

const request = async <T>(path: string, init: RequestInit): Promise<T> => {
    const endpoint = `${getBaseUrl()}${path}`;
    let response: Response;
    const headers = new Headers(init.headers);
    const session = loadAuthSession();
    if (session?.accessToken) {
        headers.set("Authorization", `Bearer ${session.accessToken}`);
    }
    const workspaceId = loadWorkspaceId();
    if (workspaceId) {
        headers.set("X-Workspace-Id", workspaceId);
    }
    const projectId = loadProjectId();
    if (projectId) {
        headers.set("X-Project-Id", projectId);
    }
    const requestInit: RequestInit = {
        ...init,
        headers,
    };

    try {
        response = await fetch(endpoint, requestInit);
    } catch {
        throw new ApiError("Unable to connect to the SandSwap API.", 0);
    }

    if (!response.ok) {
        let message = `Request failed (${response.status})`;
        try {
            const payload = (await response.json()) as { detail?: string };
            if (payload.detail) {
                message = payload.detail;
            }
        } catch {
            message = response.statusText || message;
        }
        throw new ApiError(message, response.status);
    }

    if (response.status === 204) {
        return undefined as T;
    }

    return (await response.json()) as T;
};

export const knowledgeSourcesApi = {
    list: (projectId: string) =>
        request<KnowledgeSourceRecord[]>(
            `/api/knowledge-sources?project_id=${encodeURIComponent(projectId)}`,
            {
                method: "GET",
            }
        ),

    create: (payload: CreateKnowledgeSourceRequest) =>
        request<KnowledgeSourceRecord>("/api/knowledge-sources", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        }),

    remove: (id: string) =>
        request<DeleteKnowledgeSourceResponse>(`/api/knowledge-sources/${id}`, {
            method: "DELETE",
        }),

    enable: (id: string) =>
        request<KnowledgeSourceRecord>(`/api/knowledge-sources/${id}/enable`, {
            method: "PUT",
        }),

    disable: (id: string) =>
        request<KnowledgeSourceRecord>(`/api/knowledge-sources/${id}/disable`, {
            method: "PUT",
        }),

    health: () =>
        request<KnowledgeSourcesHealthResponse>("/api/knowledge-sources/health", {
            method: "GET",
        }),

    connectConnector: (
        sourceId: string,
        payload: { connection_config: Record<string, unknown>; metadata?: Record<string, unknown> }
    ) =>
        request<ConnectorOperationResponse>(
            `/api/knowledge-sources/${sourceId}/connector/connect`,
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            }
        ),

    discoverConnector: (sourceId: string) =>
        request<ConnectorDiscoveryResponse>(
            `/api/knowledge-sources/${sourceId}/connector/discover`,
            {
                method: "GET",
            }
        ),

    syncConnector: (sourceId: string, incremental = false) =>
        request<KnowledgeSourceRecord>(
            `/api/knowledge-sources/${sourceId}/connector/sync?incremental=${String(incremental)}`,
            {
                method: "POST",
            }
        ),

    connectorHealth: (sourceId: string) =>
        request<ConnectorOperationResponse>(
            `/api/knowledge-sources/${sourceId}/connector/health`,
            {
                method: "GET",
            }
        ),
};
