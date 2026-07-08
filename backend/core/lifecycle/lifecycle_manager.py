"""
Lifecycle Manager
"""

from backend.core.logging import LoggerFactory
from backend.core.registry import registry


class LifecycleManager:
    def __init__(self):
        self.logger = LoggerFactory.get_logger("LifecycleManager")

    async def startup(self):

        self.logger.info("Starting registered services...")

        for service in registry.list_services():
            instance = registry.get(service)

            if hasattr(instance, "initialize"):
                await instance.initialize()

        self.logger.info("Startup complete.")

    async def shutdown(self):

        self.logger.info("Stopping registered services...")

        for service in reversed(registry.list_services()):
            instance = registry.get(service)

            if hasattr(instance, "shutdown"):
                await instance.shutdown()

        self.logger.info("Shutdown complete.")
