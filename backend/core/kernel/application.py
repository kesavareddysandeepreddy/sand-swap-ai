"""
SandSwap AI Application Kernel
"""

from backend.core.logging import LoggerFactory
from backend.core.registry import registry


class Application:
    def __init__(self):
        self.logger = LoggerFactory.get_logger("Application")

    async def initialize(self):

        self.logger.info("Initializing SandSwap AI...")

        registry.register("logger", self.logger)

        self.logger.info("Application initialized.")

    async def shutdown(self):

        self.logger.info("Shutting down SandSwap AI...")

        registry.clear()

        self.logger.info("Shutdown complete.")
