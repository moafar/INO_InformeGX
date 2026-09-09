"""Compatibility facade for the GX datasource.

New application code must depend on :mod:`services.gx_data_source` directly.
"""

from __future__ import annotations

from datetime import datetime

from services.gx_data_source import gx_data_source


def search_studies_by_patient_id_num(patient_id_num: str):
    """Return exact-match studies ordered from newest to oldest."""
    return gx_data_source.search_studies(patient_id_num)


def _coerce_visit_datetime(value: str | datetime | None):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    return datetime.fromisoformat(text)


def get_study_by_identity(
    patient_id_num: str | None,
    visit_datetime: str | datetime | None,
):
    """Return one study by patient identifier and exact visit datetime."""
    cleaned_patient_id_num = (patient_id_num or "").strip()
    coalesced_visit_datetime = _coerce_visit_datetime(visit_datetime)
    if not cleaned_patient_id_num or coalesced_visit_datetime is None:
        return None
    return gx_data_source.get_study(cleaned_patient_id_num, coalesced_visit_datetime)
