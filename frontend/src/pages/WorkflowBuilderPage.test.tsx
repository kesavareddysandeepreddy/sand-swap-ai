import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkflowBuilderPage } from "./WorkflowBuilderPage";

const workflowsApiMock = vi.hoisted(() => ({
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    listRuns: vi.fn(),
    execute: vi.fn(),
    streamRunEventsUrl: vi.fn(),
}));

vi.mock("../api/workflows", () => ({
    workflowsApi: workflowsApiMock,
}));

describe("WorkflowBuilderPage", () => {
    beforeEach(() => {
        workflowsApiMock.list.mockResolvedValue([
            {
                id: "wf-1",
                name: "Planner Flow",
                description: "desc",
                enabled: true,
                owner_id: "anonymous",
                workspace_id: "default",
                project_id: "default",
                nodes: [
                    { id: "start", node_type: "Start", name: "Start" },
                    {
                        id: "agent",
                        node_type: "Agent",
                        name: "Planner",
                        agent_id: "agent-1",
                    },
                ],
                edges: [
                    {
                        id: "e1",
                        source_node_id: "start",
                        target_node_id: "agent",
                    },
                ],
                execution_settings: {},
                shared_memory_settings: {},
                approval_settings: {},
                retry_settings: {},
                timeout_settings: {},
                version: 2,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
            },
        ]);
        workflowsApiMock.create.mockResolvedValue({ id: "wf-1" });
        workflowsApiMock.update.mockResolvedValue({ id: "wf-1" });
        workflowsApiMock.listRuns.mockResolvedValue([]);
        workflowsApiMock.execute.mockResolvedValue({ run_id: "run-1", status: "queued" });
        workflowsApiMock.streamRunEventsUrl.mockReturnValue("http://localhost/api/workflows/runs/run-1/events");
    });

    it("adds nodes and persists workflow", async () => {
        const user = userEvent.setup();

        render(
            <MemoryRouter>
                <WorkflowBuilderPage />
            </MemoryRouter>
        );

        await waitFor(() => {
            expect(workflowsApiMock.list).toHaveBeenCalled();
        });

        expect(await screen.findByText("Workflow Builder")).toBeInTheDocument();

        await user.click(screen.getByRole("button", { name: "Add Node" }));
        expect(screen.getByText("Research · Agent")).toBeInTheDocument();

        await user.click(screen.getByRole("button", { name: "Save" }));

        await waitFor(() => {
            expect(workflowsApiMock.update).toHaveBeenCalled();
        });
    });
});
