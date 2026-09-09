"""Transactional persistence for the durable report workflow.

Functional state and medical ownership live on the active draft.  The legacy
``draft_locks`` table is intentionally not used for authorization: a technical
lock must never transfer or release clinical responsibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from uuid import UUID, uuid4

from db import get_app_db


PRELIMINAR = "PRELIMINAR"
EN_FIRMA = "EN_FIRMA"
PRELIMINAR_BLOQUEADO = "PRELIMINAR_BLOQUEADO"
FIRMADO = "FIRMADO"
MEDICAL_OWNERSHIP_TTL = timedelta(days=30)


class DraftLockedError(RuntimeError):
    """Compatibility error for callers of the former technical lock API."""


class DraftAccessError(RuntimeError):
    pass


class DraftChangedError(RuntimeError):
    """The persisted content or workflow revision changed."""


class DraftStateError(DraftAccessError):
    pass


class DraftOwnershipError(DraftAccessError):
    pass


@dataclass(frozen=True, slots=True)
class DraftValue:
    key: str
    variable_type: str
    original_value: str
    current_value: str
    edited: bool


@dataclass(frozen=True, slots=True)
class PersistedDraft:
    id: UUID
    study_id: UUID
    next_version_number: int
    lookup_patient_id_num: str
    lookup_visit_datetime: datetime
    values: dict[str, DraftValue]
    state: str = PRELIMINAR
    medical_owner_user_id: int | None = None
    medical_taken_at: datetime | None = None
    revision: int = 1
    created_from_version_id: UUID | None = None
    vdvt_metadata: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class PersistedReportVersion:
    id: UUID
    study_id: UUID
    version_number: int
    signed_by_user_id: int
    signed_by_username: str
    signed_at: datetime
    lookup_patient_id_num: str
    lookup_visit_datetime: datetime
    values: dict[str, DraftValue]
    signer_signature_profile: dict[str, str]
    source_version_id: UUID | None
    vdvt_metadata: dict[str, object] | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _lock_key(patient_id_num: str, visit_datetime: datetime) -> str:
    return f"GXPostgresDataSource:{patient_id_num}:{visit_datetime.isoformat()}"


def _read_values(cursor, draft_id: UUID) -> dict[str, DraftValue]:
    cursor.execute(
        """
        SELECT field_key, variable_type, original_value, current_value, edited
          FROM ergo_app.draft_values WHERE draft_id = %s ORDER BY field_key
        """,
        (draft_id,),
    )
    return {
        value[0]: DraftValue(value[0], value[1], value[2], value[3], bool(value[4]))
        for value in cursor.fetchall()
    }


def _read_draft(cursor, draft_id: UUID, *, for_update: bool = False) -> PersistedDraft | None:
    cursor.execute(
        f"""
        SELECT d.id, d.study_id, d.next_version_number,
               s.lookup_patient_id_num, s.lookup_visit_datetime,
               d.state, d.medical_owner_user_id, d.medical_taken_at,
               d.revision, d.created_from_version_id, d.vdvt_metadata
          FROM ergo_app.report_drafts d
          JOIN ergo_app.studies s ON s.id = d.study_id
         WHERE d.id = %s {'FOR UPDATE' if for_update else ''}
        """,
        (draft_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return PersistedDraft(
        id=UUID(str(row[0])), study_id=UUID(str(row[1])), next_version_number=int(row[2]),
        lookup_patient_id_num=row[3], lookup_visit_datetime=row[4], values=_read_values(cursor, UUID(str(row[0]))),
        state=row[5], medical_owner_user_id=int(row[6]) if row[6] is not None else None,
        medical_taken_at=row[7], revision=int(row[8]),
        created_from_version_id=UUID(str(row[9])) if row[9] is not None else None,
        vdvt_metadata=row[10] if isinstance(row[10], dict) else None,
    )


def _audit(cursor, *, draft: PersistedDraft, event_type: str, actor_user_id: int | None, actor_username: str | None, instant: datetime) -> None:
    cursor.execute(
        """
        INSERT INTO ergo_app.report_workflow_audits
            (study_id, version_number, event_type, actor_user_id, actor_username, occurred_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (draft.study_id, draft.next_version_number, event_type, actor_user_id, actor_username, instant),
    )


