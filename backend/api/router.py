"""API router composition for SandSwap AI."""

from __future__ import annotations

from fastapi import APIRouter

from backend.agent_orchestration.api import router as workflow_orchestration_router
from backend.agent_studio.api import router as agent_studio_router
from backend.api.auth import router as auth_router
from backend.api.execution import router as execution_router
from backend.api.health import router as health_router
from backend.api.knowledge_sources import router as knowledge_sources_router
from backend.api.uploads import router as uploads_router
from backend.chat.api.chat_routes import router as chat_router
from backend.memory.api.memory_routes import router as memory_router
from backend.rag.api.document_routes import router as document_router

router = APIRouter()

router.include_router(workflow_orchestration_router)
router.include_router(agent_studio_router)
router.include_router(auth_router)
router.include_router(health_router)
router.include_router(execution_router)
router.include_router(knowledge_sources_router)
router.include_router(uploads_router)
router.include_router(chat_router)
router.include_router(memory_router)
router.include_router(document_router)
