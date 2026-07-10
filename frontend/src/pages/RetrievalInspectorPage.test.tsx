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
    it("shows retrieval results", async () => {
        render(<RetrievalInspectorPage />);

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
