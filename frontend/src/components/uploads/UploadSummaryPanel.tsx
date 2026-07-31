import type { UploadSummaryRecord } from "../../types/api";

interface UploadSummaryPanelProps {
    summary: UploadSummaryRecord | null;
    errorCount?: number;
}

export const UploadSummaryPanel = ({ summary, errorCount = 0 }: UploadSummaryPanelProps) => {
    if (!summary) {
        return <p className="memory-status">Create a session to see upload summary details.</p>;
    }

    return (
        <aside className="documents-viewer-card">
            <h2>Upload Summary</h2>
            <dl className="memory-detail-list">
                <dt>Status</dt>
                <dd>{summary.status}</dd>
                <dt>Processed</dt>
                <dd>{summary.processed_files}</dd>
                <dt>Remaining</dt>
                <dd>{summary.remaining_files}</dd>
                <dt>Failed</dt>
                <dd>{summary.failed_files}</dd>
                <dt>Skipped</dt>
                <dd>{summary.skipped_files}</dd>
                <dt>Current File</dt>
                <dd>{summary.current_file ?? "-"}</dd>
                <dt>Errors</dt>
                <dd>{errorCount}</dd>
            </dl>
        </aside>
    );
};
