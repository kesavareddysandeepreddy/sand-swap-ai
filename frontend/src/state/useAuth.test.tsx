import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import { loadAuthSession, persistAuthSession } from "./authStorage";
import { useAuth } from "./useAuth";

vi.mock("../api/client", () => ({
    apiClient: {
        setAuthToken: vi.fn(),
        getCurrentUser: vi.fn(),
        refreshToken: vi.fn(),
        login: vi.fn(),
        exchangeGoogleCode: vi.fn(),
        startGoogleOAuth: vi.fn(),
        logout: vi.fn(),
        listWorkspaces: vi.fn(),
        createWorkspace: vi.fn(),
        renameWorkspace: vi.fn(),
        deleteWorkspace: vi.fn(),
        switchWorkspace: vi.fn(),
        listProjects: vi.fn(),
        createProject: vi.fn(),
        renameProject: vi.fn(),
        deleteProject: vi.fn(),
        switchProject: vi.fn(),
        setWorkspaceId: vi.fn(),
        setProjectId: vi.fn(),
    },
    ApiError: class ApiError extends Error {
        status: number;
        constructor(message: string, status: number) {
            super(message);
            this.status = status;
        }
    },
}));

describe("useAuth", () => {
    beforeEach(() => {
        window.localStorage.clear();
        vi.resetAllMocks();
    });

    it("restores a stored session and profile on startup", async () => {
        persistAuthSession({
            accessToken: "access-token",
            refreshToken: "refresh-token",
            tokenType: "bearer",
        });

        vi.mocked(apiClient.getCurrentUser).mockResolvedValue({
            user_id: "user-1",
            email: "alice@example.com",
            display_name: "Alice Example",
            workspace_id: "workspace-user-1",
            project_id: "workspace-user-1",
            avatar_url: "https://example.com/avatar.png",
            auth_provider: "google",
            google_subject_id: "google-sub-123",
        });
        vi.mocked(apiClient.listWorkspaces).mockResolvedValue([
            {
                id: "workspace-user-1",
                name: "Personal Workspace",
                description: "",
                created_at: "2026-01-01T00:00:00Z",
                is_active: true,
            },
        ]);
        vi.mocked(apiClient.listProjects).mockResolvedValue([
            {
                id: "project-user-1",
                workspace_id: "workspace-user-1",
                name: "General Project",
                description: "",
                created_at: "2026-01-01T00:00:00Z",
                is_active: true,
            },
        ]);

        const { result } = renderHook(() => useAuth());

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false);
        });

        expect(result.current.isAuthenticated).toBe(true);
        expect(result.current.profile?.display_name).toBe("Alice Example");
        expect(result.current.profile?.avatar_url).toBe(
            "https://example.com/avatar.png"
        );
        expect(result.current.effectiveUserId).toBe("user-1");
        expect(loadAuthSession()).toEqual({
            accessToken: "access-token",
            refreshToken: "refresh-token",
            tokenType: "bearer",
        });
        expect(apiClient.setAuthToken).toHaveBeenCalledWith("access-token");
    });

    it("clears local session on logout without touching persisted user data", async () => {
        persistAuthSession({
            accessToken: "access-token",
            refreshToken: "refresh-token",
            tokenType: "bearer",
        });
        vi.mocked(apiClient.getCurrentUser).mockResolvedValue({
            user_id: "user-1",
            email: "alice@example.com",
            display_name: "Alice Example",
            workspace_id: "workspace-user-1",
            project_id: "workspace-user-1",
            avatar_url: null,
        });
        vi.mocked(apiClient.listWorkspaces).mockResolvedValue([
            {
                id: "workspace-user-1",
                name: "Personal Workspace",
                description: "",
                created_at: "2026-01-01T00:00:00Z",
                is_active: true,
            },
        ]);
        vi.mocked(apiClient.listProjects).mockResolvedValue([
            {
                id: "project-user-1",
                workspace_id: "workspace-user-1",
                name: "General Project",
                description: "",
                created_at: "2026-01-01T00:00:00Z",
                is_active: true,
            },
        ]);

        vi.mocked(apiClient.logout).mockResolvedValue({ status: "ok" });

        const { result } = renderHook(() => useAuth());
        await waitFor(() => {
            expect(result.current.isLoading).toBe(false);
        });

        await act(async () => {
            await result.current.logout();
        });

        expect(result.current.isAuthenticated).toBe(false);
        expect(result.current.profile).toBeNull();
        expect(result.current.effectiveUserId.startsWith("anon-")).toBe(true);
        expect(loadAuthSession()).toBeNull();
        expect(apiClient.setAuthToken).toHaveBeenLastCalledWith(null);
    });

    it("switches active workspace and updates profile context", async () => {
        persistAuthSession({
            accessToken: "access-token",
            refreshToken: "refresh-token",
            tokenType: "bearer",
        });
        vi.mocked(apiClient.getCurrentUser).mockResolvedValue({
            user_id: "user-1",
            email: "alice@example.com",
            display_name: "Alice Example",
            workspace_id: "workspace-a",
            project_id: "workspace-a",
            avatar_url: null,
        });
        vi.mocked(apiClient.listWorkspaces).mockResolvedValue([
            {
                id: "workspace-a",
                name: "Workspace A",
                description: "",
                created_at: "2026-01-01T00:00:00Z",
                is_active: true,
            },
            {
                id: "workspace-b",
                name: "Workspace B",
                description: "",
                created_at: "2026-01-02T00:00:00Z",
                is_active: false,
            },
        ]);
        vi.mocked(apiClient.listProjects).mockResolvedValue([
            {
                id: "project-a",
                workspace_id: "workspace-a",
                name: "Project A",
                description: "",
                created_at: "2026-01-01T00:00:00Z",
                is_active: true,
            },
        ]);
        vi.mocked(apiClient.switchWorkspace).mockResolvedValue({
            id: "workspace-b",
            name: "Workspace B",
            description: "",
            created_at: "2026-01-02T00:00:00Z",
            is_active: true,
        });
        vi.mocked(apiClient.listProjects).mockResolvedValueOnce([
            {
                id: "project-a",
                workspace_id: "workspace-a",
                name: "Project A",
                description: "",
                created_at: "2026-01-01T00:00:00Z",
                is_active: true,
            },
        ]).mockResolvedValueOnce([
            {
                id: "project-b",
                workspace_id: "workspace-b",
                name: "Project B",
                description: "",
                created_at: "2026-01-02T00:00:00Z",
                is_active: true,
            },
        ]);

        const { result } = renderHook(() => useAuth());

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false);
        });

        await act(async () => {
            await result.current.switchWorkspace("workspace-b");
        });

        expect(result.current.activeWorkspaceId).toBe("workspace-b");
        expect(result.current.profile?.workspace_id).toBe("workspace-b");
        expect(apiClient.switchWorkspace).toHaveBeenCalledWith("workspace-b");
        expect(apiClient.setWorkspaceId).toHaveBeenCalledWith("workspace-b");
    });

    it("switches active project and updates profile context", async () => {
        persistAuthSession({
            accessToken: "access-token",
            refreshToken: "refresh-token",
            tokenType: "bearer",
        });
        vi.mocked(apiClient.getCurrentUser).mockResolvedValue({
            user_id: "user-1",
            email: "alice@example.com",
            display_name: "Alice Example",
            workspace_id: "workspace-a",
            project_id: "project-a",
            avatar_url: null,
        });
        vi.mocked(apiClient.listWorkspaces).mockResolvedValue([
            {
                id: "workspace-a",
                name: "Workspace A",
                description: "",
                created_at: "2026-01-01T00:00:00Z",
                is_active: true,
            },
        ]);
        vi.mocked(apiClient.listProjects).mockResolvedValue([
            {
                id: "project-a",
                workspace_id: "workspace-a",
                name: "Project A",
                description: "",
                created_at: "2026-01-01T00:00:00Z",
                is_active: true,
            },
            {
                id: "project-b",
                workspace_id: "workspace-a",
                name: "Project B",
                description: "",
                created_at: "2026-01-02T00:00:00Z",
                is_active: false,
            },
        ]);
        vi.mocked(apiClient.switchProject).mockResolvedValue({
            id: "project-b",
            workspace_id: "workspace-a",
            name: "Project B",
            description: "",
            created_at: "2026-01-02T00:00:00Z",
            is_active: true,
        });

        const { result } = renderHook(() => useAuth());

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false);
        });

        await act(async () => {
            await result.current.switchProject("project-b");
        });

        expect(result.current.activeProjectId).toBe("project-b");
        expect(result.current.profile?.project_id).toBe("project-b");
        expect(apiClient.switchProject).toHaveBeenCalledWith("project-b");
        expect(apiClient.setProjectId).toHaveBeenCalledWith("project-b");
    });
});