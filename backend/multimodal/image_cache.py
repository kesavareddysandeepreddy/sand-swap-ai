"""Image cache abstractions for multimodal processing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ImageCache(ABC):
    """Abstract cache contract for image-derived artifacts."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return whether a cache record exists for key."""
        raise NotImplementedError

    @abstractmethod
    def load(self, key: str) -> Any | None:
        """Load a cache record by key."""
        raise NotImplementedError

    @abstractmethod
    def save(self, key: str, value: Any, image_size: int | None = None) -> None:
        """Save a cache record by key."""
        raise NotImplementedError

    @abstractmethod
    def invalidate(self, key: str) -> None:
        """Delete a cache record by key if present."""
        raise NotImplementedError


class InMemoryImageCache(ImageCache):
    """In-memory placeholder cache used until persistent storage is introduced."""

    def __init__(
        self, *, enabled: bool = True, max_image_size: int = 10_485_760
    ) -> None:
        self.enabled = enabled
        self.max_image_size = max_image_size
        self._cache: dict[str, Any] = {}

    def exists(self, key: str) -> bool:
        if not self.enabled:
            return False
        return key in self._cache

    def load(self, key: str) -> Any | None:
        if not self.enabled:
            return None
        return self._cache.get(key)

    def save(self, key: str, value: Any, image_size: int | None = None) -> None:
        if not self.enabled:
            return
        if image_size is not None and image_size > self.max_image_size:
            return
        self._cache[key] = value

    def invalidate(self, key: str) -> None:
        self._cache.pop(key, None)
