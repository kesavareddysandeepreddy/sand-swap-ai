import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MissionControlPage } from "./MissionControlPage";

const workflowsApiMock = vi.hoisted(() => ({
    listMissions: vi.fn(),
    getMissionDashboard: vi.fn(),
    listMissionTemplates: vi.fn(),
    createMission: vi.fn(),
    createMissionTemplate: vi.fn(),
}));

vi.mock("../api/workflows", () => ({
    workflowsApi: workflowsApiMock,
}));

describe("MissionControlPage", () => {
    beforeEach(() => {
        workflowsApiMock.listMissions.mockResolvedValue([
            {
                mission_id: "mission-1",
                goal: "Analyze repository",
                status: "planned",
                owner_id: "anonymous",
                workspace_id: "default",
                project_id: "default",
                run_id: "",
                selected_workflow_id: "",
                planner_output: {
                    mission: { title: "Analyze repository" },
                    task_graph: [{ task_id: "task-1", title: "Requirements" }],
                },
                capability_scores: [
                    {
                        task_id: "task-1",
                        task: "Requirements",
                        selected_agent_id: "agent-1",
                        confidence: 0.9,
                        candidates: [],
                    },
                ],
                execution_recommendations: [{ type: "optimization", message: "Parallelize research." }],
                temporary_agents: [],
                mission_timeline: [],
                artifacts: [],
                governance: {},
                execution_result: {},
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
            },
        ]);
        workflowsApiMock.getMissionDashboard.mockResolvedValue({
            running_missions: 1,
            planned_missions: 1,
            completed_missions: 2,
            failed_missions: 0,
            mission_success_rate: 1.0,
            average_runtime_ms: 1200,
            active_runs: 1,
            retries: 0,
            recent_failures: [],
        });
        workflowsApiMock.listMissionTemplates.mockResolvedValue([]);
        workflowsApiMock.createMission.mockResolvedValue({
            mission_id: "mission-2",
            goal: "Summarize documents",
            status: "running",
            owner_id: "anonymous",
            workspace_id: "default",
            project_id: "default",
            run_id: "",
            selected_workflow_id: "",
            planner_output: {},
            capability_scores: [],
            execution_recommendations: [],
            temporary_agents: [],
            mission_timeline: [],
            artifacts: [],
            governance: {},
            execution_result: {},
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
        });
        workflowsApiMock.createMissionTemplate.mockResolvedValue({
            template_id: "template-1",
            name: "Template",
            description: "desc",
            template: {},
            version: 1,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
        });
    });

    it("loads mission dashboard and launches mission", async () => {
        const user = userEvent.setup();

        render(
            <MemoryRouter>
                <MissionControlPage />
            </MemoryRouter>
        );

        expect(await screen.findByText("Mission Control")).toBeInTheDocument();

        await waitFor(() => {
            expect(workflowsApiMock.listMissions).toHaveBeenCalled();
            expect(workflowsApiMock.getMissionDashboard).toHaveBeenCalled();
        });

        await user.click(screen.getByRole("button", { name: "Launch Mission" }));

        await waitFor(() => {
            expect(workflowsApiMock.createMission).toHaveBeenCalled();
        });

        await user.selectOptions(
            screen.getByRole("combobox"),
            "mission-1"
        );

        await user.click(screen.getByRole("button", { name: "Save Template" }));

        await waitFor(() => {
            expect(workflowsApiMock.createMissionTemplate).toHaveBeenCalled();
        });
    });
});
