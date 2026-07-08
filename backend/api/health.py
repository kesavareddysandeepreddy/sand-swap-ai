"""Health endpoint for the API runtime."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.api.dependencies import get_settings
from backend.config.settings import Settings

router = APIRouter()


class HealthResponse(BaseModel):
    """Response model for the health endpoint."""

    status: str
    service: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Return the current health payload for the runtime."""
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
    )
