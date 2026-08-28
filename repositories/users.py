"""Authentication user repository."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from flask_login import UserMixin

from db import get_auth_db


USER_COLUMNS = (
    "u.id, u.username, u.full_name, u.password_hash, u.active, u.created_at, "
    "sp.signature_name, sp.profession_specialty, "
    "sp.professional_registration, sp.institutional_line"
)


@dataclass(slots=True)
class AuthUser(UserMixin):
    """Logged-in user representation."""

    id: int
    username: str
    full_name: str
    password_hash: str
    active: bool
    created_at: datetime | None = None
    signature_name: str | None = None
    profession_specialty: str | None = None
    professional_registration: str | None = None
    institutional_line: str | None = None

    @property
    def is_active(self) -> bool:
        return self.active

    def get_id(self) -> str:
        return str(self.id)


def _row_to_user(row) -> AuthUser | None:
    if row is None:
        return None
    return AuthUser(
        id=int(row[0]),
        username=row[1],
        full_name=row[2],
        password_hash=row[3],
        active=bool(row[4]),
        created_at=row[5],
        signature_name=row[6],
        profession_specialty=row[7],
        professional_registration=row[8],
        institutional_line=row[9],
    )


def get_user_by_username(username: str) -> AuthUser | None:
    """Fetch a user by username."""
    cleaned_username = (username or "").strip()
    if not cleaned_username:
        return None

    with get_auth_db().cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {USER_COLUMNS}
            FROM ergo_app.users AS u
            LEFT JOIN ergo_app.user_signature_profiles AS sp ON sp.user_id = u.id
            WHERE u.username = %s
            """,
            (cleaned_username,),
        )
        return _row_to_user(cursor.fetchone())


def get_user_by_id(user_id: str | int) -> AuthUser | None:
    """Fetch a user by identifier."""
    try:
        numeric_id = int(user_id)
    except (TypeError, ValueError):
        return None

    with get_auth_db().cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {USER_COLUMNS}
            FROM ergo_app.users AS u
            LEFT JOIN ergo_app.user_signature_profiles AS sp ON sp.user_id = u.id
            WHERE u.id = %s
            """,
            (numeric_id,),
        )
        return _row_to_user(cursor.fetchone())
