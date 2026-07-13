"""FastAPI application entrypoint for SandSwap AI."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from backend.api.dependencies import register_runtime_dependencies
from backend.api.router import router as api_router
from backend.auth import CurrentUser
from backend.core.container.container import Container
from backend.core.lifecycle.lifecycle_manager import LifecycleManager
from backend.core.logging.logger import LoggerFactory
from backend.core.registry import registry

logger = LoggerFactory.get_logger("API")


class TokenValidationMiddleware(BaseHTTPMiddleware):
    """Attach request-scoped auth context from optional bearer JWT."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        token_service = app.state.container.resolve("token_service")
        auth_header = request.headers.get("Authorization", "")
        current_user = CurrentUser.anonymous()

        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
            if token:
                try:
                    claims = token_service.verify_access_token(token)
                    current_user = CurrentUser.authenticated(claims)
                except Exception as exc:  # noqa: BLE001
                    current_user = CurrentUser.anonymous(auth_error=str(exc))

        request.state.current_user = current_user
        return await call_next(request)


def _get_cors_origins() -> list[str]:
    """Return allowed origins for browser clients."""
    raw_origins = os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173",
    )
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize runtime services for the FastAPI application."""
    logger.info("Starting SandSwap AI runtime")
    container = Container()
    container.clear()
    registry.clear()

    register_runtime_dependencies(container)

    lifecycle_manager = LifecycleManager()
    app.state.container = container
    app.state.lifecycle_manager = lifecycle_manager

    await lifecycle_manager.startup()
    try:
        yield
    finally:
        logger.info("Stopping SandSwap AI runtime")
        for name in container.list():
            dependency = container.resolve(name)
            closer = getattr(dependency, "close", None)
            if callable(closer):
                try:
                    closer()
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to close dependency '%s'", name)
        await lifecycle_manager.shutdown()


app = FastAPI(
    title="SandSwap AI",
    version="0.1.0",
    description="Production-ready runtime for SandSwap AI",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TokenValidationMiddleware)

app.include_router(api_router)
