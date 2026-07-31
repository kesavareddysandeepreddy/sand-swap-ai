import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { KnowledgeSourcesPage } from "./KnowledgeSourcesPage";

const mockState = vi.hoisted(() => ({
    sources: [
        {
            id: "source-1",
            project_id: "project-1",
            name: "GitHub Source",
            source_type: "GitHub",
            connection_config: {
                selected_repositories: [
                    {
                        repository: "kesavareddysandeepreddy/sand-swap-ai",
                        branch: "main",
                        default_branch: "main",
                    },
                ],
            },
            enabled: true,
            status: "ready",
            file_count: 4,
            chunk_count: 12,
            embedding_count: 12,
            last_sync: "2026-01-01T00:00:00+00:00",
            created_at: "2026-01-01T00:00:00+00:00",
            updated_at: "2026-01-01T00:00:00+00:00",
            metadata: {},
        },
    ],
    health: {
        status: "ok",
        connectors_total: 11,
        connectors: {
            Upload: "ok",
            GitHub: "not_implemented",
        },
    },
    isLoading: false,
    isMutating: false,
    error: null,
    refresh: vi.fn(async () => undefined),
    createSource: vi.fn(async () => undefined),
    enableSource: vi.fn(async () => undefined),
    disableSource: vi.fn(async () => undefined),
    removeSource: vi.fn(async () => undefined),
    connectConnector: vi.fn(async () => undefined),
    discoverConnector: vi.fn(async () => ({ source_id: "source-1", items: [] })),
    syncConnector: vi.fn(async () => undefined),
    connectorHealth: vi.fn(async () => undefined),
    connectorDetails: {},
}));

vi.mock("../state/useKnowledgeSources", () => ({
    useKnowledgeSources: () => mockState,
}));

describe("KnowledgeSourcesPage", () => {
    it("renders sources and health status", () => {
        render(
            <BrowserRouter>
                <KnowledgeSourcesPage projectId="project-1" />
            </BrowserRouter>
        );

        expect(screen.getByText("Knowledge Sources")).toBeInTheDocument();
        expect(screen.getByText("GitHub Source")).toBeInTheDocument();
        expect(screen.queryByText(/^Config:/)).not.toBeInTheDocument();
        expect(screen.getByText("Repository: sand-swap-ai")).toBeInTheDocument();
        expect(screen.getByText("Branch: main")).toBeInTheDocument();
        expect(screen.getByText("Registered connectors: 11")).toBeInTheDocument();
        expect(
            screen.getByText(/Connector Statuses: Upload=ok \| GitHub=not_implemented/)
        ).toBeInTheDocument();
        expect(screen.getAllByText("ok")).toHaveLength(2);
        expect(screen.getByText("Enterprise Connectors")).toBeInTheDocument();

        fireEvent.change(screen.getByLabelText("Select Source"), {
            target: { value: "source-1" },
        });

        expect(screen.getByText("Repository")).toBeInTheDocument();
        expect(screen.getByText("Branch")).toBeInTheDocument();
        expect(screen.getByText("Health")).toBeInTheDocument();
    });

    it("opens add source dialog and submits", async () => {
        render(
            <BrowserRouter>
                <KnowledgeSourcesPage projectId="project-1" />
            </BrowserRouter>
        );

        fireEvent.click(screen.getByRole("button", { name: "Add Source" }));
        expect(screen.getByText("Add Knowledge Source")).toBeInTheDocument();

        fireEvent.change(screen.getByPlaceholderText("Source display name"), {
            target: { value: "GitHub Docs" },
        });
        fireEvent.change(screen.getByDisplayValue("Upload Files"), {
            target: { value: "GitHub" },
        });
        const dialog = screen.getByRole("dialog");
        fireEvent.click(within(dialog).getByRole("button", { name: "Add Source" }));

        await waitFor(() => {
            expect(mockState.createSource).toHaveBeenCalled();
        });
    });

    it("calls enable/disable actions", async () => {
        render(
            <BrowserRouter>
                <KnowledgeSourcesPage projectId="project-1" />
            </BrowserRouter>
        );

        fireEvent.click(screen.getByRole("button", { name: "Disable" }));
        await waitFor(() => {
            expect(mockState.disableSource).toHaveBeenCalledWith("source-1");
        });
    });
});
