import { useMemo } from "react";

import type {
    ExecutionState,
    ExecutionStep,
    ExecutionTraceDetail,
    TaskPlan,
    TaskPlanStep,
} from "../types/api";

export interface TaskPlanStepView {
    stepId: string;
    order: number;
    name: string;
    capability: string;
    dependency: string | null;
    status: "pending" | "running" | "completed";
    durationMs: number | null;
    retries: number;
    queueDurationMs: number;
    executionDurationMs: number;
    checkpointState: string;
}

export interface TaskPlanView {
    goal: string;
    complexity: string;
    estimatedCost: number;
    capabilities: string[];
    steps: TaskPlanStepView[];
    executionState: ExecutionState;
    currentStepId: string | null;
}

const EXECUTION_STAGE_TO_PLAN_STEP_INDEX: Record<string, number> = {
    Planner: 1,
    "Capability Selection": 2,
    "Workflow Execution": 3,
    "Final Response": 4,
    "Worker Finish": 5,
};

const isObjectRecord = (value: unknown): value is Record<string, unknown> =>
    typeof value === "object" && value !== null;

const asNumber = (value: unknown, fallback = 0): number =>
    typeof value === "number" ? value : fallback;

const asString = (value: unknown, fallback = "pending"): string =>
    typeof value === "string" ? value : fallback;

const parsePlan = (value: unknown): TaskPlan | null => {
    if (!isObjectRecord(value)) {
        return null;
    }
    if (!Array.isArray(value.steps)) {
        return null;
    }
    const goal = isObjectRecord(value.goal) ? value.goal : { original_request: "" };
    const inferredCapabilities = Array.isArray(value.inferred_capabilities)
        ? value.inferred_capabilities.filter(
            (item): item is string => typeof item === "string"
        )
        : [];

    const steps: TaskPlanStep[] = value.steps
        .filter((entry): entry is Record<string, unknown> => isObjectRecord(entry))
        .map((entry) => ({
            step_id: typeof entry.step_id === "string" ? entry.step_id : "",
            order: typeof entry.order === "number" ? entry.order : 0,
            title: typeof entry.title === "string" ? entry.title : "",
            action: typeof entry.action === "string" ? entry.action : "",
            target: typeof entry.target === "string" ? entry.target : "",
            capabilities: Array.isArray(entry.capabilities)
                ? entry.capabilities.filter(
                    (item): item is string => typeof item === "string"
                )
                : [],
            estimated_cost:
                typeof entry.estimated_cost === "number" ? entry.estimated_cost : 0,
            complexity: typeof entry.complexity === "string" ? entry.complexity : "low",
        }))
        .filter((step) => step.step_id && step.order > 0);

    const dependencies = Array.isArray(value.dependencies)
        ? value.dependencies
            .filter((entry): entry is Record<string, unknown> => isObjectRecord(entry))
            .map((entry) => ({
                predecessor_step_id:
                    typeof entry.predecessor_step_id === "string"
                        ? entry.predecessor_step_id
                        : "",
                successor_step_id:
                    typeof entry.successor_step_id === "string"
                        ? entry.successor_step_id
                        : "",
                reason: typeof entry.reason === "string" ? entry.reason : "",
            }))
        : [];

    return {
        goal: {
            original_request:
                typeof goal.original_request === "string" ? goal.original_request : "",
            actions: Array.isArray(goal.actions)
                ? goal.actions.filter((item): item is string => typeof item === "string")
                : [],
            targets: Array.isArray(goal.targets)
                ? goal.targets.filter((item): item is string => typeof item === "string")
                : [],
            constraints: Array.isArray(goal.constraints)
                ? goal.constraints.filter((item): item is string => typeof item === "string")
                : [],
            expected_outputs: Array.isArray(goal.expected_outputs)
                ? goal.expected_outputs.filter(
                    (item): item is string => typeof item === "string"
                )
                : [],
        },
        steps,
        dependencies,
        inferred_capabilities: inferredCapabilities,
        estimated_total_cost:
            typeof value.estimated_total_cost === "number" ? value.estimated_total_cost : 0,
        overall_complexity:
            typeof value.overall_complexity === "string" ? value.overall_complexity : "low",
    };
};

const inferExecutionState = (
    metadata: Record<string, unknown>
): ExecutionState => {
    const value = metadata.execution_state;
    if (
        value === "planning"
        || value === "executing"
        || value === "completed"
        || value === "failed"
    ) {
        return value;
    }
    return "completed";
};

