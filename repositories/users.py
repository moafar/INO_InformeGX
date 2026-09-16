"""Authentication user repository."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib

from flask_login import UserMixin

from db import get_app_db


USER_COLUMNS = (
    "u.id, u.username, u.full_name, u.password_hash, u.active, u.role, u.created_at, "
    "sp.signature_name, sp.profession_specialty, "
    "sp.professional_registration, sp.institutional_line, "
    "sp.signature_image_mime_type, sp.signature_image_updated_at"
)


@dataclass(frozen=True, slots=True)
class StoredSignatureImage:
    content: bytes
    mime_type: str
    updated_at: datetime


@dataclass(slots=True)
class AuthUser(UserMixin):
    """Logged-in user representation."""

    id: int
    username: str
    full_name: str
    password_hash: str
    active: bool
    role: str = "MEDICO"
    created_at: datetime | None = None
    signature_name: str | None = None
    profession_specialty: str | None = None
    professional_registration: str | None = None
    institutional_line: str | None = None
    signature_image_mime_type: str | None = None
    signature_image_updated_at: datetime | None = None

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
        role=row[5],
        created_at=row[6],
        signature_name=row[7],
        profession_specialty=row[8],
        professional_registration=row[9],
        institutional_line=row[10],
        signature_image_mime_type=row[11],
        signature_image_updated_at=row[12],
    )


def get_user_by_username(username: str) -> AuthUser | None:
    """Fetch a user by username."""
    cleaned_username = (username or "").strip()
    if not cleaned_username:
        return None

    with get_app_db().cursor() as cursor:
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

    with get_app_db().cursor() as cursor:
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


def get_user_signature_image(user_id: str | int) -> StoredSignatureImage | None:
    """Load the current private signature image for signing, never for public delivery."""
    try:
        numeric_id = int(user_id)
    except (TypeError, ValueError):
        return None
    with get_app_db().cursor() as cursor:
        cursor.execute(
            """SELECT signature_image, signature_image_mime_type, signature_image_updated_at
                 FROM ergo_app.user_signature_profiles WHERE user_id=%s""",
            (numeric_id,),
        )
        row = cursor.fetchone()
    if row is None or row[0] is None or row[1] is None or row[2] is None:
        return None
    return StoredSignatureImage(bytes(row[0]), str(row[1]), row[2])


def save_user_signature_profile(
    *,
    user_id: int,
    actor_user_id: int,
    actor_username: str,
    signature_name: str,
    profession_specialty: str,
    professional_registration: str,
    institutional_line: str,
    signature_image_content: bytes | None = None,
    signature_image_mime_type: str | None = None,
    updated_at: datetime | None = None,
) -> StoredSignatureImage | None:
    """Create or update text and optionally replace the image in one transaction."""
    if not signature_name.strip() or not profession_specialty.strip() or not professional_registration.strip():
        raise ValueError("El perfil de firma no está completo.")
    if signature_image_content is not None and (
        not signature_image_content
        or len(signature_image_content) > 1048576
        or signature_image_mime_type != "image/png"
    ):
        raise ValueError("La firma manuscrita no es válida.")
    instant = updated_at or datetime.now(timezone.utc)
    connection = get_app_db()
    with connection.transaction():
        with connection.cursor() as cursor:
            if signature_image_content is None:
                cursor.execute(
                    """INSERT INTO ergo_app.user_signature_profiles
                           (user_id, signature_name, profession_specialty,
                            professional_registration, institutional_line, updated_at)
                         VALUES (%s, %s, %s, %s, %s, %s)
                         ON CONFLICT (user_id) DO UPDATE SET
                            signature_name=EXCLUDED.signature_name,
                            profession_specialty=EXCLUDED.profession_specialty,
                            professional_registration=EXCLUDED.professional_registration,
                            institutional_line=EXCLUDED.institutional_line,
                            updated_at=EXCLUDED.updated_at""",
                    (
                        user_id,
                        signature_name,
                        profession_specialty,
                        professional_registration,
                        institutional_line or None,
                        instant,
                    ),
                )
                return None
            cursor.execute(
                """INSERT INTO ergo_app.user_signature_profiles
                       (user_id, signature_name, profession_specialty,
                        professional_registration, institutional_line, updated_at,
                        signature_image, signature_image_mime_type,
                        signature_image_updated_at)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                     ON CONFLICT (user_id) DO UPDATE SET
                        signature_name=EXCLUDED.signature_name,
                        profession_specialty=EXCLUDED.profession_specialty,
                        professional_registration=EXCLUDED.professional_registration,
                        institutional_line=EXCLUDED.institutional_line,
                        updated_at=EXCLUDED.updated_at,
                        signature_image=EXCLUDED.signature_image,
                        signature_image_mime_type=EXCLUDED.signature_image_mime_type,
                        signature_image_updated_at=EXCLUDED.signature_image_updated_at""",
                (
                    user_id,
                    signature_name,
                    profession_specialty,
                    professional_registration,
                    institutional_line or None,
                    instant,
                    signature_image_content,
                    signature_image_mime_type,
                    instant,
                ),
            )
            cursor.execute(
                """INSERT INTO ergo_app.user_signature_profile_audits
                       (profile_user_id, actor_user_id, actor_username, event_type,
                        occurred_at, image_mime_type, image_sha256, image_size_bytes)
                     VALUES (%s, %s, %s, 'SIGNATURE_IMAGE_UPDATED', %s, %s, %s, %s)""",
                (
                    user_id,
                    actor_user_id,
                    actor_username,
                    instant,
                    signature_image_mime_type,
                    hashlib.sha256(signature_image_content).hexdigest(),
                    len(signature_image_content),
                ),
            )
    return StoredSignatureImage(
        signature_image_content,
        signature_image_mime_type,
        instant,
    )