def _expire_locked(cursor, draft: PersistedDraft, instant: datetime) -> PersistedDraft:
    """Apply the one-time functional 30-day expiration while holding the row."""
    if (
        draft.state == EN_FIRMA
        and draft.medical_taken_at is not None
        and draft.medical_taken_at <= instant - MEDICAL_OWNERSHIP_TTL
    ):
        cursor.execute(
            """
            UPDATE ergo_app.report_drafts
               SET state=%s, medical_owner_user_id=NULL, medical_taken_at=NULL,
                   revision=revision+1, updated_at=NOW()
             WHERE id=%s AND state=%s
            """,
            (PRELIMINAR_BLOQUEADO, draft.id, EN_FIRMA),
        )
        _audit(cursor, draft=draft, event_type="MEDICAL_OWNERSHIP_EXPIRED", actor_user_id=None, actor_username=None, instant=instant)
        refreshed = _read_draft(cursor, draft.id, for_update=True)
        assert refreshed is not None
        return refreshed
    return draft


def _snapshot_values(
    values: dict[str, DraftValue], vdvt_metadata: dict[str, object] | None
) -> dict[str, object]:
    snapshot: dict[str, object] = {
        "controls": {
            key: {
                "type": value.variable_type,
                "original_value": value.original_value,
                "current_value": value.current_value,
                "edited": value.edited,
            }
            for key, value in values.items()
        }
    }
    if vdvt_metadata is not None:
        snapshot["vdvt_metadata"] = vdvt_metadata
    return snapshot


def _values_from_snapshot(snapshot: dict[str, object]) -> dict[str, DraftValue]:
    controls = snapshot.get("controls", {}) if isinstance(snapshot, dict) else {}
    if not isinstance(controls, dict):
        raise DraftAccessError("El snapshot de la versión no es válido.")
    values: dict[str, DraftValue] = {}
    for key, value in controls.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            raise DraftAccessError("El snapshot de la versión no es válido.")
        values[key] = DraftValue(
            key, str(value.get("type", "")), str(value.get("original_value", "")),
            str(value.get("current_value", "")), bool(value.get("edited", False)),
        )
    return values


def _vdvt_metadata_from_snapshot(snapshot: dict[str, object]) -> dict[str, object] | None:
    metadata = snapshot.get("vdvt_metadata") if isinstance(snapshot, dict) else None
    return metadata if isinstance(metadata, dict) else None


