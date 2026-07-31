"""Read-only execution timeline API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from backend.api.dependencies import get_execution_recorder
from backend.execution.recorder import ExecutionRecorder

router = APIRouter(prefix="/api/execution", tags=["execution"])


class ExecutionStepResponse(BaseModel):
    """Serialized execution step payload."""

    id: str
    stage: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: float
    metadata: dict[str, Any]


class ExecutionTraceSummaryResponse(BaseModel):
    """Summary response model for recent execution traces."""

    trace_id: str
    worker_name: str
    request_id: str | None
    started_at: datetime
    completed_at: datetime | None
    total_duration_ms: float


class ExecutionTraceDetailResponse(ExecutionTraceSummaryResponse):
    """Detailed execution trace response including all recorded steps."""

    metadata: dict[str, Any]
    steps: list[ExecutionStepResponse]


class ExecutionHealthResponse(BaseModel):
    """Health payload for execution recorder API."""

    traces: int
    recorder_status: str


def _serialize_step(step: Any) -> ExecutionStepResponse:
    return ExecutionStepResponse(
        id=step.id,
        stage=step.stage,
        status=step.status,
        started_at=step.started_at,
        completed_at=step.completed_at,
        duration_ms=step.duration_ms,
        metadata=step.metadata,
    )


def _serialize_trace_summary(trace: Any) -> ExecutionTraceSummaryResponse:
    return ExecutionTraceSummaryResponse(
        trace_id=trace.trace_id,
        worker_name=trace.worker_name,
        request_id=trace.request_id,
        started_at=trace.started_at,
        completed_at=trace.completed_at,
        total_duration_ms=trace.total_duration_ms,
    )


@router.get("/recent", response_model=list[ExecutionTraceSummaryResponse])
def list_recent_traces(
    limit: int = Query(default=20, ge=1, le=200),
    recorder: ExecutionRecorder = Depends(get_execution_recorder),
) -> list[ExecutionTraceSummaryResponse]:
    """Return the most recent execution traces."""
    traces = recorder.list_recent(limit=limit)
    return [_serialize_trace_summary(trace) for trace in traces]


@router.get("/trace/{trace_id}", response_model=ExecutionTraceDetailResponse)
def get_trace(
    trace_id: str,
    recorder: ExecutionRecorder = Depends(get_execution_recorder),
) -> ExecutionTraceDetailResponse:
    """Return one full execution trace by identifier."""
    trace = recorder.get_trace(trace_id)
    if trace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution trace not found",
        )

    return ExecutionTraceDetailResponse(
        trace_id=trace.trace_id,
        worker_name=trace.worker_name,
        request_id=trace.request_id,
        started_at=trace.started_at,
        completed_at=trace.completed_at,
        total_duration_ms=trace.total_duration_ms,
        metadata=trace.metadata,
        steps=[_serialize_step(step) for step in trace.steps],
    )


@router.get("/health", response_model=ExecutionHealthResponse)
def execution_health(
    recorder: ExecutionRecorder = Depends(get_execution_recorder),
) -> ExecutionHealthResponse:
    """Return recorder health metadata for execution traces."""
    return ExecutionHealthResponse(
        traces=len(recorder.list_recent(limit=10_000)),
        recorder_status="ok",
    )
