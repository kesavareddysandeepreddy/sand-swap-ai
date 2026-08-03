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
            instructions: "Stay concise and practical.",
            system_prompt: "Always plan first.",
            role: "Planner",
            goal: "Create execution plans",
            expected_output: "A concise execution plan.",
            temperature: 0.2,
            model: "",
            enabled: true,
            color: "#2563eb",
            icon: "sparkles",
            capabilities: [],
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
            retry_policy: { retries: 1 },
            tags: ["ops"],
            connected_agent_ids: [],
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

        await user.click(screen.getByRole("checkbox", { name: "Enabled" }));
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
