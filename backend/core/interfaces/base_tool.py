"""
Base Tool Interface
"""

from abc import ABC, abstractmethod


class BaseTool(ABC):
    @property
    @abstractmethod
    def name(self):
        pass

    @abstractmethod
    async def execute(self, *args, **kwargs):
        pass
