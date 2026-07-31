"""Upload manager API routes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.dependencies import UploadManagerServiceDependency
from backend.upload_manager.models import UploadJob, UploadSession

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


class UploadSessionCreateRequest(BaseModel):
    project_id: str = Field(..., min_length=1)
    source_id: str = Field(..., min_length=1)
    total_files: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UploadJobEnqueueRequest(BaseModel):
    files: list[dict[str, Any]] = Field(default_factory=list)


class UploadSessionResponse(BaseModel):
    id: str
    project_id: str
    source_id: str
    status: str
    total_files: int
    processed_files: int
    failed_files: int
    skipped_files: int
    started_at: datetime
    completed_at: datetime | None
    current_file: str | None
    metadata: dict[str, Any]


class UploadJobResponse(BaseModel):
    id: str
    session_id: str
    file_name: str
    file_size: int
    mime_type: str
    parser: str
    status: str
    chunks_created: int
    embeddings_created: int
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None


class UploadHealthResponse(BaseModel):
    status: str
    sessions: int
    queued_jobs: int


class UploadProgressResponse(BaseModel):
    session_id: str
    status: str
    total_files: int
    processed_files: int
    remaining_files: int
    failed_files: int
    skipped_files: int
    progress_percent: float
    current_file: str | None
    eta: str | None


class UploadSummaryResponse(BaseModel):
    session_id: str
    status: str
    processed_files: int
    remaining_files: int
    failed_files: int
    skipped_files: int
    current_file: str | None


class UploadCancelResponse(BaseModel):
    cancelled: bool


class UploadResumeResponse(BaseModel):
    resumed: bool


def _serialize_session(session: UploadSession) -> UploadSessionResponse:
    return UploadSessionResponse(
        id=session.id,
        project_id=session.project_id,
        source_id=session.source_id,
        status=session.status,
        total_files=session.total_files,
        processed_files=session.processed_files,
        failed_files=session.failed_files,
        skipped_files=session.skipped_files,
        started_at=session.started_at,
        completed_at=session.completed_at,
        current_file=session.current_file,
        metadata=session.metadata,
    )


def _serialize_job(job: UploadJob) -> UploadJobResponse:
    return UploadJobResponse(
        id=job.id,
        session_id=job.session_id,
        file_name=job.file_name,
        file_size=job.file_size,
        mime_type=job.mime_type,
        parser=job.parser,
        status=job.status,
        chunks_created=job.chunks_created,
        embeddings_created=job.embeddings_created,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error=job.error,
    )


@router.post(
    "/session",
    response_model=UploadSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_session(
    payload: UploadSessionCreateRequest,
    service: UploadManagerServiceDependency,
) -> UploadSessionResponse:
    session = service.create_session(
        project_id=payload.project_id,
        source_id=payload.source_id,
        total_files=payload.total_files,
        metadata=payload.metadata,
    )
    return _serialize_session(session)


@router.get("/session/{session_id}", response_model=UploadSessionResponse)
def get_session(
    session_id: str,
    service: UploadManagerServiceDependency,
) -> UploadSessionResponse:
    session = service.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Upload session not found"
        )
    return _serialize_session(session)


@router.get("/session/{session_id}/jobs", response_model=list[UploadJobResponse])
def get_jobs(
    session_id: str,
    service: UploadManagerServiceDependency,
) -> list[UploadJobResponse]:
    return [_serialize_job(job) for job in service.get_jobs(session_id)]


@router.post("/session/{session_id}/enqueue", response_model=list[UploadJobResponse])
def enqueue_jobs(
    session_id: str,
    payload: UploadJobEnqueueRequest,
    service: UploadManagerServiceDependency,
) -> list[UploadJobResponse]:
    try:
        jobs = service.enqueue_jobs(session_id, payload.files)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Upload session not found"
        ) from exc
    return [_serialize_job(job) for job in jobs]


@router.post("/session/{session_id}/cancel", response_model=UploadCancelResponse)
def cancel_session(
    session_id: str,
    service: UploadManagerServiceDependency,
) -> UploadCancelResponse:
    try:
        _ = service.cancel_session(session_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Upload session not found"
        ) from exc
    return UploadCancelResponse(cancelled=True)


@router.post("/session/{session_id}/resume", response_model=UploadResumeResponse)
def resume_session(
    session_id: str,
    service: UploadManagerServiceDependency,
) -> UploadResumeResponse:
    try:
        _ = service.resume_session(session_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Upload session not found"
        ) from exc
    return UploadResumeResponse(resumed=True)


@router.get("/session/{session_id}/progress", response_model=UploadProgressResponse)
def get_progress(
    session_id: str,
    service: UploadManagerServiceDependency,
) -> UploadProgressResponse:
    try:
        payload = service.progress(session_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Upload session not found"
        ) from exc
    return UploadProgressResponse(**payload)


@router.get("/session/{session_id}/summary", response_model=UploadSummaryResponse)
def get_summary(
    session_id: str,
    service: UploadManagerServiceDependency,
) -> UploadSummaryResponse:
    try:
        payload = service.summary(session_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Upload session not found"
        ) from exc
    return UploadSummaryResponse(**payload)


@router.get("/health", response_model=UploadHealthResponse)
def health(
    service: UploadManagerServiceDependency,
) -> UploadHealthResponse:
    return UploadHealthResponse(**service.health())
