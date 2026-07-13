import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { DocumentsPage } from "./DocumentsPage";

const mockState = vi.hoisted(() => ({
    documents: [
        {
            id: "doc-1",
            name: "runbook.md",
            original_filename: "runbook.md",
            stored_path: "/tmp/doc-1_runbook.md",
            file_type: "md",
            size_bytes: 1536,
            chunk_count: 4,
            embedding_status: "completed",
            index_status: "indexed",
            metadata: { category: "document" },
            created_at: "2026-01-01T00:00:00+00:00",
            updated_at: "2026-01-01T00:00:00+00:00",
        },
    ],
    selectedDocument: null,
    selectedChunks: [],
    categories: ["document"],
    isLoading: false,
    isUploading: false,
    error: null,
    refresh: vi.fn(async () => undefined),
    upload: vi.fn(async () => undefined),
    selectDocument: vi.fn(async () => undefined),
    deleteOne: vi.fn(async () => undefined),
    deleteAll: vi.fn(async () => undefined),
}));

vi.mock("../state/useDocuments", () => ({
    useDocuments: () => mockState,
}));

describe("DocumentsPage", () => {
    it("renders uploaded document list", () => {
        render(
            <BrowserRouter>
                <DocumentsPage ownerId="user-1" />
            </BrowserRouter>
        );

        expect(screen.getByText("runbook.md")).toBeInTheDocument();
        expect(screen.getByText("indexed")).toBeInTheDocument();
    });

    it("triggers search filtering", async () => {
        render(
            <BrowserRouter>
                <DocumentsPage ownerId="user-1" />
            </BrowserRouter>
        );

        fireEvent.change(screen.getByPlaceholderText("Search documents"), {
            target: { value: "nomatch" },
        });

        await waitFor(() => {
            expect(
                screen.getByText("No documents available for the selected filters.")
            ).toBeInTheDocument();
        });
    });
});
