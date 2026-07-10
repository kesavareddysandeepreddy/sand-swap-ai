"""Helpers for working with request user context in services."""

from __future__ import annotations

from backend.auth.current_user import CurrentUser


def get_current_user_id(current_user: CurrentUser | None) -> str | None:
    """Return the authenticated user id, if one is available."""
    if current_user is None or not current_user.is_authenticated:
        return None
    return current_user.user_id
