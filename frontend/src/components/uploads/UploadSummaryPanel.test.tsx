import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { UploadSummaryPanel } from "./UploadSummaryPanel";

describe("UploadSummaryPanel", () => {
    it("renders summary values", () => {
        render(
            <UploadSummaryPanel
                summary={{
                    session_id: "session-1",
                    status: "queued",
                    processed_files: 1,
                    remaining_files: 2,
                    failed_files: 0,
                    skipped_files: 0,
                    current_file: "requirements.md",
                }}
            />
        );

        expect(screen.getByText("queued")).toBeInTheDocument();
        expect(screen.getByText("1")).toBeInTheDocument();
        expect(screen.getByText("requirements.md")).toBeInTheDocument();
    });
});
