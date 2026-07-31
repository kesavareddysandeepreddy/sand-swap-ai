import type { TaskPlanStepView } from "../../hooks/useTaskPlan";

interface PlanStepProps {
    step: TaskPlanStepView;
    isCurrent: boolean;
}

const formatDuration = (durationMs: number | null): string => {
    if (durationMs === null) {
        return "-";
    }
    return `${Math.round(durationMs)} ms`;
};

export const PlanStep = ({ step, isCurrent }: PlanStepProps) => {
    return (
        <li
            className={`plan-step ${isCurrent ? "plan-step--current" : ""}`}
            data-current-step={isCurrent ? "true" : "false"}
        >
            <div className="plan-step-main">
                <strong>{step.name}</strong>
                <span className={`execution-status execution-status--${step.status}`}>
                    {step.status}
                </span>
            </div>
            <div className="plan-step-meta">
                <span>Capability: {step.capability}</span>
                <span>Dependency: {step.dependency ?? "none"}</span>
                <span>Duration: {formatDuration(step.durationMs)}</span>
                <span>Retries: {step.retries}</span>
                <span>Queue: {Math.round(step.queueDurationMs)} ms</span>
                <span>Exec: {Math.round(step.executionDurationMs)} ms</span>
                <span>Checkpoint: {step.checkpointState}</span>
            </div>
        </li>
    );
};
