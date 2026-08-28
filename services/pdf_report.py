"""In-memory HTML-to-PDF rendering for clinical reports."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from flask import current_app, render_template

from services.report_narratives import NarrativeSection
from services.signature_profile import SignatureProfile
from services.study_report import StudyReportView


WIDE_LETTERHEAD_PATH = Path("static/report_assets/membrete_ancho.svg")
COMPACT_LETTERHEAD_PATH = Path("static/report_assets/membrete_compacto.svg")
BOGOTA_TIMEZONE = ZoneInfo("America/Bogota")


def _visible_patient_name(report: StudyReportView) -> str:
    return " ".join(
        value
        for value in (
            str(report.field("patient_first_name").value or "").strip(),
            str(report.field("patient_middle_name").value or "").strip(),
            str(report.field("patient_last_name").value or "").strip(),
        )
        if value
    )


def _asset_uri(root_path: Path, relative_path: Path) -> str | None:
    asset_path = relative_path if relative_path.is_absolute() else root_path / relative_path
    return asset_path.resolve().as_uri() if asset_path.is_file() else None


def format_generation_time_bogota(generated_at: datetime) -> str:
    """Format the audited instant for the PDF footer in Colombia time."""
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("generated_at debe incluir zona horaria")
    return generated_at.astimezone(BOGOTA_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")


def _conclusion_paragraphs(report: StudyReportView) -> tuple[str, ...]:
    value = report.field("conclusiones_definitivas").value
    text = "" if value is None else str(value).strip()
    if not text:
        return ()
    return tuple(
        paragraph.strip()
        for paragraph in re.split(r"(?:\r?\n\s*){2,}", text)
        if paragraph.strip()
    )


def generate_report_pdf(
    report: StudyReportView,
    narratives: tuple[NarrativeSection, ...],
    *,
    generated_at: datetime,
    signature_profile: SignatureProfile,
) -> bytes:
    """Render the final report to bytes without writing a repository file."""
    # Import lazily so non-PDF commands can still give a focused dependency
    # error when the deployment has not installed the documented PDF extras.
    from weasyprint import CSS, HTML

    root_path = Path(current_app.root_path)
    html = render_template(
        "study_report_pdf.html",
        report=report,
        narratives=narratives,
        patient_name=_visible_patient_name(report) or "Paciente sin identificar",
        generated_at_bogota=format_generation_time_bogota(generated_at),
        signature_profile=signature_profile,
        conclusion_paragraphs=_conclusion_paragraphs(report),
        wide_letterhead_uri=_asset_uri(root_path, WIDE_LETTERHEAD_PATH),
        compact_letterhead_uri=_asset_uri(root_path, COMPACT_LETTERHEAD_PATH),
    )
    pdf_bytes = HTML(string=html, base_url=str(root_path)).write_pdf(
        stylesheets=[CSS(filename=str(root_path / "static" / "study_report_pdf.css"))],
    )
    if not isinstance(pdf_bytes, bytes) or not pdf_bytes.startswith(b"%PDF-"):
        raise RuntimeError("El motor PDF no devolvió un documento válido.")
    return pdf_bytes
