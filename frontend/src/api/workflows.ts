import { loadAuthSession } from "../state/authStorage";
import type {
    WorkflowCreateRequest,
    WorkflowDashboardResponse,
    WorkflowExecutionRequest,
    WorkflowExecutionResponse,
    WorkflowRecord,
    WorkflowRunActionRequest,
    WorkflowRunRecord,
    WorkflowUpdateRequest,
    WorkflowValidationResponse,
    WorkflowVersionResponse,
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

    return (await response.json()) as T;
};

export const workflowsApi = {
    list: () =>
        request<WorkflowRecord[]>("/api/workflows", {
            method: "GET",
        }),

    getById: (workflowId: string) =>
        request<WorkflowRecord>(`/api/workflows/${workflowId}`, {
            method: "GET",
        }),

    create: (payload: WorkflowCreateRequest) =>
        request<WorkflowRecord>("/api/workflows", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        }),

    update: (workflowId: string, payload: WorkflowUpdateRequest) =>
        request<WorkflowRecord>(`/api/workflows/${workflowId}`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        }),

    deleteOne: (workflowId: string) =>
        request<{ deleted: boolean }>(`/api/workflows/${workflowId}`, {
            method: "DELETE",
        }),

    validate: (workflowId: string) =>
        request<WorkflowValidationResponse>(`/api/workflows/${workflowId}/validate`, {
            method: "POST",
        }),

    listVersions: (workflowId: string) =>
        request<WorkflowVersionResponse[]>(`/api/workflows/${workflowId}/versions`, {
            method: "GET",
        }),

    execute: (workflowId: string, payload: WorkflowExecutionRequest) =>
        request<WorkflowExecutionResponse>(`/api/workflows/${workflowId}/execute`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        }),

    listRuns: (workflowId: string) =>
        request<WorkflowRunRecord[]>(`/api/workflows/${workflowId}/runs`, {
            method: "GET",
        }),

    listRecentRuns: (limit = 20) =>
        request<WorkflowRunRecord[]>(`/api/workflows/runs?limit=${limit}`, {
            method: "GET",
        }),

    getRun: (runId: string) =>
        request<WorkflowRunRecord>(`/api/workflows/runs/${runId}`, {
            method: "GET",
        }),

    cancelRun: (runId: string) =>
        request<WorkflowRunRecord>(`/api/workflows/runs/${runId}/cancel`, {
            method: "POST",
        }),

    applyRunAction: (runId: string, payload: WorkflowRunActionRequest) =>
        request<WorkflowRunRecord>(`/api/workflows/runs/${runId}/actions`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        }),

    getDashboard: () =>
        request<WorkflowDashboardResponse>("/api/workflows/dashboard", {
            method: "GET",
        }),
};
