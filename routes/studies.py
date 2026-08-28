"""Study selection routes."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib

from flask import Blueprint, Response, abort, current_app, render_template, request
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from repositories.report_audits import record_pdf_generation
from services.csrf import validate_csrf_token
from services.pdf_report import generate_report_pdf
from services.report_narratives import build_report_narratives
from services.search import build_study_draft
from services.signature_profile import signature_profile_from_session
from services.study_report import (
    ReportFormValidationError,
    build_study_report_view,
    field_values_from_form,
    validated_field_values_from_form,
)


studies_bp = Blueprint("studies", __name__)


def _synthetic_preview_row() -> dict[str, object]:
    """Return synthetic study data for local UI preview."""
    return {
        "patient_id_num": "12345678",
        "patient_first_name": "Ana",
        "patient_middle_name": "María",
        "patient_last_name": "García",
        "visit_datetime": "2026-08-20 17:43:15",
        "age": 45,
        "sex": "F",
        "diagnosis": "DX",
        "dyspnea": "leve",
        "cough": "ocasional",
        "wheez": "no",
        "tbco_prod": "2",
        "pk_yrs": "10",
        "weight": 68.2,
        "height": 1.72,
        "bmi": 24.1,
        "gx_vo2_max_time_min": "12",
        "gx_vo2_max_work_watts": "150",
        "gx_vo2_max_rer": "0.98",
        "gx_rest_vo2_ml_per_min": "250",
        "gx_rest_vo2_ml_per_kg_per_min": "3.5",
        "gx_vo2_max_vo2_ml_per_min": "1800",
        "gx_vo2_max_vo2_ml_per_kg_per_min": "26.5",
        "gx_vo2_max_vo2workslope_ml_per_min_per_watt": "10.2",
        "gx_predicted_vo2_ml_per_min": "2000",
        "gx_predicted_vo2_ml_per_kg_per_min": "29.4",
        "gx_predicted_work_watts": "170",
        "gx_predicted_vo2workslope_ml_per_min_per_watt": "11.0",
        "gx_rest_hr_bpm": "80",
        "gx_vo2_max_hr_bpm": "160",
        "gx_predicted_hr_bpm": "170",
        "gx_rest_sysbp_mmhg": "120",
        "gx_rest_diabp_mmhg": "80",
        "gx_vo2_max_sysbp_mmhg": "160",
        "gx_vo2_max_diabp_mmhg": "90",
        "gx_rest_vo2_per_hr_ml_per_beat": "3.1",
        "gx_vo2_max_vo2_per_hr_ml_per_beat": "11.2",
        "gx_predicted_vo2_per_hr_ml_per_beat": "9.8",
        "pf_pre_mvv_l_per_min": "70",
        "gx_rest_ve_btps_l_per_min": "18",
        "gx_vo2_max_ve_btps_l_per_min": "55",
        "gx_vo2_max_ve_per_mvv_pct": "58",
        "gx_vo2_max_vt_per_ic_pct": "61",
        "gx_rest_rr_br_per_min": "14",
        "gx_vo2_max_rr_br_per_min": "30",
        "gx_rest_spo2_pct": "97",
        "gx_vo2_max_spo2_pct": "95",
        "gx_rest_vd_per_vt_meas": "25",
        "gx_vo2_max_vd_per_vt_meas": "18",
        "gx_rest_petco2_mmhg": "35",
        "gx_vo2_max_petco2_mmhg": "30",
    }


@studies_bp.post("/studies/select")
@login_required
def select():
    """Render the ephemeral study draft."""
    if not validate_csrf_token(request.form.get("csrf_token")):
        return render_template("index.html", result=None, error="Formulario no válido."), 400

    patient_id_num = request.form.get("study_patient_id_num")
    visit_datetime = request.form.get("study_visit_datetime")
    study_draft = build_study_draft(
        patient_id_num,
        visit_datetime,
        submitted_values=field_values_from_form(request.form.items()),
    )
    if study_draft is None:
        return render_template(
            "index.html",
            result=None,
            error="El estudio ya no está disponible.",
        )

    return render_template("study_draft.html", draft=study_draft, preview_mode=False)


def _audit_visit_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise ReportFormValidationError("La fecha del estudio no es válida.") from error


def _pdf_filename(patient_id_num: str, visit_datetime: datetime) -> str:
    safe_patient_id = secure_filename(patient_id_num) or "sin_identificacion"
    return f"informe_gx_{safe_patient_id}_{visit_datetime.date().isoformat()}.pdf"


def _generation_instant() -> datetime:
    return datetime.now(timezone.utc)


@studies_bp.post("/studies/report.pdf")
@login_required
def report_pdf():
    """Validate, rebuild, audit and return one in-memory report PDF."""
    if not validate_csrf_token(request.form.get("csrf_token")):
        return "Formulario no válido.", 400

    try:
        submitted_values = validated_field_values_from_form(request.form)
    except ReportFormValidationError as error:
        return str(error), 400

    study_report = build_study_draft(
        request.form.get("study_patient_id_num"),
        request.form.get("study_visit_datetime"),
        submitted_values=submitted_values,
    )
    if study_report is None:
        return "El estudio ya no está disponible.", 404

    try:
        visit_datetime = _audit_visit_datetime(study_report.lookup_visit_datetime)
    except ReportFormValidationError as error:
        return str(error), 400

    narratives = build_report_narratives(study_report)
    generated_at = _generation_instant()
    pdf_bytes = generate_report_pdf(
        study_report,
        narratives,
        generated_at=generated_at,
        signature_profile=signature_profile_from_session(current_user),
    )
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
    pdf_size = len(pdf_bytes)
    filename = _pdf_filename(study_report.lookup_patient_id_num, visit_datetime)
    record_pdf_generation(
        patient_id_num=study_report.lookup_patient_id_num,
        visit_datetime=visit_datetime,
        user_id=int(current_user.get_id()),
        username=current_user.username,
        generated_at=generated_at,
        filename=filename,
        pdf_sha256=pdf_hash,
        pdf_size_bytes=pdf_size,
    )

    return Response(
        pdf_bytes,
        status=200,
        headers={
            "Content-Type": "application/pdf",
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@studies_bp.get("/studies/preview")
@login_required
def preview():
    """Render the draft wireframe with synthetic data in non-production."""
    if current_app.config.get("ENVIRONMENT") == "production":
        abort(404)

    study_draft = build_study_report_view(_synthetic_preview_row())
    return render_template("study_draft.html", draft=study_draft, preview_mode=True)
