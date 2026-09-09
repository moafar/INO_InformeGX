"""Study selection, durable workflow actions and on-demand PDF routes."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from uuid import UUID

from flask import Blueprint, Response, abort, current_app, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from repositories.drafts import (
    EN_FIRMA,
    PRELIMINAR,
    PRELIMINAR_BLOQUEADO,
    DraftAccessError,
    DraftChangedError,
    DraftOwnershipError,
    DraftStateError,
    get_draft,
    get_report_version,
    list_report_versions,
    record_pdf_event,
)
from services.csrf import validate_csrf_token
from services.draft_workflow import (
    DraftPermissionError,
    create_new_report_version,
    editable_control_ids,
    open_persistent_draft,
    release_draft,
    report_view_for_draft,
    report_view_for_version,
    save_draft_values,
    sign_report_draft,
    take_draft_for_signature,
)
from services.gx_data_source import AmbiguousGXStudyError, gx_data_source
from services.pdf_report import generate_report_pdf
from services.report_controls import COORDINADORA, MEDICO
from services.report_narratives import build_report_narratives
from services.signature_profile import SignatureProfile
from services.study_report import ReportFormValidationError, build_study_report_view


studies_bp = Blueprint("studies", __name__)


def _synthetic_preview_row() -> dict[str, object]:
    return {
        "patient_id_num": "12345678", "patient_first_name": "Ana", "patient_middle_name": "María",
        "patient_last_name": "García", "visit_datetime": "2026-08-20 17:43:15", "age": 45, "sex": "F",
        "diagnosis": "DX", "weight": 68.2, "height": 1.72, "bmi": 24.1,
        "gx_vo2_max_time_sec": "675", "gx_at_ex_time_sec": "386", "gx_at_vo2_ml_per_min": "720",
        "gx_vo2_max_work_watts": "150", "gx_vo2_max_rer": "0.98", "gx_rest_vo2_ml_per_min": "250",
        "gx_rest_vo2_ml_per_kg_per_min": "3.5", "gx_vo2_max_vo2_ml_per_min": "1800",
        "gx_vo2_max_vo2_ml_per_kg_per_min": "26.5", "gx_vo2_max_vo2workslope_ml_per_min_per_watt": "10.2",
        "gx_predicted_vo2_ml_per_min": "2000", "gx_predicted_work_watts": "170",
        "gx_rest_hr_bpm": "80", "gx_vo2_max_hr_bpm": "160", "gx_predicted_hr_bpm": "170",
        "gx_rest_sysbp_mmhg": "120", "gx_rest_diabp_mmhg": "80", "gx_vo2_max_sysbp_mmhg": "160",
        "gx_vo2_max_diabp_mmhg": "90", "gx_vo2_max_vo2_per_hr_ml_per_beat": "11.2",
        "gx_predicted_vo2_per_hr_ml_per_beat": "9.8", "pf_pre_mvv_l_per_min": "70",
        "gx_rest_ve_btps_l_per_min": "18", "gx_vo2_max_ve_btps_l_per_min": "55",
        "gx_vo2_max_ve_per_mvv_pct": "58", "gx_vo2_max_vt_per_ic_pct": "61", "gx_rest_rr_br_per_min": "14",
        "gx_vo2_max_rr_br_per_min": "30", "gx_rest_spo2_pct": "97", "gx_vo2_max_spo2_pct": "95",
        "gx_rest_vd_per_vt_meas": "25", "gx_vo2_max_vd_per_vt_meas": "18", "gx_rest_vd_per_vt_est": "30",
        "gx_vo2_max_vd_per_vt_est": "22", "gx_rest_petco2_mmhg": "35", "gx_rest_ph": "7.4", "gx_vo2_max_ph": "7.3",
        "gx_at_ve_per_vco2": "28", "gx_at_ve_per_vo2": "24",
    }


def _audit_visit_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise ReportFormValidationError("La fecha del estudio no es válida.") from error


def _generation_instant() -> datetime:
    return datetime.now(timezone.utc)


def _pdf_filename(patient_id_num: str, visit_datetime: datetime, version_number: int) -> str:
    safe_patient_id = secure_filename(patient_id_num) or "sin_identificacion"
    return f"informe_gx_{safe_patient_id}_{visit_datetime.date().isoformat()}_v{version_number}.pdf"


def _render_draft(draft, report, *, preview_mode: bool = False):
    user_id = int(current_user.get_id()) if current_user.is_authenticated else None
    can_take = not preview_mode and current_user.role == MEDICO and draft.state in {PRELIMINAR, PRELIMINAR_BLOQUEADO}
    is_owner = draft.state == EN_FIRMA and draft.medical_owner_user_id == user_id
    return render_template(
        "study_draft.html", draft=report, persistent_draft=draft,
        editable_control_ids=editable_control_ids(current_user.role, draft, user_id=user_id) if not preview_mode else frozenset(report.fields),
        preview_mode=preview_mode, workflow_state=draft.state if not preview_mode else "PRELIMINAR",
        can_take=can_take, can_release=not preview_mode and current_user.role == MEDICO and is_owner,
        can_sign=not preview_mode and current_user.role == MEDICO and is_owner,
    )


@studies_bp.post("/studies/select")
@login_required
def select():
    if not validate_csrf_token(request.form.get("csrf_token")):
        return render_template("index.html", result=None, error="Formulario no válido."), 400
    patient_id_num = request.form.get("study_patient_id_num") or ""
    try:
        parsed_visit = _audit_visit_datetime(request.form.get("study_visit_datetime", ""))
        row = gx_data_source.get_study(patient_id_num, parsed_visit)
    except (ReportFormValidationError, AmbiguousGXStudyError) as error:
        return render_template("index.html", result=None, error=str(error)), 409
    if row is None:
        return render_template("index.html", result=None, error="El estudio ya no está disponible."), 404
    if current_user.role == COORDINADORA:
        return render_template("study_versions.html", patient_id_num=patient_id_num, visit_datetime=parsed_visit, versions=list_report_versions(patient_id_num=patient_id_num, visit_datetime=parsed_visit))
    try:
        draft, report = open_persistent_draft(patient_id_num=patient_id_num, visit_datetime=parsed_visit, clinical_row=row)
    except DraftStateError as error:
        versions = list_report_versions(patient_id_num=patient_id_num, visit_datetime=parsed_visit)
        if current_user.role == MEDICO and versions:
            return redirect(url_for("studies.view_version", version_id=versions[0].id))
        return render_template("index.html", result=None, error=str(error)), 409
    except DraftAccessError as error:
        return render_template("index.html", result=None, error=str(error)), 409
    return _render_draft(draft, report)


def _load_draft_from_request():
    try:
        draft_id = UUID(request.form.get("draft_id", ""))
    except (TypeError, ValueError):
        raise DraftAccessError("El borrador no es válido.")
    draft = get_draft(draft_id)
    if draft is None:
        raise DraftAccessError("El borrador ya no está disponible.")
    return draft


def _workflow_error(error):
    status = 409 if isinstance(error, (DraftChangedError, DraftStateError)) else 403
    return {"error": str(error)}, status


@studies_bp.post("/studies/drafts/save")
@login_required
def save_draft():
    if not validate_csrf_token(request.form.get("csrf_token")):
        return {"error": "Formulario no válido."}, 400
    try:
        draft = _load_draft_from_request()
        revision = int(request.form.get("draft_revision", draft.revision))
        values = {key: request.form.get(key, "") for key in draft.values if key in request.form}
        saved = save_draft_values(draft=draft, user_id=int(current_user.get_id()), role=current_user.role, submitted_values=values, expected_revision=revision)
    except (ValueError, DraftAccessError, DraftChangedError, DraftPermissionError, DraftStateError, DraftOwnershipError) as error:
        return _workflow_error(error)
    return {"draft_id": str(saved.id), "revision": saved.revision, "state": saved.state, "saved": True}


@studies_bp.post("/studies/drafts/take")
@login_required
def take_draft():
    if not validate_csrf_token(request.form.get("csrf_token")):
        return {"error": "Formulario no válido."}, 400
    try:
        taken = take_draft_for_signature(draft=_load_draft_from_request(), user_id=int(current_user.get_id()), username=current_user.username, role=current_user.role)
    except (DraftAccessError, DraftPermissionError, DraftStateError, DraftOwnershipError) as error:
        return _workflow_error(error)
    return {"draft_id": str(taken.id), "revision": taken.revision, "state": taken.state, "taken": True}


@studies_bp.post("/studies/drafts/release")
@login_required
def release_draft_route():
    if not validate_csrf_token(request.form.get("csrf_token")):
        return {"error": "Formulario no válido."}, 400
    try:
        released = release_draft(draft=_load_draft_from_request(), user_id=int(current_user.get_id()), username=current_user.username, role=current_user.role)
    except (DraftAccessError, DraftPermissionError, DraftStateError, DraftOwnershipError) as error:
        return _workflow_error(error)
    return {"draft_id": str(released.id), "revision": released.revision, "state": released.state, "released": True}


@studies_bp.post("/studies/drafts/sign")
@login_required
def sign_draft_route():
    if not validate_csrf_token(request.form.get("csrf_token")):
        return {"error": "Formulario no válido."}, 400
    try:
        draft = _load_draft_from_request()
        version = sign_report_draft(draft=draft, user=current_user, expected_values=draft.values)
    except (DraftAccessError, DraftChangedError, DraftPermissionError, DraftStateError, DraftOwnershipError) as error:
        return _workflow_error(error)
    return {"version_id": str(version.id), "version_number": version.version_number, "state": "FIRMADO", "signed": True, "next_url": url_for("studies.view_version", version_id=version.id)}


@studies_bp.get("/studies/drafts/<uuid:draft_id>")
@login_required
def view_draft(draft_id: UUID):
    draft = get_draft(draft_id)
    if draft is None:
        abort(404)
    return _render_draft(draft, report_view_for_draft(draft))


@studies_bp.get("/studies/versions/<uuid:version_id>")
@login_required
def view_version(version_id: UUID):
    version = get_report_version(version_id)
    if version is None:
        abort(404)
    if current_user.role == COORDINADORA:
        return render_template("study_versions.html", patient_id_num=version.lookup_patient_id_num, visit_datetime=version.lookup_visit_datetime, versions=[version])
    if current_user.role != MEDICO:
        abort(403)
    return render_template("study_signed.html", version=version, draft=report_view_for_version(version))


@studies_bp.post("/studies/versions/create")
@login_required
def create_version():
    if not validate_csrf_token(request.form.get("csrf_token")):
        return {"error": "Formulario no válido."}, 400
    try:
        source_version_id = UUID(request.form.get("version_id", ""))
        draft = create_new_report_version(source_version_id=source_version_id, user_id=int(current_user.get_id()), username=current_user.username, role=current_user.role)
    except (TypeError, ValueError, DraftAccessError, DraftPermissionError, DraftStateError) as error:
        return _workflow_error(error)
    if request.form.get("response_format") == "html":
        return redirect(url_for("studies.view_draft", draft_id=draft.id))
    return {"draft_id": str(draft.id), "revision": draft.revision, "state": draft.state, "created": True}


@studies_bp.post("/studies/versions/report.pdf")
@login_required
def report_pdf():
    if not validate_csrf_token(request.form.get("csrf_token")):
        return "Formulario no válido.", 400
    if current_user.role != COORDINADORA:
        return "Solo una coordinadora puede generar el PDF.", 403
    try:
        version_id = UUID(request.form.get("version_id", ""))
    except (TypeError, ValueError):
        return "La versión no es válida.", 400
    version = get_report_version(version_id)
    if version is None:
        return "La versión firmada no existe.", 404
    report = report_view_for_version(version)
    generated_at = _generation_instant()
    profile = SignatureProfile(
        name=version.signer_signature_profile.get("name", "Profesional responsable"),
        profession_specialty=version.signer_signature_profile.get("profession_specialty", ""),
        professional_registration=version.signer_signature_profile.get("professional_registration", ""),
        institutional_line=version.signer_signature_profile.get("institutional_line", ""),
    )
    pdf_bytes = generate_report_pdf(report, build_report_narratives(report), generated_at=generated_at, signature_profile=profile)
    filename = _pdf_filename(version.lookup_patient_id_num, version.lookup_visit_datetime, version.version_number)
    try:
        record_pdf_event(version_id=version.id, user_id=int(current_user.get_id()), username=current_user.username, generated_at=generated_at, filename=filename, pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(), pdf_size_bytes=len(pdf_bytes))
    except DraftAccessError as error:
        return str(error), 409
    return Response(pdf_bytes, status=200, headers={"Content-Type": "application/pdf", "Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@studies_bp.get("/studies/preview")
@login_required
def preview():
    if current_app.config.get("ENVIRONMENT") == "production":
        abort(404)
    report = build_study_report_view(_synthetic_preview_row())
    class PreviewDraft:
        state = PRELIMINAR
        medical_owner_user_id = None
        id = None
        revision = 1
    return _render_draft(PreviewDraft(), report, preview_mode=True)
