import { CapabilityBadge } from "./CapabilityBadge";
import { PlanStep } from "./PlanStep";

import type { TaskPlanView } from "../../hooks/useTaskPlan";

interface ExecutionPlanProps {
    plan: TaskPlanView | null;
    isLoading: boolean;
    isExpanded: boolean;
    onToggle: () => void;
}

const formatCost = (value: number): string => `$${value.toFixed(2)}`;

export const ExecutionPlan = ({
    plan,
    isLoading,
    isExpanded,
    onToggle,
}: ExecutionPlanProps) => {
    return (
        <section className="execution-plan" aria-label="Execution plan">
            <button
                type="button"
                className="execution-panel-toggle"
                onClick={onToggle}
                aria-expanded={isExpanded}
                aria-controls="execution-plan-content"
            >
                <span>Execution Plan</span>
                <span>{isExpanded ? "Hide" : "Show"}</span>
            </button>

            {isExpanded ? (
                <div id="execution-plan-content" className="execution-panel-content">
                    {isLoading ? (
                        <p className="execution-state">Loading execution plan...</p>
                    ) : null}

                    {!isLoading && !plan ? (
                        <p className="execution-state">No execution plan available yet.</p>
                    ) : null}

                    {!isLoading && plan ? (
                        <div className="execution-plan-content-grid">
                            <div className="execution-plan-facts">
                                <p><strong>Goal</strong>: {plan.goal}</p>
                                <p><strong>Estimated Complexity</strong>: {plan.complexity}</p>
                                <p><strong>Estimated Cost</strong>: {formatCost(plan.estimatedCost)}</p>
                            </div>
                            <div>
                                <p className="execution-plan-subheading">Capabilities</p>
                                <div className="execution-plan-badges">
                                    {plan.capabilities.map((capability) => (
                                        <CapabilityBadge
                                            key={capability}
                                            capability={capability}
                                        />
                                    ))}
                                </div>
                            </div>
                            <div>
                                <p className="execution-plan-subheading">Ordered Steps</p>
                                <ol className="execution-plan-steps">
                                    {plan.steps.map((step) => (
                                        <PlanStep
                                            key={step.stepId}
                                            step={step}
                                            isCurrent={plan.currentStepId === step.stepId}
                                        />
                                    ))}
                                </ol>
                            </div>
                        </div>
                    ) : null}
                </div>
            ) : null}
        </section>
    );
};
