import { loadAuthSession } from "../state/authStorage";
import type {
    AutonomousMissionRecord,
    AutonomousMissionRequest,
    AutonomousMissionStatusRecord,
    MissionControlDashboard,
    MissionTemplateRecord,
    MissionTemplateRequest,
    WorkflowAgentMessagesResponse,
    WorkflowAgentRegistryResponse,
    WorkflowArtifactsResponse,
    WorkflowCreateRequest,
    WorkflowDashboardResponse,
    WorkflowDebuggerResponse,
    WorkflowExecutionRequest,
    WorkflowExecutionResponse,
    WorkflowNodeDebuggerResponse,
    WorkflowRecord,
    WorkflowRetryRequest,
    WorkflowRunActionRequest,
    WorkflowRunRecord,
    WorkflowSupervisorResponse,
    WorkflowTimelineResponse,
    WorkflowUpdateRequest,
    WorkflowValidationResponse,
    WorkflowVersionCompareResponse,
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

    compareVersions: (workflowId: string, leftVersion: number, rightVersion: number) =>
        request<WorkflowVersionCompareResponse>(
            `/api/workflows/${workflowId}/versions/compare?left_version=${leftVersion}&right_version=${rightVersion}`,
            {
                method: "GET",
            }
        ),

    restoreVersion: (workflowId: string, versionId: string) =>
        request<WorkflowRecord>(
            `/api/workflows/${workflowId}/versions/${versionId}/restore`,
            {
                method: "POST",
            }
        ),

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

    getRunState: (runId: string) =>
        request<WorkflowRunRecord>(`/api/workflows/runs/${runId}/state`, {
            method: "GET",
        }),

    getRunDebugger: (runId: string) =>
        request<WorkflowDebuggerResponse>(`/api/workflows/runs/${runId}/debugger`, {
            method: "GET",
        }),

    getRunNodeDebugger: (runId: string, nodeId: string) =>
        request<WorkflowNodeDebuggerResponse>(
            `/api/workflows/runs/${runId}/nodes/${nodeId}`,
            {
                method: "GET",
            }
        ),

    getRunAgentRegistry: (runId: string) =>
        request<WorkflowAgentRegistryResponse>(
            `/api/workflows/runs/${runId}/agent-registry`,
            {
                method: "GET",
            }
        ),

    getRunMessages: (runId: string) =>
        request<WorkflowAgentMessagesResponse>(`/api/workflows/runs/${runId}/messages`, {
            method: "GET",
        }),

    getRunTimeline: (runId: string) =>
        request<WorkflowTimelineResponse>(`/api/workflows/runs/${runId}/timeline`, {
            method: "GET",
        }),

    getRunArtifacts: (runId: string) =>
        request<WorkflowArtifactsResponse>(`/api/workflows/runs/${runId}/artifacts`, {
            method: "GET",
        }),

    getRunSupervisor: (runId: string) =>
        request<WorkflowSupervisorResponse>(`/api/workflows/runs/${runId}/supervisor`, {
            method: "GET",
        }),

    cancelRun: (runId: string) =>
        request<WorkflowRunRecord>(`/api/workflows/runs/${runId}/cancel`, {
            method: "POST",
        }),

    pauseRun: (runId: string) =>
        request<WorkflowRunRecord>(`/api/workflows/runs/${runId}/pause`, {
            method: "POST",
        }),

    resumeRun: (runId: string) =>
        request<WorkflowRunRecord>(`/api/workflows/runs/${runId}/resume`, {
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

    retryRun: (runId: string, payload: WorkflowRetryRequest) =>
        request<WorkflowRunRecord>(`/api/workflows/runs/${runId}/retry`, {
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

    createMission: (payload: AutonomousMissionRequest) =>
        request<AutonomousMissionRecord>("/api/workflows/missions", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        }),

    listMissions: (limit = 50) =>
        request<AutonomousMissionRecord[]>(`/api/workflows/missions?limit=${limit}`, {
            method: "GET",
        }),

    getMission: (missionId: string) =>
        request<AutonomousMissionRecord>(`/api/workflows/missions/${missionId}`, {
            method: "GET",
        }),

    getMissionStatus: (missionId: string) =>
        request<AutonomousMissionStatusRecord>(
            `/api/workflows/missions/${missionId}/status`,
            {
                method: "GET",
            }
        ),

    getMissionPlannerOutput: (missionId: string) =>
        request<{ mission_id: string; planner_output: Record<string, unknown> }>(
            `/api/workflows/missions/${missionId}/planner`,
            {
                method: "GET",
            }
        ),

    getMissionCapabilityScores: (missionId: string) =>
        request<{ mission_id: string; scores: Array<Record<string, unknown>> }>(
            `/api/workflows/missions/${missionId}/capability-scores`,
            {
                method: "GET",
            }
        ),

    getMissionRecommendations: (missionId: string) =>
        request<{ mission_id: string; recommendations: Array<Record<string, unknown>> }>(
            `/api/workflows/missions/${missionId}/recommendations`,
            {
                method: "GET",
            }
        ),

    getMissionTemporaryAgents: (missionId: string) =>
        request<{ mission_id: string; temporary_agents: Array<Record<string, unknown>> }>(
            `/api/workflows/missions/${missionId}/temporary-agents`,
            {
                method: "GET",
            }
        ),

    getMissionDashboard: () =>
        request<MissionControlDashboard>("/api/workflows/missions/dashboard", {
            method: "GET",
        }),

    createMissionTemplate: (payload: MissionTemplateRequest) =>
        request<MissionTemplateRecord>("/api/workflows/mission-templates", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        }),

    updateMissionTemplate: (templateId: string, payload: MissionTemplateRequest) =>
        request<MissionTemplateRecord>(`/api/workflows/mission-templates/${templateId}`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        }),

    listMissionTemplates: () =>
        request<MissionTemplateRecord[]>("/api/workflows/mission-templates", {
            method: "GET",
        }),

    streamRunEventsUrl: (runId: string) => `${getBaseUrl()}/api/workflows/runs/${runId}/events`,
};
