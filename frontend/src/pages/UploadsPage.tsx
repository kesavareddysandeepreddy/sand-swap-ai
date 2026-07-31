import { useMemo } from "react";

import { UploadJobTable } from "../components/uploads/UploadJobTable";
import { UploadProgressBar } from "../components/uploads/UploadProgressBar";
import { UploadSessionCard } from "../components/uploads/UploadSessionCard";
import { UploadSummaryPanel } from "../components/uploads/UploadSummaryPanel";
import { useUploads } from "../state/useUploads";

interface UploadsPageProps {
    projectId: string;
}

const MOCK_FILES = [
    { file_name: "requirements.md", file_size: 1452, mime_type: "text/markdown", parser: "auto" },
    { file_name: "design.pdf", file_size: 348291, mime_type: "application/pdf", parser: "pdf" },
    { file_name: "notes.txt", file_size: 822, mime_type: "text/plain", parser: "plain" },
];

export const UploadsPage = ({ projectId }: UploadsPageProps) => {
    const {
        session,
        jobs,
        progress,
        summary,
        health,
        remaining,
        isLoading,
        isMutating,
        error,
        refresh,
        createSession,
        enqueueMockFiles,
        cancel,
        resume,
    } = useUploads(projectId);

    const fileCount = useMemo(() => MOCK_FILES.length, []);

    const currentProgress = progress?.progress_percent ?? (session ? Math.round((session.processed_files / Math.max(1, session.total_files)) * 100) : 0);
    const eta = progress?.eta ?? null;

    return (
        <div className="knowledge-page">
            <section className="knowledge-toolbar">
                <h2>Uploads</h2>
                <div className="memory-actions">
                    <button type="button" className="memory-button" onClick={() => void refresh()} disabled={isLoading || isMutating}>
                        Refresh
                    </button>
                    <button type="button" className="memory-button" onClick={() => void createSession("upload-source")} disabled={isMutating}>
                        Create Session
                    </button>
                    <button type="button" className="memory-button" onClick={() => void enqueueMockFiles(MOCK_FILES)} disabled={!session || isMutating}>
                        Enqueue Mock Files ({fileCount})
                    </button>
                </div>
            </section>

            {health ? (
                <section className="knowledge-health">
                    <p><strong>{health.status}</strong></p>
                    <p>Sessions {health.sessions}</p>
                    <p>Queued Jobs {health.queued_jobs}</p>
                </section>
            ) : null}

            {error ? (
                <p className="error-banner" role="alert">
                    <span className="error-icon" aria-hidden="true">!</span>
                    {error}
                </p>
            ) : null}

            <UploadProgressBar progressPercent={currentProgress} remaining={remaining} eta={eta} />

            {session ? (
                <UploadSessionCard
                    session={session}
                    remaining={remaining}
                    onCancel={() => void cancel()}
                    onResume={() => void resume()}
                    isMutating={isMutating}
                />
            ) : (
                <p className="memory-status">Create an upload session to manage files.</p>
            )}

            <section className="documents-content">
                <div className="documents-list-card">
                    <UploadJobTable jobs={jobs} />
                </div>
                <UploadSummaryPanel summary={summary} errorCount={0} />
            </section>
        </div>
    );
};
