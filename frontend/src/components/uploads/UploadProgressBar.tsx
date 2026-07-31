interface UploadProgressBarProps {
    progressPercent: number;
    remaining: number;
    eta: string | null;
}

export const UploadProgressBar = ({ progressPercent, remaining, eta }: UploadProgressBarProps) => {
    return (
        <section className="upload-progress-bar">
            <div className="upload-progress-track" aria-hidden="true">
                <div className="upload-progress-fill" style={{ width: `${Math.min(100, Math.max(0, progressPercent))}%` }} />
            </div>
            <div className="upload-progress-meta">
                <span>Progress {progressPercent}%</span>
                <span>Remaining {remaining}</span>
                <span>ETA {eta ?? "calculating..."}</span>
            </div>
        </section>
    );
};