def get_or_create_draft(
    *,
    patient_id_num: str,
    visit_datetime: datetime,
    initial_values: dict[str, DraftValue],
    vdvt_metadata: dict[str, object] | None = None,
) -> PersistedDraft:
    """Create v1 in PRELIMINAR, or return its durable active draft."""
    connection = get_app_db()
    instant = _now()
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (_lock_key(patient_id_num, visit_datetime),))
            cursor.execute(
                """SELECT id FROM ergo_app.studies
                     WHERE gx_source='GXPostgresDataSource' AND lookup_patient_id_num=%s
                       AND lookup_visit_datetime=%s FOR UPDATE""",
                (patient_id_num, visit_datetime),
            )
            study_row = cursor.fetchone()
            if study_row is not None:
                cursor.execute("SELECT id FROM ergo_app.report_drafts WHERE study_id=%s", (study_row[0],))
                row = cursor.fetchone()
                if row is None:
                    raise DraftStateError("El estudio ya tiene versiones firmadas; cree una nueva versión desde la última.")
                draft = _read_draft(cursor, UUID(str(row[0])), for_update=True)
                assert draft is not None
                return _expire_locked(cursor, draft, instant)
            study_id, draft_id = uuid4(), uuid4()
            cursor.execute(
                """INSERT INTO ergo_app.studies (id, gx_source, lookup_patient_id_num, lookup_visit_datetime)
                   VALUES (%s, 'GXPostgresDataSource', %s, %s)""",
                (study_id, patient_id_num, visit_datetime),
            )
            cursor.execute(
                """INSERT INTO ergo_app.report_drafts (id, study_id, state, vdvt_metadata)
                   VALUES (%s, %s, %s, %s::jsonb)""",
                (draft_id, study_id, PRELIMINAR, json.dumps(vdvt_metadata) if vdvt_metadata is not None else None),
            )
            cursor.executemany(
                """INSERT INTO ergo_app.draft_values
                   (draft_id, field_key, variable_type, original_value, current_value, edited)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                [(draft_id, value.key, value.variable_type, value.original_value, value.current_value, value.edited) for value in initial_values.values()],
            )
            draft = _read_draft(cursor, draft_id, for_update=True)
            assert draft is not None
            _audit(cursor, draft=draft, event_type="CREATED", actor_user_id=None, actor_username=None, instant=instant)
            return draft


def get_draft(draft_id: UUID, *, now: datetime | None = None) -> PersistedDraft | None:
    connection = get_app_db()
    with connection.transaction():
        with connection.cursor() as cursor:
            draft = _read_draft(cursor, draft_id, for_update=True)
            return _expire_locked(cursor, draft, now or _now()) if draft is not None else None


def get_existing_draft_for_study(*, patient_id_num: str, visit_datetime: datetime) -> PersistedDraft | None:
    connection = get_app_db()
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT d.id FROM ergo_app.report_drafts d JOIN ergo_app.studies s ON s.id=d.study_id
                   WHERE s.gx_source='GXPostgresDataSource' AND s.lookup_patient_id_num=%s
                     AND s.lookup_visit_datetime=%s""",
                (patient_id_num, visit_datetime),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            draft = _read_draft(cursor, UUID(str(row[0])), for_update=True)
            assert draft is not None
            return _expire_locked(cursor, draft, _now())


def save_values(
    *,
    draft_id: UUID,
    updates: dict[str, tuple[str, bool]],
    expected_revision: int,
    expected_state: str,
    expected_owner_user_id: int | None,
    vdvt_metadata: dict[str, object] | None = None,
) -> PersistedDraft:
    connection = get_app_db()
    with connection.transaction():
        with connection.cursor() as cursor:
            draft = _read_draft(cursor, draft_id, for_update=True)
            if draft is None:
                raise DraftAccessError("El borrador no existe.")
            draft = _expire_locked(cursor, draft, _now())
            if (draft.revision != expected_revision or draft.state != expected_state or draft.medical_owner_user_id != expected_owner_user_id):
                raise DraftChangedError("El informe cambió; actualice la página antes de guardar.")
            cursor.executemany(
                """UPDATE ergo_app.draft_values SET current_value=%s, edited=%s, updated_at=NOW()
                   WHERE draft_id=%s AND field_key=%s""",
                [(value, edited, draft_id, key) for key, (value, edited) in updates.items()],
            )
            if vdvt_metadata is None:
                cursor.execute("UPDATE ergo_app.report_drafts SET revision=revision+1, updated_at=NOW() WHERE id=%s", (draft_id,))
            else:
                cursor.execute(
                    """UPDATE ergo_app.report_drafts
                       SET vdvt_metadata=%s::jsonb, revision=revision+1, updated_at=NOW()
                     WHERE id=%s""",
                    (json.dumps(vdvt_metadata), draft_id),
                )
            saved = _read_draft(cursor, draft_id, for_update=True)
            assert saved is not None
            return saved


def take_for_signature(*, draft_id: UUID, user_id: int, username: str, taken_at: datetime | None = None) -> PersistedDraft:
    instant = taken_at or _now()
    connection = get_app_db()
    with connection.transaction():
        with connection.cursor() as cursor:
            draft = _read_draft(cursor, draft_id, for_update=True)
            if draft is None:
                raise DraftAccessError("El borrador no existe.")
            draft = _expire_locked(cursor, draft, instant)
            if draft.state not in {PRELIMINAR, PRELIMINAR_BLOQUEADO}:
                raise DraftStateError("El informe no está disponible para toma médica.")
            cursor.execute(
                """UPDATE ergo_app.report_drafts SET state=%s, medical_owner_user_id=%s,
                   medical_taken_at=%s, revision=revision+1, updated_at=NOW() WHERE id=%s""",
                (EN_FIRMA, user_id, instant, draft_id),
            )
            taken = _read_draft(cursor, draft_id, for_update=True)
            assert taken is not None
            _audit(cursor, draft=taken, event_type="MEDICAL_TAKEN", actor_user_id=user_id, actor_username=username, instant=instant)
            return taken


def release_from_signature(*, draft_id: UUID, user_id: int, username: str, released_at: datetime | None = None) -> PersistedDraft:
    instant = released_at or _now()
    connection = get_app_db()
    with connection.transaction():
        with connection.cursor() as cursor:
            draft = _read_draft(cursor, draft_id, for_update=True)
            if draft is None:
                raise DraftAccessError("El borrador no existe.")
            draft = _expire_locked(cursor, draft, instant)
            if draft.state != EN_FIRMA:
                raise DraftStateError("El informe no está en firma.")
            if draft.medical_owner_user_id != user_id:
                raise DraftOwnershipError("Solo el médico propietario puede liberar el informe.")
            cursor.execute(
                """UPDATE ergo_app.report_drafts SET state=%s, medical_owner_user_id=NULL,
                   medical_taken_at=NULL, revision=revision+1, updated_at=NOW() WHERE id=%s""",
                (PRELIMINAR_BLOQUEADO, draft_id),
            )
            released = _read_draft(cursor, draft_id, for_update=True)
            assert released is not None
            _audit(cursor, draft=released, event_type="MEDICAL_RELEASED", actor_user_id=user_id, actor_username=username, instant=instant)
            return released


def sign_draft(*, draft_id: UUID, user_id: int, username: str, signer_signature_profile: dict[str, str], signed_at: datetime | None = None, expected_values: dict[str, DraftValue] | None = None) -> PersistedReportVersion:
    instant = signed_at or _now()
    connection = get_app_db()
    with connection.transaction():
        with connection.cursor() as cursor:
            draft = _read_draft(cursor, draft_id, for_update=True)
            if draft is None:
                raise DraftAccessError("El borrador no existe.")
            draft = _expire_locked(cursor, draft, instant)
            if draft.state != EN_FIRMA:
                raise DraftStateError("El informe no está en firma.")
            if draft.medical_owner_user_id != user_id:
                raise DraftOwnershipError("Solo el médico propietario puede firmar el informe.")
            if expected_values is not None and draft.values != expected_values:
                raise DraftChangedError("El informe cambió durante la firma; actualice la página.")
            version_id = uuid4()
            identity = {
                "study_id": str(draft.study_id), "gx_source": "GXPostgresDataSource",
                "lookup_patient_id_num": draft.lookup_patient_id_num,
                "lookup_visit_datetime": draft.lookup_visit_datetime.isoformat(),
            }
            cursor.execute(
                """INSERT INTO ergo_app.report_versions
                   (id, study_id, version_number, signed_by_user_id, signed_by_username, signed_at,
                    state, source_version_id, signer_signature_profile, study_identity, snapshot)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)""",
                (version_id, draft.study_id, draft.next_version_number, user_id, username, instant,
                 FIRMADO, draft.created_from_version_id, json.dumps(signer_signature_profile),
                 json.dumps(identity), json.dumps(_snapshot_values(draft.values, draft.vdvt_metadata))),
            )
            _audit(cursor, draft=draft, event_type="SIGNED", actor_user_id=user_id, actor_username=username, instant=instant)
            cursor.execute("DELETE FROM ergo_app.report_drafts WHERE id=%s", (draft.id,))
            return PersistedReportVersion(version_id, draft.study_id, draft.next_version_number, user_id, username, instant,
                draft.lookup_patient_id_num, draft.lookup_visit_datetime, draft.values, signer_signature_profile,
                draft.created_from_version_id, draft.vdvt_metadata)


def _read_version(cursor, version_id: UUID, *, for_update: bool = False) -> PersistedReportVersion | None:
    cursor.execute(
        f"""SELECT v.id, v.study_id, v.version_number, v.signed_by_user_id, v.signed_by_username,
                   v.signed_at, v.study_identity, v.snapshot, v.signer_signature_profile, v.source_version_id
              FROM ergo_app.report_versions v WHERE v.id=%s AND v.state=%s {'FOR UPDATE' if for_update else ''}""",
        (version_id, FIRMADO),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    identity, snapshot, profile = row[6], row[7], row[8]
    return PersistedReportVersion(
        UUID(str(row[0])), UUID(str(row[1])), int(row[2]), int(row[3]), row[4], row[5],
        str(identity["lookup_patient_id_num"]), datetime.fromisoformat(identity["lookup_visit_datetime"]),
        _values_from_snapshot(snapshot), {str(key): str(value) for key, value in profile.items()},
        UUID(str(row[9])) if row[9] is not None else None, _vdvt_metadata_from_snapshot(snapshot),
    )


def get_report_version(version_id: UUID) -> PersistedReportVersion | None:
    with get_app_db().cursor() as cursor:
        return _read_version(cursor, version_id)


def list_report_versions(*, patient_id_num: str, visit_datetime: datetime) -> list[PersistedReportVersion]:
    with get_app_db().cursor() as cursor:
        cursor.execute(
            """SELECT v.id FROM ergo_app.report_versions v JOIN ergo_app.studies s ON s.id=v.study_id
                 WHERE s.lookup_patient_id_num=%s AND s.lookup_visit_datetime=%s AND v.state=%s
                 ORDER BY v.version_number DESC""",
            (patient_id_num, visit_datetime, FIRMADO),
        )
        return [version for row in cursor.fetchall() if (version := _read_version(cursor, UUID(str(row[0])))) is not None]


def create_next_version(*, source_version_id: UUID, user_id: int, username: str, created_at: datetime | None = None) -> PersistedDraft:
    instant = created_at or _now()
    connection = get_app_db()
    with connection.transaction():
        with connection.cursor() as cursor:
            source = _read_version(cursor, source_version_id, for_update=True)
            if source is None:
                raise DraftAccessError("La versión firmada no existe.")
            cursor.execute("SELECT id FROM ergo_app.studies WHERE id=%s FOR UPDATE", (source.study_id,))
            cursor.execute("SELECT COALESCE(MAX(version_number), 0) FROM ergo_app.report_versions WHERE study_id=%s", (source.study_id,))
            if int(cursor.fetchone()[0]) != source.version_number:
                raise DraftStateError("Solo se puede crear versión desde la última versión firmada.")
            cursor.execute("SELECT id FROM ergo_app.report_drafts WHERE study_id=%s", (source.study_id,))
            if cursor.fetchone() is not None:
                raise DraftStateError("Ya existe una versión activa para este estudio.")
            draft_id = uuid4()
            cursor.execute(
                """INSERT INTO ergo_app.report_drafts
                   (id, study_id, next_version_number, created_from_version_id, state,
                    medical_owner_user_id, medical_taken_at, vdvt_metadata)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)""",
                (
                    draft_id, source.study_id, source.version_number + 1, source.id,
                    EN_FIRMA, user_id, instant,
                    json.dumps(source.vdvt_metadata) if source.vdvt_metadata is not None else None,
                ),
            )
            cursor.executemany(
                """INSERT INTO ergo_app.draft_values
                   (draft_id, field_key, variable_type, original_value, current_value, edited)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                [(draft_id, value.key, value.variable_type, value.original_value, value.current_value, value.edited) for value in source.values.values()],
            )
            draft = _read_draft(cursor, draft_id, for_update=True)
            assert draft is not None
            _audit(cursor, draft=draft, event_type="NEW_VERSION_CREATED", actor_user_id=user_id, actor_username=username, instant=instant)
            _audit(cursor, draft=draft, event_type="MEDICAL_TAKEN", actor_user_id=user_id, actor_username=username, instant=instant)
            return draft


def record_pdf_event(*, version_id: UUID, user_id: int, username: str, generated_at: datetime, filename: str, pdf_sha256: str, pdf_size_bytes: int) -> None:
    connection = get_app_db()
    with connection.transaction():
        with connection.cursor() as cursor:
            if _read_version(cursor, version_id, for_update=True) is None:
                raise DraftAccessError("La versión firmada no existe.")
            cursor.execute(
                """INSERT INTO ergo_app.report_pdf_events
                   (version_id, generated_by_user_id, generated_by_username, generated_at,
                    filename, pdf_sha256, pdf_size_bytes)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (version_id, user_id, username, generated_at, filename, pdf_sha256, pdf_size_bytes),
            )


# Compatibility helpers: technical locks may be cleaned at logout but are not
# acquired by the workflow and never imply a functional state transition.
def acquire_lock(draft_id: UUID, user_id: int, *, now: datetime | None = None) -> PersistedDraft:
    draft = get_draft(draft_id, now=now)
    if draft is None:
        raise DraftAccessError("El borrador no existe.")
    return draft


def assert_and_renew_lock(draft_id: UUID, user_id: int, *, now: datetime | None = None) -> None:
    acquire_lock(draft_id, user_id, now=now)


def release_locks_for_user(user_id: int) -> None:
    connection = get_app_db()
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM ergo_app.draft_locks WHERE user_id=%s", (user_id,))
    connection.commit()
