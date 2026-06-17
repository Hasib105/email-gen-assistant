"""User authorization helpers."""

from __future__ import annotations


class AuthorizationError(Exception):
    """Raised when a user is not allowed to use the assistant."""


def authorize_user(user_id: str, allowed_user_ids: list[str]) -> None:
    """Check if a user is in the allowed list.

    If the allowlist is empty, all users are authorized.
    """
    if not allowed_user_ids:
        return
    if user_id not in allowed_user_ids:
        raise AuthorizationError(f"User is not authorized: {user_id}")
