"""
Base Agent Interface
"""

from abc import ABC, abstractmethod


class BaseAgent(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    async def execute(self, request):
        pass
