"""Read-only repository helpers for clinical studies."""

from __future__ import annotations

from datetime import datetime

from db import get_clinical_db
from services.draft import CLINICAL_STUDY_COLUMN_KEYS


STUDY_COLUMNS = ", ".join(CLINICAL_STUDY_COLUMN_KEYS)


def _row_to_dict(cursor, row):
    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row, strict=True))


def search_studies_by_patient_id_num(patient_id_num: str):
    """Return exact-match studies ordered from newest to oldest."""
    with get_clinical_db() as conn:
        with conn.transaction():
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT {STUDY_COLUMNS}
                    FROM staging.gx_analytics
                    WHERE patient_id_num = %s
                    ORDER BY visit_datetime DESC
                    """,
                    (patient_id_num,),
                )
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


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

    with get_clinical_db() as conn:
        with conn.transaction():
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT {STUDY_COLUMNS}
                    FROM staging.gx_analytics
                    WHERE patient_id_num = %s
                      AND visit_datetime = %s
                    """,
                    (cleaned_patient_id_num, coalesced_visit_datetime),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row, strict=True))