const computeCurrentStepId = (
    steps: TaskPlanStepView[],
    executionState: ExecutionState,
    traceSteps: ExecutionStep[]
): string | null => {
    if (executionState === "completed" || executionState === "failed") {
        return null;
    }
    if (steps.length === 0) {
        return null;
    }

    if (executionState === "planning") {
        return steps[0].stepId;
    }

    const running = traceSteps.find((step) => step.status === "running");
    if (!running) {
        return steps[0].stepId;
    }

    const mappedOrder = EXECUTION_STAGE_TO_PLAN_STEP_INDEX[running.stage];
    if (!mappedOrder) {
        return steps[0].stepId;
    }

    const mapped = steps.find((step) => step.order === mappedOrder);
    return mapped?.stepId ?? steps[0].stepId;
};

export const useTaskPlan = (
    trace: ExecutionTraceDetail | null
): {
    plan: TaskPlanView | null;
    isLoading: boolean;
} => {
    return useMemo(() => {
        if (!trace) {
            return { plan: null, isLoading: true };
        }

        const metadata = trace.metadata ?? {};
        const parsedPlan = parsePlan(metadata.task_plan);
        if (!parsedPlan) {
            return { plan: null, isLoading: false };
        }

        const dependencyByStep = new Map<string, string>();
        for (const edge of parsedPlan.dependencies) {
            if (edge.successor_step_id && edge.predecessor_step_id) {
                dependencyByStep.set(edge.successor_step_id, edge.predecessor_step_id);
            }
        }

        const executionState = inferExecutionState(metadata);
        const retries = isObjectRecord(metadata.retries) ? metadata.retries : {};
        const queueDuration = isObjectRecord(metadata.queue_duration_ms)
            ? metadata.queue_duration_ms
            : {};
        const executionDuration = isObjectRecord(metadata.execution_duration_ms)
            ? metadata.execution_duration_ms
            : {};
        const checkpointState = isObjectRecord(metadata.checkpoint_state)
            ? metadata.checkpoint_state
            : {};
        const nodeStatus = isObjectRecord(metadata.node_status)
            ? metadata.node_status
            : {};
        const stepViews: TaskPlanStepView[] = parsedPlan.steps.map((step) => {
            const nodeKey = `node:${step.step_id}`;
            return {
                stepId: step.step_id,
                order: step.order,
                name: step.title || `${step.action} ${step.target}`,
                capability: step.capabilities[0] ?? "workflow",
                dependency: dependencyByStep.get(step.step_id) ?? null,
                status:
                    nodeStatus[`node:${step.step_id}`] === "running"
                        ? "running"
                        : nodeStatus[`node:${step.step_id}`] === "completed"
                            ? "completed"
                            : executionState === "completed"
                                ? "completed"
                                : "pending",
                durationMs: null,
                retries: asNumber(retries[nodeKey]),
                queueDurationMs: asNumber(queueDuration[nodeKey]),
                executionDurationMs: asNumber(executionDuration[nodeKey]),
                checkpointState: asString(checkpointState[nodeKey]),
            };
        });

        if (executionState === "planning") {
            if (stepViews[0]) {
                stepViews[0].status = "running";
            }
        }

        const currentStepId = computeCurrentStepId(stepViews, executionState, trace.steps);
        if (currentStepId) {
            const currentStep = stepViews.find((step) => step.stepId === currentStepId);
            if (currentStep) {
                currentStep.status = "running";
            }
            if (executionState === "executing") {
                for (const step of stepViews) {
                    if (step.order < (currentStep?.order ?? 0)) {
                        step.status = "completed";
                    }
                }
            }
        }

        if (executionState === "completed") {
            for (const step of stepViews) {
                step.status = "completed";
            }
        }

        const workflowExecution = trace.steps.find(
            (step) => step.stage === "Workflow Execution"
        );
        if (workflowExecution) {
            const executionStep = stepViews.find((step) => step.order === 3);
            if (executionStep) {
                executionStep.durationMs = workflowExecution.duration_ms;
            }
        }

        const capabilitiesSource =
            Array.isArray(metadata.inferred_capabilities)
                ? metadata.inferred_capabilities.filter(
                    (item): item is string => typeof item === "string"
                )
                : parsedPlan.inferred_capabilities;

        return {
            plan: {
                goal: parsedPlan.goal.original_request,
                complexity:
                    typeof metadata.complexity === "string"
                        ? metadata.complexity
                        : parsedPlan.overall_complexity,
                estimatedCost:
                    typeof metadata.estimated_cost === "number"
                        ? metadata.estimated_cost
                        : parsedPlan.estimated_total_cost,
                capabilities: capabilitiesSource,
                steps: stepViews,
                executionState,
                currentStepId,
            },
            isLoading: false,
        };
    }, [trace]);
};
