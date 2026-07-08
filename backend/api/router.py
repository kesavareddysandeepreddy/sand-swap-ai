"""API router composition for SandSwap AI."""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.health import router as health_router
from backend.chat.api.chat_routes import router as chat_router

router = APIRouter()
router.include_router(health_router)
router.include_router(chat_router)
