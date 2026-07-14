import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { documentsApi } from "../api/documents";
import { ChatPage } from "./ChatPage";

const promptSpy = vi.spyOn(window, "prompt");
const confirmSpy = vi.spyOn(window, "confirm");

vi.mock("../api/documents", () => ({
    documentsApi: {
        upload: vi.fn(async () => ({ id: "doc-1" })),
    },
}));

const buildAuth = (isAuthenticated = false) => ({
    isLoading: false,
    isAuthenticated,
    error: null,
    session: null,
    profile: isAuthenticated
        ? {
            user_id: "user-1",
            email: "user@example.com",
            display_name: "User",
            workspace_id: "workspace-1",
            project_id: "project-1",
            avatar_url: null,
        }
        : null,
    workspaces: [
        {
            id: "workspace-1",
            name: "Workspace A",
            description: "",
            created_at: "2026-01-01T00:00:00Z",
            is_active: true,
        },
        {
            id: "workspace-2",
            name: "Workspace B",
            description: "",
            created_at: "2026-01-02T00:00:00Z",
            is_active: false,
        },
    ],
    projects: [
        {
            id: "project-1",
            workspace_id: "workspace-1",
            name: "Project A",
            description: "",
            created_at: "2026-01-01T00:00:00Z",
            is_active: true,
        },
        {
            id: "project-2",
            workspace_id: "workspace-1",
            name: "Project B",
            description: "",
            created_at: "2026-01-02T00:00:00Z",
            is_active: false,
        },
    ],
    activeWorkspaceId: "workspace-1",
    activeProjectId: "project-1",
    isWorkspaceLoading: false,
    isProjectLoading: false,
    anonymousUserId: "anon-1",
    effectiveUserId: isAuthenticated ? "user-1" : "anon-1",
    createWorkspace: vi.fn(async () => ({
        id: "workspace-1",
        name: "Workspace A",
        description: "",
        created_at: "2026-01-01T00:00:00Z",
        is_active: true,
    })),
    createProject: vi.fn(async () => ({
        id: "project-1",
        workspace_id: "workspace-1",
        name: "Project A",
        description: "",
        created_at: "2026-01-01T00:00:00Z",
        is_active: true,
    })),
    renameWorkspace: vi.fn(async () => ({
        id: "workspace-1",
        name: "Workspace A",
        description: "",
        created_at: "2026-01-01T00:00:00Z",
        is_active: true,
    })),
    renameProject: vi.fn(async () => ({
        id: "project-1",
        workspace_id: "workspace-1",
        name: "Project A",
        description: "",
        created_at: "2026-01-01T00:00:00Z",
        is_active: true,
    })),
    deleteWorkspace: vi.fn(async () => undefined),
    deleteProject: vi.fn(async () => undefined),
    switchWorkspace: vi.fn(async () => ({
        id: "workspace-1",
        name: "Workspace A",
        description: "",
        created_at: "2026-01-01T00:00:00Z",
        is_active: true,
    })),
    switchProject: vi.fn(async () => ({
        id: "project-1",
        workspace_id: "workspace-1",
        name: "Project A",
        description: "",
        created_at: "2026-01-01T00:00:00Z",
        is_active: true,
    })),
    loginWithPassword: vi.fn(async () => true),
    loginWithGoogleCode: vi.fn(async () => true),
    signInWithGooglePopup: vi.fn(async () => true),
    loadProfile: vi.fn(async () => null),
    logout: vi.fn(async () => undefined),
});

