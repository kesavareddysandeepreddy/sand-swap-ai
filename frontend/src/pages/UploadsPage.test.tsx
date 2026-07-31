import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { UploadsPage } from "./UploadsPage";

const mockState = vi.hoisted(() => ({
    session: {
        id: "session-1",
        project_id: "project-1",
        source_id: "source-1",
        status: "queued",
        total_files: 3,
        processed_files: 1,
        failed_files: 0,
        skipped_files: 0,
        started_at: "2026-01-01T00:00:00+00:00",
        completed_at: null,
        current_file: "requirements.md",
        metadata: {},
    },
    jobs: [
        {
            id: "job-1",
            session_id: "session-1",
            file_name: "requirements.md",
            file_size: 1452,
            mime_type: "text/markdown",
            parser: "auto",
            status: "queued",
            chunks_created: 0,
            embeddings_created: 0,
            started_at: null,
            completed_at: null,
            error: null,
        },
    ],
    progress: {
        session_id: "session-1",
        status: "queued",
        total_files: 3,
        processed_files: 1,
        remaining_files: 2,
        failed_files: 0,
        skipped_files: 0,
        progress_percent: 33.33,
        current_file: "requirements.md",
        eta: "2026-01-01T01:00:00+00:00",
    },
    summary: {
        session_id: "session-1",
        status: "queued",
        processed_files: 1,
        remaining_files: 2,
        failed_files: 0,
        skipped_files: 0,
        current_file: "requirements.md",
    },
    health: { status: "ok", sessions: 1, queued_jobs: 1 },
    remaining: 2,
    isLoading: false,
    isMutating: false,
    error: null,
    refresh: vi.fn(async () => undefined),
    createSession: vi.fn(async () => undefined),
    enqueueMockFiles: vi.fn(async () => undefined),
    cancel: vi.fn(async () => undefined),
    resume: vi.fn(async () => undefined),
}));

vi.mock("../state/useUploads", () => ({
    useUploads: () => mockState,
}));

describe("UploadsPage", () => {
    it("renders progress and job table", () => {
        render(
            <BrowserRouter>
                <UploadsPage projectId="project-1" />
            </BrowserRouter>
        );

        expect(screen.getByText("Uploads")).toBeInTheDocument();
        expect(screen.getAllByText("requirements.md").length).toBeGreaterThan(0);
        expect(screen.getByText(/Progress\s+33(\.33)?%/)).toBeInTheDocument();
        expect(screen.getByText("ok")).toBeInTheDocument();
    });

    it("creates a session and enqueues mock files", async () => {
        render(
            <BrowserRouter>
                <UploadsPage projectId="project-1" />
            </BrowserRouter>
        );

        fireEvent.click(screen.getByRole("button", { name: "Create Session" }));
        fireEvent.click(screen.getByRole("button", { name: /Enqueue Mock Files/ }));

        await waitFor(() => {
            expect(mockState.createSession).toHaveBeenCalledWith("upload-source");
            expect(mockState.enqueueMockFiles).toHaveBeenCalled();
        });
    });

    it("supports cancel and resume", async () => {
        render(
            <BrowserRouter>
                <UploadsPage projectId="project-1" />
            </BrowserRouter>
        );

        fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
        fireEvent.click(screen.getByRole("button", { name: "Resume" }));

        await waitFor(() => {
            expect(mockState.cancel).toHaveBeenCalled();
            expect(mockState.resume).toHaveBeenCalled();
        });
    });
});
