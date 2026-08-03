import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkflowsPage } from "./WorkflowsPage";

const workflowsApiMock = vi.hoisted(() => ({
    list: vi.fn(),
    listVersions: vi.fn(),
    validate: vi.fn(),
    create: vi.fn(),
    deleteOne: vi.fn(),
}));

vi.mock("../api/workflows", () => ({
    workflowsApi: workflowsApiMock,
}));

describe("WorkflowsPage", () => {
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
                nodes: [],
                edges: [],
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
        workflowsApiMock.listVersions.mockResolvedValue([]);
        workflowsApiMock.validate.mockResolvedValue({
            valid: true,
            errors: [],
            warnings: [],
        });
        workflowsApiMock.create.mockResolvedValue({ id: "wf-1" });
        workflowsApiMock.deleteOne.mockResolvedValue({ deleted: true });
    });

    it("renders workflow catalog", async () => {
        render(
            <MemoryRouter>
                <WorkflowsPage />
            </MemoryRouter>
        );

        await waitFor(() => {
            expect(workflowsApiMock.list).toHaveBeenCalled();
        });

        expect(await screen.findByText("Workflows")).toBeInTheDocument();
        expect(await screen.findByText("Planner Flow")).toBeInTheDocument();
    });
});
