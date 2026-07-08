"""
Base Service Interface
"""

from abc import ABC, abstractmethod


class BaseService(ABC):
    """Base class for all platform services."""

    @abstractmethod
    async def initialize(self) -> None:
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass
