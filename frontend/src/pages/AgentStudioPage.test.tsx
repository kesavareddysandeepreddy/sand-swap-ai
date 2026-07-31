import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AgentStudioPage } from "./AgentStudioPage";

const useAgentsMock = vi.fn();

vi.mock("../state/useAgents", () => ({
    useAgents: () => useAgentsMock(),
}));

const auth = {
    isAuthenticated: true,
    isLoading: false,
    error: null,
    session: null,
    profile: null,
    workspaces: [{ id: "ws-1", name: "Workspace One", description: "", created_at: "2026-01-01T00:00:00Z", is_active: true }],
    projects: [{ id: "pr-1", workspace_id: "ws-1", name: "Project One", description: "", created_at: "2026-01-01T00:00:00Z", is_active: true }],
    activeWorkspaceId: "ws-1",
    activeProjectId: "pr-1",
    isWorkspaceLoading: false,
    isProjectLoading: false,
    anonymousUserId: "anon-1",
    effectiveUserId: "user-1",
    createWorkspace: vi.fn(),
    createProject: vi.fn(),
    renameWorkspace: vi.fn(),
    renameProject: vi.fn(),
    deleteWorkspace: vi.fn(),
    deleteProject: vi.fn(),
    switchWorkspace: vi.fn(),
    switchProject: vi.fn(),
    loginWithPassword: vi.fn(),
    loginWithGoogleCode: vi.fn(),
    signInWithGooglePopup: vi.fn(),
    loadProfile: vi.fn(),
    logout: vi.fn(),
};

describe("AgentStudioPage", () => {
    it("renders the agent list and actions", async () => {
        const user = userEvent.setup();
        const onDelete = vi.fn().mockResolvedValue(undefined);
        const onEnable = vi.fn().mockResolvedValue(undefined);
        const onDisable = vi.fn().mockResolvedValue(undefined);
        const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);

        useAgentsMock.mockReturnValue({
            agents: [
                {
                    id: "agent-1",
                    name: "Planner",
                    description: "Plans work",
                    role: "Planner",
                    objective: "Plan the work",
                    system_prompt: "Be concise.",
                    enabled: true,
                    short_term_enabled: true,
                    long_term_enabled: true,
                    project_memory_enabled: true,
                    tools_allowed: ["search"],
                    connectors_allowed: ["GitHub"],
                    approval_required: false,
                    max_iterations: 3,
                    timeout: 45,
                    retry_policy: {},
                    tags: ["ops"],
                    owner_id: "user-1",
                    workspace_id: "ws-1",
                    project_id: "pr-1",
                    created_at: "2026-01-01T00:00:00Z",
                    updated_at: "2026-01-01T00:00:00Z",
                },
            ],
            enabledCount: 1,
            isLoading: false,
            isMutating: false,
            error: null,
            refresh: vi.fn(),
            createAgent: vi.fn(),
            updateAgent: vi.fn().mockResolvedValue(undefined),
            deleteAgent: onDelete,
            enableAgent: onEnable,
            disableAgent: onDisable,
        });

        render(
            <MemoryRouter initialEntries={["/agent-studio/agent-1"]}>
                <Routes>
                    <Route path="/agent-studio/:agentId?" element={<AgentStudioPage auth={auth as never} />} />
                </Routes>
            </MemoryRouter>
        );

        expect(screen.getByRole("heading", { name: "Planner" })).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Planner" })).toBeInTheDocument();

        await user.click(screen.getAllByRole("button", { name: "Disable" })[0]);
        expect(onDisable).toHaveBeenCalledWith("agent-1");

        await user.click(screen.getAllByRole("button", { name: "Delete" })[0]);
        expect(onDelete).toHaveBeenCalledWith("agent-1");

        await user.click(screen.getByRole("button", { name: "Create" }));
        expect(screen.getByRole("dialog", { name: "Create Agent" })).toBeInTheDocument();

        confirmSpy.mockRestore();
    });
});
