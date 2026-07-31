import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { AgentRecord } from "../../types/api";
import { AgentDialog } from "./AgentDialog";

describe("AgentDialog", () => {
    it("submits a create payload", async () => {
        const user = userEvent.setup();
        const onSubmit = vi.fn().mockResolvedValue(undefined);
        const onClose = vi.fn();

        render(
            <AgentDialog
                isOpen
                isSaving={false}
                mode="create"
                onClose={onClose}
                onSubmit={onSubmit}
            />
        );

        await user.type(screen.getByLabelText("Agent Name"), "Research Agent");
        await user.type(screen.getByLabelText("Role"), "Analyst");
        await user.type(screen.getByLabelText("Objective"), "Summarize notes");
        await user.type(screen.getByLabelText("System Prompt"), "You are a concise agent.");
        await user.type(screen.getByLabelText("Tags"), "research, internal");
        await user.type(screen.getByLabelText("Allowed Tools"), "search, browser");
        await user.type(screen.getByLabelText("Allowed Connectors"), "GitHub");

        await user.click(screen.getByRole("button", { name: "Create" }));

        expect(onSubmit).toHaveBeenCalledWith(
            expect.objectContaining({
                name: "Research Agent",
                role: "Analyst",
                objective: "Summarize notes",
                system_prompt: "You are a concise agent.",
                tags: ["research", "internal"],
                tools_allowed: ["search", "browser"],
                connectors_allowed: ["GitHub"],
            })
        );
        expect(onClose).toHaveBeenCalled();
    });

    it("submits an edit payload with existing values", async () => {
        const user = userEvent.setup();
        const onSubmit = vi.fn().mockResolvedValue(undefined);
        const onClose = vi.fn();
        const agent: AgentRecord = {
            id: "agent-1",
            name: "Planner",
            description: "Plans tasks",
            role: "Planner",
            objective: "Create execution plans",
            system_prompt: "Always plan first.",
            enabled: true,
            short_term_enabled: true,
            long_term_enabled: true,
            project_memory_enabled: true,
            tools_allowed: ["search"],
            connectors_allowed: ["GitHub"],
            approval_required: false,
            max_iterations: 3,
            timeout: 45,
            retry_policy: { retries: 1 },
            tags: ["ops"],
            owner_id: "user-1",
            workspace_id: "ws-1",
            project_id: "pr-1",
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
        };

        render(
            <AgentDialog
                isOpen
                isSaving={false}
                mode="edit"
                agent={agent}
                onClose={onClose}
                onSubmit={onSubmit}
            />
        );

        expect((screen.getByLabelText("Agent Name") as HTMLInputElement).value).toBe("Planner");

        await user.click(screen.getByLabelText("Enabled"));
        await user.click(screen.getByRole("button", { name: "Save" }));

        expect(onSubmit).toHaveBeenCalledWith(
            expect.objectContaining({
                enabled: false,
                name: "Planner",
            })
        );
        expect(onClose).toHaveBeenCalled();
    });
});
