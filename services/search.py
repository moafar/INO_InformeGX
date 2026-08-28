"""Study search and selection services."""

from __future__ import annotations

from dataclasses import dataclass

from repositories.studies import (
    get_study_by_identity,
    search_studies_by_patient_id_num,
)
from services.study_report import StudyReportView, build_study_report_view
from services.names import format_full_name, format_visit_datetime


@dataclass(slots=True)
class StudySummary:
    """Renderable summary of a study."""

    patient_id_num: str
    full_name: str
    visit_datetime: str


@dataclass(slots=True)
class SearchResult:
    """Search result for the home page."""

    studies: list[StudySummary]
    error: str | None = None
    patient_id_num: str = ""


def _to_summary(row) -> StudySummary:
    return StudySummary(
        patient_id_num=str(row["patient_id_num"]),
        full_name=format_full_name(
            row["patient_first_name"],
            row["patient_middle_name"],
            row["patient_last_name"],
        ),
        visit_datetime=format_visit_datetime(row["visit_datetime"]),
    )


def search_by_patient_id_num(patient_id_num: str | None) -> SearchResult:
    """Search for exact patient ID matches."""
    cleaned = (patient_id_num or "").strip()
    if not cleaned:
        return SearchResult(studies=[], error="Introduce un ID de paciente válido.")

    rows = search_studies_by_patient_id_num(cleaned)
    if not rows:
        return SearchResult(
            studies=[],
            error="No se encontraron estudios para ese ID.",
            patient_id_num=cleaned,
        )

    return SearchResult(
        studies=[_to_summary(row) for row in rows],
        patient_id_num=cleaned,
    )


def build_study_draft(
    patient_id_num: str | None,
    visit_datetime: str | None,
    submitted_values: dict[str, str] | None = None,
) -> StudyReportView | None:
    """Build the ephemeral study draft after exact identity lookup."""
    row = get_study_by_identity(patient_id_num, visit_datetime)
    if row is None:
        return None

    return build_study_report_view(row, submitted_values=submitted_values)
