import type { UploadSessionRecord } from "../../types/api";
import { formatTimestamp } from "../../utils/date";

interface UploadSessionCardProps {
    session: UploadSessionRecord;
    remaining: number;
    onCancel: () => void;
    onResume: () => void;
    isMutating: boolean;
}

export const UploadSessionCard = ({
    session,
    remaining,
    onCancel,
    onResume,
    isMutating,
}: UploadSessionCardProps) => {
    const progressPercent = session.total_files > 0
        ? Math.round((session.processed_files / session.total_files) * 100)
        : 0;

    return (
        <section className="upload-session-card">
            <header className="knowledge-source-card-header">
                <div>
                    <h3>Upload Session</h3>
                    <p>
                        <span className="knowledge-chip">project: {session.project_id}</span>
                        <span className="knowledge-chip">source: {session.source_id}</span>
                    </p>
                </div>
                <span className="knowledge-enabled-pill knowledge-enabled-pill--on">
                    {session.status}
                </span>
            </header>
            <div className="upload-progress-summary">
                <strong>{progressPercent}%</strong>
                <span>Processed {session.processed_files} of {session.total_files}</span>
                <span>Remaining {remaining}</span>
                <span>Current file {session.current_file ?? "-"}</span>
                <span>Started {formatTimestamp(session.started_at)}</span>
            </div>
            <div className="knowledge-source-actions">
                <button type="button" className="memory-row-action" onClick={onCancel} disabled={isMutating}>
                    Cancel
                </button>
                <button type="button" className="memory-row-action" onClick={onResume} disabled={isMutating}>
                    Resume
                </button>
            </div>
        </section>
    );
};
