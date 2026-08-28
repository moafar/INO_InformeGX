"""Authentication-database audit repository for generated report PDFs."""

from __future__ import annotations

from datetime import datetime

from db import get_auth_db


def record_pdf_generation(
    *,
    patient_id_num: str,
    visit_datetime: datetime,
    user_id: int,
    username: str,
    generated_at: datetime,
    filename: str,
    pdf_sha256: str,
    pdf_size_bytes: int,
) -> None:
    """Insert and commit one audit row, rolling back on every failure."""
    connection = get_auth_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ergo_app.report_pdf_audits (
                    patient_id_num,
                    visit_datetime,
                    generated_by_user_id,
                    generated_by_username,
                    generated_at,
                    filename,
                    pdf_sha256,
                    pdf_size_bytes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    patient_id_num,
                    visit_datetime,
                    user_id,
                    username,
                    generated_at,
                    filename,
                    pdf_sha256,
                    pdf_size_bytes,
                ),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
