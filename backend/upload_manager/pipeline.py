"""Deterministic upload processing pipeline."""

from __future__ import annotations

from backend.upload_manager.models import UploadJob, UploadStage


class UploadPipeline:
    """Compute upload pipeline stages without executing external work."""

    def build(self, job: UploadJob) -> list[UploadStage]:
        stages = [
            UploadStage.VALIDATION,
            UploadStage.PARSER_SELECTION,
            UploadStage.OCR_REQUIRED,
            UploadStage.CHUNK_REQUIRED,
            UploadStage.EMBEDDING_REQUIRED,
            UploadStage.KNOWLEDGE_GRAPH_REQUIRED,
            UploadStage.FINISHED,
        ]
        return stages

    def annotate(self, job: UploadJob) -> dict[str, object]:
        return {
            "job_id": job.id,
            "file_name": job.file_name,
            "parser": job.parser,
            "stages": [stage.value for stage in self.build(job)],
        }
