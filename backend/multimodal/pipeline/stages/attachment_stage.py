"""Attachment collection stage for multimodal pipeline."""

from __future__ import annotations

from pathlib import Path

from backend.core.logging.logger import LoggerFactory
from backend.knowledge.knowledge_service import KnowledgeService
from backend.multimodal.attachment_router import AttachmentRouter
from backend.multimodal.attachment_types import AttachmentType
from backend.multimodal.models import AttachmentMetadata
from backend.multimodal.pipeline.processor import MultimodalPipelineContext


class AttachmentStage:
    """Collect and normalize image attachments from uploaded documents."""

    def __init__(
        self,
        attachment_router: AttachmentRouter,
        knowledge_service: KnowledgeService,
    ) -> None:
        self.attachment_router = attachment_router
        self.knowledge_service = knowledge_service
        self.logger = LoggerFactory.get_logger("AttachmentStage")

    def process(self, context: MultimodalPipelineContext) -> MultimodalPipelineContext:
        attachments: list[AttachmentMetadata] = []
        knowledge_ids = set(context.conversation.knowledge_object_ids)
        knowledge_objects = list(context.knowledge_objects)

        for document in context.documents:
            workspace_id = str(document.metadata.get("workspace_id") or "default")
            project_id = str(document.metadata.get("project") or "default")
            knowledge_object = self.knowledge_service.ensure_from_document(
                document=document,
                workspace_id=workspace_id,
                project_id=project_id,
                conversation_id=context.conversation.id,
            )

            if knowledge_object.id not in knowledge_ids:
                context.conversation.knowledge_object_ids.append(knowledge_object.id)
                knowledge_ids.add(knowledge_object.id)

            knowledge_objects.append(knowledge_object)

            mime_type = self.attachment_router.detect_mime_type(document.name)
            attachment_type = self.attachment_router.classify_attachment(
                filename=document.name,
                mime_type=mime_type,
            )
            if attachment_type != AttachmentType.IMAGE:
                continue

            attachment = AttachmentMetadata(
                filename=document.name,
                mime_type=mime_type,
                extension=Path(document.name).suffix.lower(),
                size=document.size_bytes,
                width=(
                    document.metadata.get("width")
                    if isinstance(document.metadata.get("width"), int)
                    else None
                ),
                height=(
                    document.metadata.get("height")
                    if isinstance(document.metadata.get("height"), int)
                    else None
                ),
                metadata={
                    "path": document.stored_path,
                    "document_id": document.id,
                    "sha256": document.sha256,
                    "workspace_id": document.metadata.get("workspace_id"),
                    "project": document.metadata.get("project"),
                    "knowledge_object_id": knowledge_object.id,
                },
            )
            attachments.append(attachment)
            self.logger.debug(
                "Image uploaded document_id=%s name=%s", document.id, document.name
            )

        context.knowledge_objects = knowledge_objects
        context.attachments = attachments
        context.metadata["attachment_count"] = len(attachments)
        context.metadata["knowledge_object_count"] = len(
            context.conversation.knowledge_object_ids
        )
        return context
