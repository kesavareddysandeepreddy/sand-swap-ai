import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ExecutionTimeline } from "./ExecutionTimeline";

const recent = [
    {
        trace_id: "trace-1",
        worker_name: "universal_worker",
        request_id: "req-1",
        started_at: "2026-01-01T00:00:00Z",
        completed_at: "2026-01-01T00:00:01Z",
        total_duration_ms: 1000,
    },
];

const selectedTrace = {
    trace_id: "trace-1",
    worker_name: "universal_worker",
    request_id: "req-1",
    started_at: "2026-01-01T00:00:00Z",
    completed_at: "2026-01-01T00:00:01Z",
    total_duration_ms: 1000,
    metadata: {
        execution_state: "completed",
        retries: { "node:step-1": 0 },
        queue_duration_ms: { "node:step-1": 5 },
        execution_duration_ms: { "node:step-1": 9 },
        node_status: { "node:step-1": "completed" },
        checkpoint_state: { "node:step-1": "checkpointed" },
    },
    steps: [
        {
            id: "step-1",
            stage: "Planner",
            status: "completed",
            started_at: "2026-01-01T00:00:00Z",
            completed_at: "2026-01-01T00:00:00.5Z",
            duration_ms: 500,
            metadata: { phase: "planning" },
        },
    ],
};

describe("ExecutionTimeline", () => {
    it("renders from shared state and invokes callbacks", () => {
        const onTimelineToggle = vi.fn();
        const onPlanToggle = vi.fn();
        const onSelectTrace = vi.fn();

        render(
            <ExecutionTimeline
                recent={recent}
                selectedTrace={selectedTrace}
                isLoadingRecent={false}
                isLoadingTrace={false}
                recentError={null}
                traceError={null}
                hasLoadedRecent={true}
                isTimelineExpanded={true}
                onTimelineToggle={onTimelineToggle}
                isPlanExpanded={false}
                onPlanToggle={onPlanToggle}
                onSelectTrace={onSelectTrace}
            />
        );

        expect(screen.getByText("universal_worker")).toBeInTheDocument();
        expect(screen.getByText("Planner")).toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", { name: /Execution Timeline/i }));
        expect(onTimelineToggle).toHaveBeenCalledTimes(1);

        fireEvent.click(screen.getByRole("button", { name: /Execution Plan/i }));
        expect(onPlanToggle).toHaveBeenCalledTimes(1);

        fireEvent.click(screen.getByRole("button", { name: /Worker/i }));
        expect(onSelectTrace).toHaveBeenCalledTimes(1);
    });

    it("shows loading and empty shared-state messages", () => {
        render(
            <ExecutionTimeline
                recent={[]}
                selectedTrace={null}
                isLoadingRecent={true}
                isLoadingTrace={false}
                recentError={null}
                traceError={null}
                hasLoadedRecent={false}
                isTimelineExpanded={true}
                onTimelineToggle={() => undefined}
                isPlanExpanded={false}
                onPlanToggle={() => undefined}
                onSelectTrace={() => undefined}
            />
        );

        expect(screen.getByText("Loading execution traces...")).toBeInTheDocument();
    });
});