describe("ChatPage", () => {
    beforeEach(() => {
        window.localStorage.clear();
        window.sessionStorage.clear();
        vi.clearAllMocks();
        promptSpy.mockReset();
        confirmSpy.mockReset();
        confirmSpy.mockReturnValue(true);
    });

    it("shows guest welcome only once per browser session", async () => {
        const auth = buildAuth(false);
        const baseProps = {
            auth,
            workspaceScopeId: "anon-1:default:default",
            messages: [],
            isSending: false,
            error: null,
            availableModels: ["llama3.2:3b"],
            selectedModel: "llama3.2:3b",
            onSelectModel: vi.fn(),
            onSendMessage: vi.fn(async () => undefined),
        };

        const first = render(<ChatPage {...baseProps} />);
        expect(screen.getByRole("dialog", { name: "Welcome to SandSwap AI" })).toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", { name: "Continue as Guest" }));
        await waitFor(() => {
            expect(screen.queryByRole("dialog", { name: "Welcome to SandSwap AI" })).not.toBeInTheDocument();
        });
        first.unmount();

        render(<ChatPage {...baseProps} />);
        expect(screen.queryByRole("dialog", { name: "Welcome to SandSwap AI" })).not.toBeInTheDocument();
    });

    it("loads model selector options and notifies selection", () => {
        const auth = buildAuth(true);
        const onSelectModel = vi.fn();

        render(
            <ChatPage
                auth={auth}
                workspaceScopeId="user-1:workspace-1:project-1"
                messages={[]}
                isSending={false}
                error={null}
                availableModels={["llama3.2:3b", "qwen2.5:14b"]}
                selectedModel="llama3.2:3b"
                onSelectModel={onSelectModel}
                onSendMessage={vi.fn(async () => undefined)}
            />
        );

        const modelSelect = screen.getByLabelText("Model") as HTMLSelectElement;
        expect(modelSelect.value).toBe("llama3.2:3b");
        expect(screen.getByRole("option", { name: "qwen2.5:14b" })).toBeInTheDocument();

        fireEvent.change(modelSelect, { target: { value: "qwen2.5:14b" } });
        expect(onSelectModel).toHaveBeenCalledWith("qwen2.5:14b");
    });

    it("uploads document from chat and shows success message", async () => {
        const auth = buildAuth(false);

        render(
            <ChatPage
                auth={auth}
                workspaceScopeId="anon-1:default:default"
                messages={[]}
                isSending={false}
                error={null}
                availableModels={["llama3.2:3b"]}
                selectedModel="llama3.2:3b"
                onSelectModel={vi.fn()}
                onSendMessage={vi.fn(async () => undefined)}
            />
        );

        const file = new File(["hello"], "note.txt", { type: "text/plain" });
        const input = screen.getByLabelText("Upload document from chat") as HTMLInputElement;
        fireEvent.change(input, { target: { files: [file] } });

        await waitFor(() => {
            expect(documentsApi.upload).toHaveBeenCalled();
            expect(
                screen.getByText("Document indexed successfully. You can now ask questions about it.")
            ).toBeInTheDocument();
        });
    });

    it("hides workspace and project selectors for guests", () => {
        const auth = buildAuth(false);

        render(
            <ChatPage
                auth={auth}
                workspaceScopeId="anon-1:default:default"
                messages={[]}
                isSending={false}
                error={null}
                availableModels={["llama3.2:3b"]}
                selectedModel="llama3.2:3b"
                onSelectModel={vi.fn()}
                onSendMessage={vi.fn(async () => undefined)}
            />
        );

        expect(screen.queryByLabelText("Workspace")).not.toBeInTheDocument();
        expect(screen.queryByLabelText("Project")).not.toBeInTheDocument();
        expect(screen.getByLabelText("Model")).toBeInTheDocument();
    });

    it("does not upload when clicking outside upload control", async () => {
        const auth = buildAuth(true);

        render(
            <ChatPage
                auth={auth}
                workspaceScopeId="user-1:workspace-1:project-1"
                messages={[]}
                isSending={false}
                error={null}
                availableModels={["llama3.2:3b"]}
                selectedModel="llama3.2:3b"
                onSelectModel={vi.fn()}
                onSendMessage={vi.fn(async () => undefined)}
            />
        );

        fireEvent.click(screen.getByLabelText("Workspace"));
        fireEvent.click(screen.getByLabelText("Project"));
        fireEvent.click(screen.getByLabelText("Model"));
        fireEvent.click(screen.getByPlaceholderText("Ask SandSwap AI something..."));
        fireEvent.click(screen.getByText("Welcome to SandSwap AI"));

        await waitFor(() => {
            expect(documentsApi.upload).not.toHaveBeenCalled();
        });
    });

    it("keeps workspace CRUD controls available in chat", async () => {
        const auth = buildAuth(true);
        promptSpy
            .mockReturnValueOnce("New Workspace")
            .mockReturnValueOnce("Renamed Workspace");

        render(
            <ChatPage
                auth={auth}
                workspaceScopeId="user-1:workspace-1:project-1"
                messages={[]}
                isSending={false}
                error={null}
                availableModels={["llama3.2:3b"]}
                selectedModel="llama3.2:3b"
                onSelectModel={vi.fn()}
                onSendMessage={vi.fn(async () => undefined)}
            />
        );

        fireEvent.click(screen.getAllByRole("button", { name: "New" })[0]);
        fireEvent.click(screen.getAllByRole("button", { name: "Rename" })[0]);
        fireEvent.click(screen.getAllByRole("button", { name: "Delete" })[0]);

        await waitFor(() => {
            expect(auth.createWorkspace).toHaveBeenCalledWith("New Workspace");
            expect(auth.renameWorkspace).toHaveBeenCalledWith(
                "workspace-1",
                "Renamed Workspace"
            );
            expect(auth.deleteWorkspace).toHaveBeenCalledWith("workspace-1");
        });
    });

    it("keeps project CRUD controls available in chat", async () => {
        const auth = buildAuth(true);
        promptSpy
            .mockReturnValueOnce("New Project")
            .mockReturnValueOnce("Renamed Project");

        render(
            <ChatPage
                auth={auth}
                workspaceScopeId="user-1:workspace-1:project-1"
                messages={[]}
                isSending={false}
                error={null}
                availableModels={["llama3.2:3b"]}
                selectedModel="llama3.2:3b"
                onSelectModel={vi.fn()}
                onSendMessage={vi.fn(async () => undefined)}
            />
        );

        fireEvent.click(screen.getAllByRole("button", { name: "New" })[1]);
        fireEvent.click(screen.getAllByRole("button", { name: "Rename" })[1]);
        fireEvent.click(screen.getAllByRole("button", { name: "Delete" })[1]);

        await waitFor(() => {
            expect(auth.createProject).toHaveBeenCalledWith("New Project");
            expect(auth.renameProject).toHaveBeenCalledWith(
                "project-1",
                "Renamed Project"
            );
            expect(auth.deleteProject).toHaveBeenCalledWith("project-1");
        });
    });
});
