"""Authorization and orchestration for the persistent report state machine."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from uuid import UUID

from repositories.drafts import (
    EN_FIRMA,
    PRELIMINAR,
    PRELIMINAR_BLOQUEADO,
    DraftAccessError,
    DraftChangedError,
    DraftOwnershipError,
    DraftStateError,
    DraftValue,
    PersistedDraft,
    PersistedReportVersion,
    create_next_version,
    get_or_create_draft,
    release_from_signature,
    save_values,
    sign_draft,
    take_for_signature,
)
from services.report_controls import AUXILIAR, MEDICO, CALCULADO, DIRECTO, CONTROL_TYPES, controls_editable_by
from services.signature_profile import signature_profile_for_user
from services.study_report import (
    MAX_REPORT_FIELD_LENGTH,
    REPORT_CONTROL_IDS,
    StudyReportView,
    VDVT_ESTIMATED_SOURCE,
    VDVT_FIELD_SOURCES,
    VDVT_MEASURED_SOURCE,
    build_study_report_from_persisted,
    build_study_report_view,
    vdvt_source_for_medicion_gases,
)


class DraftPermissionError(PermissionError):
    pass


def _as_view(draft: PersistedDraft) -> StudyReportView:
    return build_study_report_from_persisted(
        values={key: value.current_value for key, value in draft.values.items()},
        originals={key: value.original_value for key, value in draft.values.items()},
        edited={key: value.edited for key, value in draft.values.items()},
        lookup_patient_id_num=draft.lookup_patient_id_num,
        lookup_visit_datetime=draft.lookup_visit_datetime.strftime("%Y-%m-%d %H:%M:%S"),
        vdvt_metadata=draft.vdvt_metadata,
    )


def report_view_for_version(version: PersistedReportVersion) -> StudyReportView:
    return build_study_report_from_persisted(
        values={key: value.current_value for key, value in version.values.items()},
        originals={key: value.original_value for key, value in version.values.items()},
        edited={key: value.edited for key, value in version.values.items()},
        lookup_patient_id_num=version.lookup_patient_id_num,
        lookup_visit_datetime=version.lookup_visit_datetime.strftime("%Y-%m-%d %H:%M:%S"),
        vdvt_metadata=version.vdvt_metadata,
    )


def open_persistent_draft(*, patient_id_num: str, visit_datetime: datetime, clinical_row: dict[str, object]) -> tuple[PersistedDraft, StudyReportView]:
    """Create v1 only when absent; opening never takes medical ownership."""
    initial_view = build_study_report_view(clinical_row)
    initial_values = {
        key: DraftValue(key, field.variable_type, str(field.original_value), str(field.value), False)
        for key, field in initial_view.fields.items()
    }
    draft = get_or_create_draft(
        patient_id_num=patient_id_num,
        visit_datetime=visit_datetime,
        initial_values=initial_values,
        vdvt_metadata=dict(initial_view.vdvt_metadata or {}),
    )
    return draft, _as_view(draft)


def editable_control_ids(role: str, draft: PersistedDraft, *, user_id: int | None = None) -> frozenset[str]:
    if role == AUXILIAR and draft.state == PRELIMINAR:
        return controls_editable_by(AUXILIAR, signed_version_exists=False)
    if role == MEDICO and draft.state == EN_FIRMA and draft.medical_owner_user_id == user_id:
        return frozenset(CONTROL_TYPES)
    return frozenset()


def _vdvt_switch_updates(
    draft: PersistedDraft, submitted_values: dict[str, object]
) -> tuple[dict[str, object], dict[str, object] | None]:
    """Apply a submitted VD/VT source change using only persisted alternatives."""
    if "medicion_gases" not in submitted_values or not draft.vdvt_metadata:
        return submitted_values, None
    metadata = draft.vdvt_metadata
    values = metadata.get("values")
    current_source = metadata.get("selected_source")
    selected_source = vdvt_source_for_medicion_gases(submitted_values["medicion_gases"])
    if (
        current_source not in {VDVT_MEASURED_SOURCE, VDVT_ESTIMATED_SOURCE}
        or not isinstance(values, dict)
        or selected_source == current_source
    ):
        return submitted_values, None

    updated_values = dict(submitted_values)
    copied_sources: dict[str, dict[str, str]] = {}
    for key in VDVT_FIELD_SOURCES:
        pair = values.get(key)
        if not isinstance(pair, dict):
            return submitted_values, None
        measured = pair.get(VDVT_MEASURED_SOURCE)
        estimated = pair.get(VDVT_ESTIMATED_SOURCE)
        if not isinstance(measured, str) or not isinstance(estimated, str):
            return submitted_values, None
        copied_sources[key] = {
            VDVT_MEASURED_SOURCE: measured,
            VDVT_ESTIMATED_SOURCE: estimated,
        }
        updated_values[key] = pair[selected_source]
    return updated_values, {"selected_source": selected_source, "values": copied_sources}


def save_draft_values(*, draft: PersistedDraft, user_id: int, role: str, submitted_values: dict[str, object], expected_revision: int | None = None) -> PersistedDraft:
    editable = editable_control_ids(role, draft, user_id=user_id)
    if not editable:
        raise DraftPermissionError("No tiene permiso para editar este informe en su estado actual.")
    normalized_submitted_values, vdvt_metadata = _vdvt_switch_updates(draft, submitted_values)
    updates: dict[str, tuple[str, bool]] = {}
    for key, raw_value in normalized_submitted_values.items():
        if key not in REPORT_CONTROL_IDS or not isinstance(raw_value, str):
            raise DraftPermissionError("El formulario contiene un campo no válido.")
        if len(raw_value) > MAX_REPORT_FIELD_LENGTH or "\x00" in raw_value:
            raise DraftPermissionError(f"El campo {key} no es válido.")
        prior = draft.values[key]
        if key not in editable:
            if raw_value != prior.current_value:
                raise DraftPermissionError(f"No tiene permiso para modificar {key}.")
            continue
        updates[key] = (raw_value, CONTROL_TYPES[key] in {DIRECTO, CALCULADO} and raw_value != prior.original_value)
    return save_values(
        draft_id=draft.id, updates=updates,
        expected_revision=draft.revision if expected_revision is None else expected_revision,
        expected_state=draft.state, expected_owner_user_id=draft.medical_owner_user_id,
        vdvt_metadata=vdvt_metadata,
    )


def take_draft_for_signature(*, draft: PersistedDraft, user_id: int, username: str, role: str) -> PersistedDraft:
    if role != MEDICO:
        raise DraftPermissionError("Solo un médico puede tomar el informe para firma.")
    return take_for_signature(draft_id=draft.id, user_id=user_id, username=username)


def release_draft(*, draft: PersistedDraft, user_id: int, username: str, role: str) -> PersistedDraft:
    if role != MEDICO:
        raise DraftPermissionError("Solo un médico puede liberar el informe.")
    return release_from_signature(draft_id=draft.id, user_id=user_id, username=username)


def sign_report_draft(*, draft: PersistedDraft, user, expected_values: dict[str, DraftValue] | None = None) -> PersistedReportVersion:
    if user.role != MEDICO:
        raise DraftPermissionError("Solo un médico puede firmar el informe.")
    return sign_draft(
        draft_id=draft.id, user_id=int(user.get_id()), username=user.username,
        signer_signature_profile=asdict(signature_profile_for_user(user)), expected_values=expected_values,
    )


def create_new_report_version(*, source_version_id: UUID, user_id: int, username: str, role: str) -> PersistedDraft:
    if role != MEDICO:
        raise DraftPermissionError("Solo un médico puede crear una nueva versión.")
    return create_next_version(source_version_id=source_version_id, user_id=user_id, username=username)


def report_view_for_draft(draft: PersistedDraft) -> StudyReportView:
    return _as_view(draft)


__all__ = [
    "DraftPermissionError", "DraftAccessError", "DraftChangedError", "DraftOwnershipError", "DraftStateError",
    "editable_control_ids", "open_persistent_draft", "save_draft_values", "take_draft_for_signature",
    "release_draft", "sign_report_draft", "create_new_report_version", "report_view_for_draft", "report_view_for_version",
]
