"""Helpers for working with request user context in services."""

from __future__ import annotations

from backend.auth.current_user import CurrentUser

ANONYMOUS_USER_ID = "anonymous"


def normalize_user_id(user_id: str | None) -> str:
    """Normalize blank or missing user identifiers to the anonymous owner."""
    if user_id is None:
        return ANONYMOUS_USER_ID

    normalized = user_id.strip()
    return normalized or ANONYMOUS_USER_ID


def get_current_user_id(current_user: CurrentUser | None) -> str | None:
    """Return the authenticated user id, if one is available."""
    if current_user is None or not current_user.is_authenticated:
        return None
    return current_user.user_id


def resolve_owner_id(
    current_user: CurrentUser | None,
    *,
    fallback_user_id: str | None = None,
) -> str:
    """Resolve the effective owner for the current request.

    Authenticated requests always use the JWT subject. Anonymous requests may
    fall back to an explicit legacy request user id, otherwise they use the
    shared anonymous owner bucket.
    """
    current_user_id = get_current_user_id(current_user)
    if current_user_id is not None:
        return normalize_user_id(current_user_id)
    if fallback_user_id is not None:
        normalized_fallback = normalize_user_id(fallback_user_id)
        if normalized_fallback.startswith("anon-"):
            return normalized_fallback
    return ANONYMOUS_USER_ID
