import type { ExecutionTraceSummary } from "../../types/api";
import { formatTimestamp } from "../../utils/date";

interface ExecutionSummaryProps {
    trace: ExecutionTraceSummary;
    isSelected: boolean;
    onSelect: (traceId: string) => void;
}

const toDuration = (value: number): string => `${Math.round(value)} ms`;

const deriveStatus = (trace: ExecutionTraceSummary): string => {
    if (!trace.completed_at) {
        return "running";
    }
    return "completed";
};

export const ExecutionSummary = ({
    trace,
    isSelected,
    onSelect,
}: ExecutionSummaryProps) => {
    const status = deriveStatus(trace);

    return (
        <button
            type="button"
            className={`execution-summary ${isSelected ? "execution-summary--selected" : ""}`}
            onClick={() => onSelect(trace.trace_id)}
        >
            <div className="execution-summary-grid">
                <span className="execution-summary-label">Worker</span>
                <span>{trace.worker_name}</span>

                <span className="execution-summary-label">Duration</span>
                <span>{toDuration(trace.total_duration_ms)}</span>

                <span className="execution-summary-label">Started</span>
                <span>{formatTimestamp(trace.started_at)}</span>

                <span className="execution-summary-label">Completed</span>
                <span>
                    {trace.completed_at ? formatTimestamp(trace.completed_at) : "In progress"}
                </span>

                <span className="execution-summary-label">Status</span>
                <span className={`execution-status execution-status--${status}`}>{status}</span>
            </div>
        </button>
    );
};
