"""Session-backed presentation data for the authenticated user's PDF signature."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

from flask import session


SIGNATURE_PROFILE_SESSION_KEY = "_pdf_signature_profile"


class _SignatureUser(Protocol):
    full_name: str
    signature_name: str | None
    profession_specialty: str | None
    professional_registration: str | None
    institutional_line: str | None


@dataclass(frozen=True, slots=True)
class SignatureProfile:
    """Trusted signature footer values loaded from the authentication source."""

    name: str
    profession_specialty: str = ""
    professional_registration: str = ""
    institutional_line: str = ""


def _clean(value: object, *, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def signature_profile_for_user(user: _SignatureUser) -> SignatureProfile:
    """Build the database-backed profile, falling back only to full_name."""
    fallback_name = _clean(user.full_name, limit=200) or "Profesional responsable"
    return SignatureProfile(
        name=_clean(user.signature_name, limit=200) or fallback_name,
        profession_specialty=_clean(user.profession_specialty, limit=200),
        professional_registration=_clean(user.professional_registration, limit=120),
        institutional_line=_clean(user.institutional_line, limit=300),
    )


def store_signature_profile_in_session(user: _SignatureUser) -> None:
    """Store a trusted, bounded profile when authentication is established."""
    session[SIGNATURE_PROFILE_SESSION_KEY] = asdict(signature_profile_for_user(user))


def signature_profile_from_session(user: _SignatureUser) -> SignatureProfile:
    """Read the authenticated session profile without consulting clinical input."""
    stored = session.get(SIGNATURE_PROFILE_SESSION_KEY)
    if not isinstance(stored, dict):
        profile = signature_profile_for_user(user)
        session[SIGNATURE_PROFILE_SESSION_KEY] = asdict(profile)
        return profile

    fallback = signature_profile_for_user(user)
    return SignatureProfile(
        name=_clean(stored.get("name"), limit=200) or fallback.name,
        profession_specialty=_clean(
            stored.get("profession_specialty"),
            limit=200,
        ),
        professional_registration=_clean(
            stored.get("professional_registration"),
            limit=120,
        ),
        institutional_line=_clean(stored.get("institutional_line"), limit=300),
    )


def clear_signature_profile_from_session() -> None:
    session.pop(SIGNATURE_PROFILE_SESSION_KEY, None)
