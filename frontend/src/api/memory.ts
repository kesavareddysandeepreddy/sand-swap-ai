import { loadAuthSession } from "../state/authStorage";
import type {
    MemoryListResponse,
    MemoryRecord,
    MemoryUpdateRequest,
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

export interface ListMemoriesParams {
    page?: number;
    pageSize?: number;
    search?: string;
    category?: string;
    minImportance?: number;
}

const buildQuery = (params: ListMemoriesParams): string => {
    const query = new URLSearchParams();
    if (params.page) {
        query.set("page", String(params.page));
    }
    if (params.pageSize) {
        query.set("page_size", String(params.pageSize));
    }
    if (params.search) {
        query.set("search", params.search);
    }
    if (params.category) {
        query.set("category", params.category);
    }
    if (typeof params.minImportance === "number") {
        query.set("min_importance", String(params.minImportance));
    }
    const encoded = query.toString();
    return encoded ? `?${encoded}` : "";
};

export const memoryApi = {
    list: (params: ListMemoriesParams = {}) =>
        request<MemoryListResponse>(`/memory${buildQuery(params)}`, {
            method: "GET",
        }),

    getById: (id: string) =>
        request<MemoryRecord>(`/memory/${id}`, {
            method: "GET",
        }),

    update: (id: string, payload: MemoryUpdateRequest) =>
        request<MemoryRecord>(`/memory/${id}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        }),

    deleteOne: (id: string) =>
        request<void>(`/memory/${id}`, {
            method: "DELETE",
        }),

    deleteAll: () =>
        request<{ deleted: number }>("/memory", {
            method: "DELETE",
        }),
};
