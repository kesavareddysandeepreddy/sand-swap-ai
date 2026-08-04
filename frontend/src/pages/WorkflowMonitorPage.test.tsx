import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkflowMonitorPage } from "./WorkflowMonitorPage";

const workflowsApiMock = vi.hoisted(() => ({
    getRun: vi.fn(),
    getDashboard: vi.fn(),
    getRunDebugger: vi.fn(),
    getRunAgentRegistry: vi.fn(),
    getRunMessages: vi.fn(),
    getRunTimeline: vi.fn(),
    getRunArtifacts: vi.fn(),
    getRunSupervisor: vi.fn(),
    streamRunEventsUrl: vi.fn(),
    pauseRun: vi.fn(),
    resumeRun: vi.fn(),
    cancelRun: vi.fn(),
    applyRunAction: vi.fn(),
    getRunNodeDebugger: vi.fn(),
    retryRun: vi.fn(),
}));

class EventSourceMock {
    public onerror: ((event: Event) => void) | null = null;

    public addEventListener = vi.fn();

    public close = vi.fn();

    public constructor(url: string) {
        void url;
    }
}

vi.mock("../api/workflows", () => ({
    workflowsApi: workflowsApiMock,
}));

describe("WorkflowMonitorPage", () => {
    beforeEach(() => {
        vi.stubGlobal("EventSource", EventSourceMock);

        const baseRun = {
            id: "run-1",
            workflow_id: "wf-1",
            status: "running",
            input_payload: {},
            context: {},
            started_at: new Date().toISOString(),
            ended_at: null,
            duration_ms: 120,
            error: "",
            current_node_id: "agent",
            pending_node_id: "",
            cancel_requested: false,
            node_records: [
                {
                    node_id: "agent",
                    node_name: "Planner",
                    node_type: "Agent",
                    status: "running",
                    started_at: new Date().toISOString(),
                    completed_at: null,
                    duration_ms: 120,
                    error: "",
                    output: {},
                },
            ],
            messages: [],
            artifacts: [],
            logs: [],
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
        };

        workflowsApiMock.getRun.mockResolvedValue(baseRun);
        workflowsApiMock.getDashboard.mockResolvedValue({
            running: 1,
            queued: 0,
            succeeded: 3,
            failed: 0,
            average_runtime_ms: 90,
            average_token_usage: 0,
            agent_usage: {},
            most_active_workflows: [],
        });
        workflowsApiMock.getRunDebugger.mockResolvedValue({
            run: null,
            workflow: null,
            nodes: {},
            timeline: [],
            messages: [],
        });
        workflowsApiMock.streamRunEventsUrl.mockReturnValue(
            "http://localhost/api/workflows/runs/run-1/events"
        );
        workflowsApiMock.getRunAgentRegistry.mockResolvedValue({
            run_id: "run-1",
            registry: {},
        });
        workflowsApiMock.getRunMessages.mockResolvedValue({
            run_id: "run-1",
            messages: [],
        });
        workflowsApiMock.getRunTimeline.mockResolvedValue({
            run_id: "run-1",
            timeline: [],
        });
        workflowsApiMock.getRunArtifacts.mockResolvedValue({
            run_id: "run-1",
            artifacts: [],
        });
        workflowsApiMock.getRunSupervisor.mockResolvedValue({
            run_id: "run-1",
            supervisor: {},
        });
        workflowsApiMock.pauseRun.mockResolvedValue({ ...baseRun, status: "paused" });
        workflowsApiMock.resumeRun.mockResolvedValue({ ...baseRun, status: "running" });
        workflowsApiMock.cancelRun.mockResolvedValue({ ...baseRun, status: "canceled" });
        workflowsApiMock.applyRunAction.mockResolvedValue({ ...baseRun, status: "running" });
        workflowsApiMock.retryRun.mockResolvedValue({ ...baseRun, status: "queued" });
        workflowsApiMock.getRunNodeDebugger.mockResolvedValue({
            run_id: "run-1",
            node_id: "agent",
            record: {
                node_id: "agent",
                node_name: "Planner",
                node_type: "Agent",
                status: "running",
                started_at: new Date().toISOString(),
                completed_at: null,
                duration_ms: 100,
                error: "",
                output: {},
            },
            logs: [],
        });
    });

    it("loads run monitor and executes pause/resume controls", async () => {
        const user = userEvent.setup();

        render(
            <MemoryRouter initialEntries={["/workflows/monitor/run-1"]}>
                <Routes>
                    <Route path="/workflows/monitor/:runId" element={<WorkflowMonitorPage />} />
                </Routes>
            </MemoryRouter>
        );

        await waitFor(() => {
            expect(workflowsApiMock.getRun).toHaveBeenCalledWith("run-1");
        });

        expect(await screen.findByText("Execution Monitor")).toBeInTheDocument();

        await user.click(screen.getByRole("button", { name: "Pause" }));
        await waitFor(() => {
            expect(workflowsApiMock.pauseRun).toHaveBeenCalledWith("run-1");
        });

        await user.click(screen.getByRole("button", { name: "Resume" }));
        await waitFor(() => {
            expect(workflowsApiMock.resumeRun).toHaveBeenCalledWith("run-1");
        });
    });
});
