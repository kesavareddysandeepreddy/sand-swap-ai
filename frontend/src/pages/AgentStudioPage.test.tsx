import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AgentStudioPage } from "./AgentStudioPage";

const useAgentsMock = vi.fn();
const agentsApiMock = vi.hoisted(() => ({
    getDashboard: vi.fn().mockResolvedValue({
        agent_id: "agent-1",
        status: "ready",
        last_run_at: "2026-01-01T00:00:00Z",
        success_rate: 100,
        average_runtime_ms: 120.5,
        memory_usage: "1 mode",
        knowledge_source_count: 2,
        connected_agent_count: 1,
        total_versions: 3,
    }),
    listVersions: vi.fn().mockResolvedValue([]),
    listTestRuns: vi.fn().mockResolvedValue([]),
    runTestPrompt: vi.fn(),
    compareVersions: vi.fn(),
    restoreVersion: vi.fn(),
}));

vi.mock("../state/useAgents", () => ({
    useAgents: () => useAgentsMock(),
}));

vi.mock("../api/agents", () => ({
    agentsApi: agentsApiMock,
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
                    instructions: "Stay precise.",
                    system_prompt: "Be concise.",
                    role: "Planner",
                    goal: "Plan the work",
                    expected_output: "A practical execution plan.",
                    temperature: 0.2,
                    model: "",
                    enabled: true,
                    color: "#2563eb",
                    icon: "sparkles",
                    capabilities: ["research", "planning"],
                    agent_memory_enabled: true,
                    short_term_enabled: true,
                    long_term_enabled: true,
                    long_term_memory_enabled: true,
                    conversation_memory_enabled: true,
                    memory_importance: 0.5,
                    memory_scope: "project",
                    project_memory_enabled: true,
                    knowledge_source_ids: [],
                    document_library_ids: [],
                    github_repositories: [],
                    sharepoint_sites: [],
                    uploaded_document_ids: [],
                    project_knowledge_enabled: true,
                    tools_allowed: ["search"],
                    tool_permissions: { search: true },
                    connectors_allowed: ["GitHub"],
                    execution_mode: "sequential",
                    approval_required: false,
                    max_iterations: 3,
                    timeout: 45,
                    retry_count: 0,
                    retry_policy: {},
                    tags: ["ops"],
                    connected_agent_ids: [],
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

        await user.click(screen.getAllByRole("button", { name: "Disable" })[0]);
        expect(onDisable).toHaveBeenCalledWith("agent-1");

        await user.click(screen.getAllByRole("button", { name: "Delete" })[0]);
        expect(onDelete).toHaveBeenCalledWith("agent-1");

        await user.click(screen.getByRole("button", { name: "New Agent" }));
        expect(screen.getByRole("dialog", { name: "Create Agent" })).toBeInTheDocument();

        confirmSpy.mockRestore();
    });
});
