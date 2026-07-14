import type {
    ApiErrorPayload,
    AuthLoginRequest,
    AuthTokenPair,
    AuthUserProfile,
    ChatRequest,
    ChatResponse,
    CreateProjectRequest,
    CreateWorkspaceRequest,
    GoogleOAuthExchangeRequest,
    GoogleOAuthStartResponse,
    HealthResponse,
    LogoutRequest,
    ProjectRecord,
    RefreshTokenRequest,
    RenameProjectRequest,
    RenameWorkspaceRequest,
    WorkspaceRecord,
} from "../types/api";

export class ApiError extends Error {
    status: number;

    constructor(message: string, status: number) {
        super(message);
        this.status = status;
    }
}

export class ApiClient {
    private readonly baseUrl: string;
    private authToken: string | null = null;
    private workspaceId: string | null = null;
    private projectId: string | null = null;

    constructor(
        baseUrl = import.meta.env.VITE_API_BASE_URL ?? "",
    ) {
        this.baseUrl = baseUrl.trim().replace(/\/$/, "");
    }

    setAuthToken(token: string | null): void {
        this.authToken = token;
    }

    setWorkspaceId(workspaceId: string | null): void {
        this.workspaceId = workspaceId;
    }

    setProjectId(projectId: string | null): void {
        this.projectId = projectId;
    }

    async getHealth(): Promise<HealthResponse> {
        return this.request<HealthResponse>("/health", {
            method: "GET",
        });
    }

    async sendChatMessage(payload: ChatRequest): Promise<ChatResponse> {
        return this.request<ChatResponse>("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });
    }

    async login(payload: AuthLoginRequest): Promise<AuthTokenPair> {
        return this.request<AuthTokenPair>("/auth/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });
    }

    async refreshToken(payload: RefreshTokenRequest): Promise<AuthTokenPair> {
        return this.request<AuthTokenPair>("/auth/refresh", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });
    }

    async logout(payload: LogoutRequest): Promise<{ status: string }> {
        return this.request<{ status: string }>("/auth/logout", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });
    }

    async getCurrentUser(): Promise<AuthUserProfile> {
        return this.request<AuthUserProfile>("/auth/me", {
            method: "GET",
        });
    }

    async exchangeGoogleCode(
        payload: GoogleOAuthExchangeRequest
    ): Promise<AuthTokenPair> {
        return this.request<AuthTokenPair>("/auth/oauth/google/exchange", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });
    }

    async startGoogleOAuth(): Promise<GoogleOAuthStartResponse> {
        return this.request<GoogleOAuthStartResponse>("/auth/oauth/google/start", {
            method: "GET",
        });
    }

    async listWorkspaces(): Promise<WorkspaceRecord[]> {
        return this.request<WorkspaceRecord[]>("/auth/workspaces", {
            method: "GET",
        });
    }

    async createWorkspace(payload: CreateWorkspaceRequest): Promise<WorkspaceRecord> {
        return this.request<WorkspaceRecord>("/auth/workspaces", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });
    }

    async renameWorkspace(
        workspaceId: string,
        payload: RenameWorkspaceRequest
    ): Promise<WorkspaceRecord> {
        return this.request<WorkspaceRecord>(`/auth/workspaces/${workspaceId}`, {
            method: "PATCH",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });
    }

    async deleteWorkspace(workspaceId: string): Promise<{ deleted: boolean }> {
        return this.request<{ deleted: boolean }>(`/auth/workspaces/${workspaceId}`, {
            method: "DELETE",
        });
    }

    async switchWorkspace(workspaceId: string): Promise<WorkspaceRecord> {
        return this.request<WorkspaceRecord>("/auth/workspaces/switch", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ workspace_id: workspaceId }),
        });
    }

    async listProjects(): Promise<ProjectRecord[]> {
        return this.request<ProjectRecord[]>("/auth/projects", {
            method: "GET",
        });
    }

    async createProject(payload: CreateProjectRequest): Promise<ProjectRecord> {
        return this.request<ProjectRecord>("/auth/projects", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });
    }

    async renameProject(
        projectId: string,
        payload: RenameProjectRequest
    ): Promise<ProjectRecord> {
        return this.request<ProjectRecord>(`/auth/projects/${projectId}`, {
            method: "PATCH",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });
    }

    async deleteProject(projectId: string): Promise<{ deleted: boolean }> {
        return this.request<{ deleted: boolean }>(`/auth/projects/${projectId}`, {
            method: "DELETE",
        });
    }

    async switchProject(projectId: string): Promise<ProjectRecord> {
        return this.request<ProjectRecord>("/auth/projects/switch", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ project_id: projectId }),
        });
    }

    private async request<T>(path: string, init: RequestInit): Promise<T> {
        const endpoint = this.buildEndpoint(path);
        let response: Response;
        const headers = new Headers(init.headers);
        if (this.authToken) {
            headers.set("Authorization", `Bearer ${this.authToken}`);
        }
        if (this.workspaceId) {
            headers.set("X-Workspace-Id", this.workspaceId);
        }
        if (this.projectId) {
            headers.set("X-Project-Id", this.projectId);
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
                const payload = (await response.json()) as ApiErrorPayload;
                if (payload.detail) {
                    message = payload.detail;
                }
            } catch {
                message = response.statusText || message;
            }
            throw new ApiError(message, response.status);
        }

        return (await response.json()) as T;
    }

    private buildEndpoint(path: string): string {
        if (!this.baseUrl) {
            throw new ApiError("VITE_API_BASE_URL is not configured.", 0);
        }

        const isAbsolute = /^https?:\/\//i.test(this.baseUrl);
        const isRelative = this.baseUrl.startsWith("/");

        if (!isAbsolute && !isRelative) {
            throw new ApiError(
                "VITE_API_BASE_URL must be an absolute URL or '/api'.",
                0,
            );
        }

        return `${this.baseUrl}${path}`;
    }
}

export const apiClient = new ApiClient();
