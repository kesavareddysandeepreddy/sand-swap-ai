import { useTaskPlan } from "../../hooks/useTaskPlan";
import type { ExecutionTraceDetail, ExecutionTraceSummary } from "../../types/api";
import { ExecutionPlan } from "../planner/ExecutionPlan";
import { ExecutionStep } from "./ExecutionStep";
import { ExecutionSummary } from "./ExecutionSummary";

interface ExecutionTimelineProps {
    recent: ExecutionTraceSummary[];
    selectedTrace: ExecutionTraceDetail | null;
    isLoadingRecent: boolean;
    isLoadingTrace: boolean;
    recentError: string | null;
    traceError: string | null;
    hasLoadedRecent: boolean;
    isTimelineExpanded: boolean;
    onTimelineToggle: () => void;
    isPlanExpanded: boolean;
    onPlanToggle: () => void;
    onSelectTrace: (trace: ExecutionTraceSummary) => void;
}

export const ExecutionTimeline = ({
    recent,
    selectedTrace,
    isLoadingRecent,
    isLoadingTrace,
    recentError,
    traceError,
    hasLoadedRecent,
    isTimelineExpanded,
    onTimelineToggle,
    isPlanExpanded,
    onPlanToggle,
    onSelectTrace,
}: ExecutionTimelineProps) => {
    const { plan, isLoading: isLoadingPlan } = useTaskPlan(selectedTrace);
    const executionState =
        typeof selectedTrace?.metadata?.execution_state === "string"
            ? selectedTrace.metadata.execution_state
            : "completed";

    return (
        <section className="execution-panel" aria-label="Execution timeline panel">
            <ExecutionPlan
                plan={plan}
                isLoading={isLoadingPlan}
                isExpanded={isPlanExpanded}
                onToggle={onPlanToggle}
            />
            <button
                type="button"
                className="execution-panel-toggle"
                onClick={onTimelineToggle}
                aria-expanded={isTimelineExpanded}
                aria-controls="execution-timeline-content"
            >
                <span>Execution Timeline</span>
                <span>{isTimelineExpanded ? "Hide" : "Show"}</span>
            </button>

            {isTimelineExpanded ? (
                <div id="execution-timeline-content" className="execution-panel-content">
                    <div className="execution-phases" aria-label="Execution phases">
                        <span className={`execution-status ${executionState === "planning" ? "execution-status--running" : ""}`}>
                            Planning
                        </span>
                        <span className={`execution-status ${executionState === "executing" ? "execution-status--running" : ""}`}>
                            Executing
                        </span>
                        <span className={`execution-status ${executionState === "completed" ? "execution-status--completed" : ""}`}>
                            Completed
                        </span>
                    </div>
                    {isLoadingRecent ? <p className="execution-state">Loading execution traces...</p> : null}

                    {!isLoadingRecent && recentError ? (
                        <p className="execution-state execution-state--error" role="alert">
                            {recentError}
                        </p>
                    ) : null}

                    {!hasLoadedRecent ? (
                        <p className="execution-state">Open a panel to load execution traces.</p>
                    ) : null}

                    {hasLoadedRecent && !isLoadingRecent && !recentError && recent.length === 0 ? (
                        <p className="execution-state">No execution traces available yet.</p>
                    ) : null}

                    {hasLoadedRecent && !isLoadingRecent && !recentError && recent.length > 0 ? (
                        <div className="execution-panel-grid">
                            <div className="execution-summary-list">
                                {recent.map((trace) => (
                                    <ExecutionSummary
                                        key={trace.trace_id}
                                        trace={trace}
                                        isSelected={selectedTrace?.trace_id === trace.trace_id}
                                        onSelect={(traceId) => {
                                            const selected = recent.find((item) => item.trace_id === traceId);
                                            if (selected) {
                                                onSelectTrace(selected);
                                            }
                                        }}
                                    />
                                ))}
                            </div>
                            <div className="execution-steps-column">
                                {isLoadingTrace ? (
                                    <p className="execution-state">Loading trace details...</p>
                                ) : null}
                                {!isLoadingTrace && traceError ? (
                                    <p className="execution-state execution-state--error" role="alert">
                                        {traceError}
                                    </p>
                                ) : null}
                                {!isLoadingTrace && !traceError && selectedTrace ? (
                                    <div className="execution-step-list">
                                        {selectedTrace.steps.map((step) => (
                                            <ExecutionStep key={step.id} step={step} />
                                        ))}
                                    </div>
                                ) : null}
                            </div>
                        </div>
                    ) : null}
                </div>
            ) : null}
        </section>
    );
};
