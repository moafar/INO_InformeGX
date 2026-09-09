"""Authentication service."""

from __future__ import annotations

from repositories.users import AuthUser, get_user_by_username
from services.passwords import verify_password


def authenticate_user(username: str, password: str) -> AuthUser | None:
    """Authenticate a user against the application database."""
    cleaned_username = (username or "").strip()
    if not cleaned_username or not password:
        return None

    user = get_user_by_username(cleaned_username)
    if user is None or not user.active:
        return None
    if not verify_password(user.password_hash, password):
        return None
    return user
