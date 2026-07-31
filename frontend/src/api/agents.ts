import { loadAuthSession } from "../state/authStorage";
import type {
    AgentCreateRequest,
    AgentRecord,
    AgentUpdateRequest,
} from "../types/api";
import { ApiError } from "./client";

const WORKSPACE_STORAGE_KEY = "sand-swap-active-workspace-v1";
const PROJECT_STORAGE_KEY = "sand-swap-active-project-v1";

const loadWorkspaceId = (): string | null => {
    const value = window.localStorage.getItem(WORKSPACE_STORAGE_KEY);
    return value?.trim() || null;
};

const loadProjectId = (): string | null => {
    const value = window.localStorage.getItem(PROJECT_STORAGE_KEY);
    return value?.trim() || null;
};

const getBaseUrl = (): string => {
    const raw = (import.meta.env.VITE_API_BASE_URL ?? "").trim().replace(/\/$/, "");
    if (!raw) {
        throw new ApiError("VITE_API_BASE_URL is not configured.", 0);
    }
    return raw;
};

const request = async <T>(path: string, init: RequestInit): Promise<T> => {
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

    let response: Response;
    try {
        response = await fetch(`${getBaseUrl()}${path}`, {
            ...init,
            headers,
        });
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

export const agentsApi = {
    list: () =>
        request<AgentRecord[]>("/api/agents", {
            method: "GET",
        }),

    getById: (id: string) =>
        request<AgentRecord>(`/api/agents/${id}`, {
            method: "GET",
        }),

    create: (payload: AgentCreateRequest) =>
        request<AgentRecord>("/api/agents", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        }),

    update: (id: string, payload: AgentUpdateRequest) =>
        request<AgentRecord>(`/api/agents/${id}`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        }),

    deleteOne: (id: string) =>
        request<{ deleted: boolean }>(`/api/agents/${id}`, {
            method: "DELETE",
        }),

    enable: (id: string) =>
        request<AgentRecord>(`/api/agents/${id}/enable`, {
            method: "POST",
        }),

    disable: (id: string) =>
        request<AgentRecord>(`/api/agents/${id}/disable`, {
            method: "POST",
        }),
};
