import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChatPage } from "../../pages/ChatPage";

const buildAuth = () => ({
    isLoading: false,
    isAuthenticated: false,
    error: null,
    session: null,
    profile: null,
    workspaces: [],
    projects: [],
    activeWorkspaceId: null,
    activeProjectId: null,
    isWorkspaceLoading: false,
    isProjectLoading: false,
    anonymousUserId: "anon-1",
    effectiveUserId: "anon-1",
    createWorkspace: vi.fn(async () => undefined),
    createProject: vi.fn(async () => undefined),
    renameWorkspace: vi.fn(async () => undefined),
    renameProject: vi.fn(async () => undefined),
    deleteWorkspace: vi.fn(async () => undefined),
    deleteProject: vi.fn(async () => undefined),
    switchWorkspace: vi.fn(async () => undefined),
    switchProject: vi.fn(async () => undefined),
    loginWithPassword: vi.fn(async () => true),
    loginWithGoogleCode: vi.fn(async () => true),
    signInWithGooglePopup: vi.fn(async () => true),
    loadProfile: vi.fn(async () => null),
    logout: vi.fn(async () => undefined),
});

const traceSummary = [
    {
        trace_id: "trace-plan-1",
        worker_name: "universal_worker",
        request_id: "req-1",
        started_at: "2026-07-16T10:00:00Z",
        completed_at: "2026-07-16T10:00:02Z",
        total_duration_ms: 42,
    },
];

const traceDetail = {
    trace_id: "trace-plan-1",
    worker_name: "universal_worker",
    request_id: "req-1",
    started_at: "2026-07-16T10:00:00Z",
    completed_at: "2026-07-16T10:00:02Z",
    total_duration_ms: 42,
    metadata: {
        task_plan: {
            goal: {
                original_request: "Analyze uploaded files and return summary",
                actions: ["analyze"],
                targets: ["files"],
                constraints: [],
                expected_outputs: ["summary"],
            },
            steps: [
                {
                    step_id: "step-01",
                    order: 1,
                    title: "FILESYSTEM read",
                    action: "read",
                    target: "files",
                    capabilities: ["filesystem"],
                    estimated_cost: 0.31,
                    complexity: "low",
                },
            ],
            dependencies: [],
            inferred_capabilities: ["filesystem"],
            estimated_total_cost: 0.31,
            overall_complexity: "low",
        },
        inferred_capabilities: ["filesystem"],
        estimated_cost: 0.31,
        complexity: "low",
        execution_state: "completed",
        retries: {
            "node:step-01": 0,
        },
        queue_duration_ms: {
            "node:step-01": 4,
        },
        execution_duration_ms: {
            "node:step-01": 8,
        },
        node_status: {
            "node:step-01": "completed",
        },
        checkpoint_state: {
            "node:step-01": "checkpointed",
        },
    },
    steps: [
        {
            id: "step-a",
            stage: "Planner",
            status: "completed",
            started_at: "2026-07-16T10:00:00Z",
            completed_at: "2026-07-16T10:00:01Z",
            duration_ms: 10,
            metadata: {},
        },
    ],
};

describe("Execution plan shared state", () => {
    it("fetches trace once and reuses shared state across panels", async () => {
        const onSendMessage = vi.fn(async () => undefined);
        const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
            const url = String(input);
            if (url.includes("/api/execution/recent")) {
                return new Response(JSON.stringify(traceSummary), { status: 200 });
            }
            if (url.includes("/api/execution/trace/trace-plan-1")) {
                return new Response(JSON.stringify(traceDetail), { status: 200 });
            }
            if (url.includes("/chat/models")) {
                return new Response(JSON.stringify({ models: ["llama3.2:3b"] }), { status: 200 });
            }
            return new Response(JSON.stringify({ detail: "not found" }), { status: 404 });
        });

        render(
            <ChatPage
                auth={buildAuth() as never}
                workspaceScopeId="anon-1:default:default"
                messages={[]}
                isSending={false}
                error={null}
                availableModels={["llama3.2:3b"]}
                selectedModel="llama3.2:3b"
                onSelectModel={() => undefined}
                onSendMessage={onSendMessage}
            />
        );

        fireEvent.click(screen.getByRole("button", { name: /Continue as Guest/i }));

        fireEvent.click(screen.getByRole("button", { name: /Execution Timeline/i }));

        await waitFor(() => {
            expect(screen.getByText("Planner")).toBeInTheDocument();
        });

        const traceCallsAfterFirstOpen = fetchMock.mock.calls.filter((call) =>
            String(call[0]).includes("/api/execution/trace/trace-plan-1")
        );
        expect(traceCallsAfterFirstOpen).toHaveLength(1);

        fireEvent.click(screen.getByRole("button", { name: /Execution Timeline/i }));
        fireEvent.click(screen.getByRole("button", { name: /Execution Timeline/i }));

        fireEvent.click(screen.getByRole("button", { name: /Execution Plan/i }));
        expect(screen.getByText("Goal")).toBeInTheDocument();
        expect(screen.getByText("Filesystem")).toBeInTheDocument();
        expect(screen.getByText(/Retries:/i)).toBeInTheDocument();
        expect(screen.getByText(/Checkpoint:/i)).toBeInTheDocument();

        const traceCallsAfterReopen = fetchMock.mock.calls.filter((call) =>
            String(call[0]).includes("/api/execution/trace/trace-plan-1")
        );
        expect(traceCallsAfterReopen).toHaveLength(1);

        fetchMock.mockRestore();
    });
});
