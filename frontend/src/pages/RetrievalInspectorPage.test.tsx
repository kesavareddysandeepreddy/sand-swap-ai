import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { documentsApi } from "../api/documents";
import { RetrievalInspectorPage } from "./RetrievalInspectorPage";

vi.mock("../api/documents", () => ({
    documentsApi: {
        retrieve: vi.fn(async () => ({
            chunks: [
                {
                    chunk_id: "chunk-1",
                    document_id: "doc-1",
                    document_name: "guide.md",
                    text: "deployment guidance",
                    score: 0.91,
                    metadata: { section: "Deployment" },
                },
            ],
            citations: ["guide.md | page=- | section=Deployment | chunk=chunk-1"],
        })),
    },
}));

describe("RetrievalInspectorPage", () => {
    it("renders safely when optional scores are missing", async () => {
        vi.mocked(documentsApi.retrieve).mockResolvedValueOnce({
            chunks: [
                {
                    chunk_id: "chunk-missing-scores",
                    document_id: "doc-1",
                    document_name: "guide.md",
                    text: "deployment guidance",
                    score: undefined as unknown as number,
                    metadata: { section: "Deployment" },
                },
            ],
            citations: [
                "guide.md | page=- | section=Deployment | chunk=chunk-missing-scores",
            ],
        });

        render(<RetrievalInspectorPage ownerId="user-1" />);

        fireEvent.change(
            screen.getByPlaceholderText(
                "Ask: What chunks are relevant for this query?"
            ),
            { target: { value: "how to deploy" } }
        );

        fireEvent.click(screen.getByRole("button", { name: "Run Inspector" }));

        await waitFor(() => {
            expect(screen.getByText(/semantic=N\/A/i)).toBeInTheDocument();
            expect(screen.getByText(/keyword=0\.0000/i)).toBeInTheDocument();
            expect(screen.getByText(/combined=N\/A/i)).toBeInTheDocument();
        });
    });

    it("shows retrieval results", async () => {
        render(<RetrievalInspectorPage ownerId="user-1" />);

        fireEvent.change(
            screen.getByPlaceholderText(
                "Ask: What chunks are relevant for this query?"
            ),
            { target: { value: "how to deploy" } }
        );

        fireEvent.click(screen.getByRole("button", { name: "Run Inspector" }));

        await waitFor(() => {
            expect(documentsApi.retrieve).toHaveBeenCalled();
            expect(screen.getByText("Retrieved Chunks")).toBeInTheDocument();
            expect(screen.getByText(/ment guidance/i)).toBeInTheDocument();
        });
    });
});
