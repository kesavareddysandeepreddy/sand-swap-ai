import { loadAuthSession } from "../state/authStorage";
import type {
    AgentCreateRequest,
    AgentDashboardResponse,
    AgentExecutionStepResponse,
    AgentRecord,
    AgentTestRequest,
    AgentTestRunResponse,
    AgentUpdateRequest,
    AgentVersionCompareResponse,
    AgentVersionResponse,
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

const normalizeAgent = (agent: AgentRecord): AgentRecord => ({
    ...agent,
    objective: agent.objective ?? agent.goal,
    short_term_enabled: agent.short_term_enabled ?? agent.conversation_memory_enabled,
    long_term_enabled: agent.long_term_enabled ?? agent.long_term_memory_enabled,
});

const toAgentPayload = (payload: AgentCreateRequest | AgentUpdateRequest) => ({
    ...payload,
    instructions: payload.instructions ?? "",
    objective: payload.objective ?? payload.goal ?? "",
    goal: payload.goal ?? payload.objective ?? "",
    expected_output: payload.expected_output ?? "",
    temperature: payload.temperature ?? 0.2,
    model: payload.model ?? "",
    color: payload.color ?? "#2563eb",
    icon: payload.icon ?? "sparkles",
    capabilities: payload.capabilities ?? [],
    agent_memory_enabled: payload.agent_memory_enabled ?? true,
    short_term_enabled: payload.short_term_enabled ?? payload.conversation_memory_enabled ?? true,
    long_term_enabled: payload.long_term_enabled ?? payload.long_term_memory_enabled ?? true,
    project_memory_enabled: payload.project_memory_enabled ?? true,
    long_term_memory_enabled: payload.long_term_memory_enabled ?? true,
    conversation_memory_enabled: payload.conversation_memory_enabled ?? true,
    memory_importance: payload.memory_importance ?? 0.5,
    memory_scope: payload.memory_scope ?? "project",
    knowledge_source_ids: payload.knowledge_source_ids ?? [],
    document_library_ids: payload.document_library_ids ?? [],
    github_repositories: payload.github_repositories ?? [],
    sharepoint_sites: payload.sharepoint_sites ?? [],
    uploaded_document_ids: payload.uploaded_document_ids ?? [],
    project_knowledge_enabled: payload.project_knowledge_enabled ?? true,
    tools_allowed: payload.tools_allowed ?? [],
    tool_permissions: payload.tool_permissions ?? {},
    connectors_allowed: payload.connectors_allowed ?? [],
    execution_mode: payload.execution_mode ?? "sequential",
    approval_required: payload.approval_required ?? false,
    max_iterations: payload.max_iterations ?? 1,
    timeout: payload.timeout ?? 60,
    retry_count: payload.retry_count ?? 0,
    retry_policy: payload.retry_policy ?? {},
    tags: payload.tags ?? [],
    connected_agent_ids: payload.connected_agent_ids ?? [],
});

const normalizeVersion = (version: AgentVersionResponse): AgentVersionResponse => ({
    ...version,
});

const normalizeTestRun = (testRun: AgentTestRunResponse): AgentTestRunResponse => ({
    ...testRun,
    tool_calls: testRun.tool_calls.map((toolCall) => ({ ...toolCall })),
    execution: testRun.execution.map((step: AgentExecutionStepResponse) => ({ ...step })),
});

export const agentsApi = {
    list: () =>
        request<AgentRecord[]>("/api/agents", {
            method: "GET",
        }).then((agents) => agents.map(normalizeAgent)),

    getById: (id: string) =>
        request<AgentRecord>(`/api/agents/${id}`, {
            method: "GET",
        }).then(normalizeAgent),

    create: (payload: AgentCreateRequest) =>
        request<AgentRecord>("/api/agents", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(toAgentPayload(payload)),
        }).then(normalizeAgent),

    update: (id: string, payload: AgentUpdateRequest) =>
        request<AgentRecord>(`/api/agents/${id}`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(toAgentPayload(payload)),
        }).then(normalizeAgent),

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
        }).then(normalizeAgent),

    listVersions: (id: string) =>
        request<AgentVersionResponse[]>(`/api/agents/${id}/versions`, {
            method: "GET",
        }).then((versions) => versions.map(normalizeVersion)),

    compareVersions: (id: string, leftVersion: number, rightVersion: number) =>
        request<AgentVersionCompareResponse>(
            `/api/agents/${id}/versions/compare?left_version=${leftVersion}&right_version=${rightVersion}`,
            {
                method: "GET",
            }
        ),

    restoreVersion: (id: string, versionId: string) =>
        request<AgentRecord>(`/api/agents/${id}/versions/${versionId}/restore`, {
            method: "POST",
        }).then(normalizeAgent),

    listTestRuns: (id: string) =>
        request<AgentTestRunResponse[]>(`/api/agents/${id}/test-runs`, {
            method: "GET",
        }).then((runs) => runs.map(normalizeTestRun)),

    runTestPrompt: (id: string, payload: AgentTestRequest) =>
        request<AgentTestRunResponse>(`/api/agents/${id}/test-runs`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        }).then(normalizeTestRun),

    getDashboard: (id: string) =>
        request<AgentDashboardResponse>(`/api/agents/${id}/dashboard`, {
            method: "GET",
        }),
};
