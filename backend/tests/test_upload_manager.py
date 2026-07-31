from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.upload_manager.models import UploadJob, UploadSession, UploadStage
from backend.upload_manager.pipeline import UploadPipeline
from backend.upload_manager.progress import UploadProgressService
from backend.upload_manager.queue import UploadQueue
from backend.upload_manager.repository import UploadRepository
from backend.upload_manager.service import UploadManagerService


@pytest.fixture
def runtime_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "upload-memory.db"))
    monkeypatch.setenv("RAG_DB_PATH", str(tmp_path / "upload-rag.db"))
    monkeypatch.setenv("ENTERPRISE_DB_PATH", str(tmp_path / "upload-enterprise.db"))
    with TestClient(app) as client:
        yield client


def test_repository_session_and_job_lifecycle() -> None:
    repository = UploadRepository()
    session = repository.create_session(
        UploadSession(project_id="project-1", source_id="source-1")
    )
    assert repository.get_session(session.id) is not None

    updated_session = session
    updated_session.status = "queued"
    assert repository.update_session(updated_session).status == "queued"

    job = repository.create_job(
        UploadJob(
            session_id=session.id,
            file_name="alpha.txt",
            file_size=12,
            mime_type="text/plain",
            parser="auto",
        )
    )
    assert len(repository.list_jobs(session.id)) == 1

    job.status = "processing"
    assert repository.update_job(job).status == "processing"


def test_queue_fifo_cancel_resume() -> None:
    queue = UploadQueue()
    job_one = UploadJob(
        session_id="session-1",
        file_name="one.txt",
        file_size=1,
        mime_type="text/plain",
        parser="auto",
    )
    job_two = UploadJob(
        session_id="session-1",
        file_name="two.txt",
        file_size=1,
        mime_type="text/plain",
        parser="auto",
    )
    queue.enqueue(job_one)
    queue.enqueue(job_two)
    queue.cancel(job_one.id)
    assert queue.dequeue() == job_two
    assert queue.resume(job_one.id) is True


def test_pipeline_builds_deterministic_stages() -> None:
    pipeline = UploadPipeline()
    job = UploadJob(
        session_id="session-1",
        file_name="one.txt",
        file_size=1,
        mime_type="text/plain",
        parser="auto",
    )
    stages = pipeline.build(job)
    assert stages[0] == UploadStage.VALIDATION
    assert stages[-1] == UploadStage.FINISHED
    assert pipeline.annotate(job)["stages"][-1] == "Finished"


def test_progress_service_summary_and_eta() -> None:
    repository = UploadRepository()
    session = repository.create_session(
        UploadSession(
            project_id="project-1",
            source_id="source-1",
            total_files=4,
            processed_files=2,
        )
    )
    progress = UploadProgressService(repository)
    payload = progress.get_progress(session.id)
    assert payload["remaining_files"] == 2
    assert payload["progress_percent"] == 50.0
    assert progress.get_summary(session.id)["processed_files"] == 2


def test_service_session_enqueue_cancel_resume_and_health() -> None:
    repository = UploadRepository()
    queue = UploadQueue()
    pipeline = UploadPipeline()
    service = UploadManagerService(
        repository=repository, queue=queue, pipeline=pipeline
    )
    session = service.create_session(project_id="project-1", source_id="source-1")
    jobs = service.enqueue_jobs(
        session.id,
        [
            {
                "file_name": "alpha.txt",
                "file_size": 10,
                "mime_type": "text/plain",
                "parser": "auto",
            },
            {
                "file_name": "beta.txt",
                "file_size": 20,
                "mime_type": "text/plain",
                "parser": "auto",
            },
        ],
    )
    assert len(jobs) == 2
    assert service.cancel_session(session.id).status == "cancelled"
    assert service.resume_session(session.id).status == "queued"
    assert service.health()["status"] == "ok"


def test_upload_api_session_jobs_progress_and_health(
    runtime_client: TestClient,
) -> None:
    create_response = runtime_client.post(
        "/api/uploads/session",
        json={
            "project_id": "project-1",
            "source_id": "source-1",
            "total_files": 0,
            "metadata": {"origin": "ui"},
        },
    )
    assert create_response.status_code == 201
    session_id = create_response.json()["id"]

    enqueue_response = runtime_client.post(
        f"/api/uploads/session/{session_id}/enqueue",
        json={
            "files": [
                {
                    "file_name": "alpha.txt",
                    "file_size": 10,
                    "mime_type": "text/plain",
                    "parser": "auto",
                },
                {
                    "file_name": "beta.txt",
                    "file_size": 20,
                    "mime_type": "text/plain",
                    "parser": "auto",
                },
            ]
        },
    )
    assert enqueue_response.status_code == 200
    assert len(enqueue_response.json()) == 2

    get_session = runtime_client.get(f"/api/uploads/session/{session_id}")
    assert get_session.status_code == 200
    assert get_session.json()["total_files"] == 2

    get_jobs = runtime_client.get(f"/api/uploads/session/{session_id}/jobs")
    assert get_jobs.status_code == 200
    assert len(get_jobs.json()) == 2

    progress = runtime_client.get(f"/api/uploads/session/{session_id}/progress")
    assert progress.status_code == 200
    assert progress.json()["remaining_files"] == 2

    summary = runtime_client.get(f"/api/uploads/session/{session_id}/summary")
    assert summary.status_code == 200
    assert summary.json()["processed_files"] == 0

    cancel = runtime_client.post(f"/api/uploads/session/{session_id}/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["cancelled"] is True

    resume = runtime_client.post(f"/api/uploads/session/{session_id}/resume")
    assert resume.status_code == 200
    assert resume.json()["resumed"] is True

    health = runtime_client.get("/api/uploads/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
