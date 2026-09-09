"""Clinical GX datasource boundary.

Only this module knows that the current datasource is PostgreSQL staging.
Future GX API implementations must satisfy :class:`GXDataSource`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from db import get_clinical_db
from services.clinical_columns import CLINICAL_STUDY_COLUMN_KEYS


class GXDataSource(Protocol):
    def search_studies(self, patient_id_num: str) -> list[dict[str, object]]: ...

    def get_study(
        self, patient_id_num: str, visit_datetime: str | datetime
    ) -> dict[str, object] | None: ...


class AmbiguousGXStudyError(RuntimeError):
    """The current source cannot identify one study safely."""


class GXPostgresDataSource:
    """Read-only PostgreSQL implementation against ``staging.gx_analytics``."""

    _columns = ", ".join(CLINICAL_STUDY_COLUMN_KEYS)

    @staticmethod
    def _row(cursor, row) -> dict[str, object]:
        return dict(zip((item[0] for item in cursor.description), row, strict=True))

    def search_studies(self, patient_id_num: str) -> list[dict[str, object]]:
        connection = get_clinical_db()
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT {self._columns} FROM staging.gx_analytics "
                    "WHERE patient_id_num = %s ORDER BY visit_datetime DESC",
                    (patient_id_num,),
                )
                return [self._row(cursor, row) for row in cursor.fetchall()]

    def get_study(
        self, patient_id_num: str, visit_datetime: str | datetime
    ) -> dict[str, object] | None:
        connection = get_clinical_db()
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT {self._columns} FROM staging.gx_analytics "
                    "WHERE patient_id_num = %s AND visit_datetime = %s LIMIT 2",
                    (patient_id_num, visit_datetime),
                )
                rows = cursor.fetchall()
                if len(rows) > 1:
                    raise AmbiguousGXStudyError(
                        "La fuente GX devolvió más de un estudio para la selección."
                    )
                return self._row(cursor, rows[0]) if rows else None


gx_data_source: GXDataSource = GXPostgresDataSource()
