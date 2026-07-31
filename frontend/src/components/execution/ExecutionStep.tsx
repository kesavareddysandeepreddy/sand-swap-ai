import { useState } from "react";

import type { ExecutionStep as ExecutionStepModel } from "../../types/api";

interface ExecutionStepProps {
    step: ExecutionStepModel;
}

const formatDuration = (durationMs: number): string => `${Math.round(durationMs)} ms`;

export const ExecutionStep = ({ step }: ExecutionStepProps) => {
    const [showMetadata, setShowMetadata] = useState(false);
    const hasMetadata = Object.keys(step.metadata).length > 0;

    return (
        <article className="execution-step">
            <header className="execution-step-header">
                <div className="execution-step-title-wrap">
                    <span className="execution-step-check" aria-hidden="true">✓</span>
                    <strong>{step.stage}</strong>
                </div>
                <div className="execution-step-meta">
                    <span className={`execution-status execution-status--${step.status}`}>
                        {step.status}
                    </span>
                    <span>{formatDuration(step.duration_ms)}</span>
                </div>
            </header>
            {hasMetadata ? (
                <div className="execution-step-metadata">
                    <button
                        type="button"
                        className="execution-step-toggle"
                        onClick={() => setShowMetadata((current) => !current)}
                    >
                        {showMetadata ? "Hide metadata" : "Show metadata"}
                    </button>
                    {showMetadata ? (
                        <pre>{JSON.stringify(step.metadata, null, 2)}</pre>
                    ) : null}
                </div>
            ) : null}
        </article>
    );
};
