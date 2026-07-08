"""FastAPI application entrypoint for SandSwap AI."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from backend.api.dependencies import register_runtime_dependencies
from backend.api.router import router as api_router
from backend.core.container.container import Container
from backend.core.lifecycle.lifecycle_manager import LifecycleManager
from backend.core.logging.logger import LoggerFactory
from backend.core.registry import registry

logger = LoggerFactory.get_logger("API")


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
        await lifecycle_manager.shutdown()


app = FastAPI(
    title="SandSwap AI",
    version="0.1.0",
    description="Production-ready runtime for SandSwap AI",
    lifespan=lifespan,
)

app.include_router(api_router)
