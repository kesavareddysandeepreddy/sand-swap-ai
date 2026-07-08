"""
Base Memory Interface
"""

from abc import ABC, abstractmethod


class BaseMemory(ABC):
    @abstractmethod
    async def store(self, key, value):
        pass

    @abstractmethod
    async def retrieve(self, key):
        pass

    @abstractmethod
    async def delete(self, key):
        pass
