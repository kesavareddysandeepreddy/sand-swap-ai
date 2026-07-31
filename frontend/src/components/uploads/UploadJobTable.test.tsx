import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { UploadJobTable } from "./UploadJobTable";

describe("UploadJobTable", () => {
    it("renders queued jobs", () => {
        render(
            <UploadJobTable
                jobs={[
                    {
                        id: "job-1",
                        session_id: "session-1",
                        file_name: "alpha.txt",
                        file_size: 10,
                        mime_type: "text/plain",
                        parser: "auto",
                        status: "queued",
                        chunks_created: 0,
                        embeddings_created: 0,
                        started_at: null,
                        completed_at: null,
                        error: null,
                    },
                ]}
            />
        );

        expect(screen.getByText("alpha.txt")).toBeInTheDocument();
        expect(screen.getByText("queued")).toBeInTheDocument();
    });
});
