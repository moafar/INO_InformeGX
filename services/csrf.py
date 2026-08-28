"""Simple session-backed CSRF helpers."""

from __future__ import annotations

import hmac
import secrets

from flask import session


CSRF_SESSION_KEY = "_csrf_token"


def generate_csrf_token() -> str:
    """Return the current token, creating one if needed."""
    token = session.get(CSRF_SESSION_KEY)
    if token is None:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def validate_csrf_token(form_token: str | None) -> bool:
    """Validate a submitted token against the session token."""
    session_token = session.get(CSRF_SESSION_KEY)
    if not session_token or not form_token:
        return False
    return hmac.compare_digest(session_token, form_token)
