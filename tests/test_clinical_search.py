"""Unit coverage for the read-only GX datasource and study selection.

All clinical rows used here are synthetic.  The PostgreSQL and durable-workflow
boundaries are mocked, so these tests never require a clinical database.
"""

from __future__ import annotations

from datetime import datetime
from unittest import TestCase
from unittest.mock import MagicMock, Mock, call, patch, sentinel

from app import create_app
from repositories.studies import get_study_by_identity, search_studies_by_patient_id_num
from repositories.users import AuthUser
from services.clinical_columns import CLINICAL_STUDY_COLUMN_KEYS
from services.gx_data_source import AmbiguousGXStudyError, GXPostgresDataSource
from services.search import SearchResult, StudySummary, search_by_patient_id_num


def extract_csrf(html: str) -> str:
    marker = 'name="csrf_token" value="'
    start = html.index(marker) + len(marker)
    return html[start : html.index('"', start)]


def synthetic_row(*, visit_datetime: datetime) -> tuple[object, ...]:
    values = {column: f"synthetic-{column}" for column in CLINICAL_STUDY_COLUMN_KEYS}
    values.update(
        patient_id_num="90000001",
        patient_first_name="Ana",
        patient_middle_name="Lucía",
        patient_last_name="Sintética",
        visit_datetime=visit_datetime,
    )
    return tuple(values[column] for column in CLINICAL_STUDY_COLUMN_KEYS)


def clinical_connection(*, rows: list[tuple[object, ...]]) -> tuple[MagicMock, MagicMock]:
    connection = MagicMock(name="clinical_connection")
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.description = [(column,) for column in CLINICAL_STUDY_COLUMN_KEYS]
    cursor.fetchall.return_value = rows
    return connection, cursor


class GXPostgresDataSourceTests(TestCase):
    def test_search_uses_only_the_declared_clinical_columns_and_read_only_source(self) -> None:
        visit = datetime(2026, 8, 20, 17, 43, 15)
        connection, cursor = clinical_connection(rows=[synthetic_row(visit_datetime=visit)])
        source = GXPostgresDataSource()

        with patch("services.gx_data_source.get_clinical_db", return_value=connection) as get_clinical:
            rows = source.search_studies("90000001")

        query, parameters = cursor.execute.call_args.args
        selected_columns = query.split(" FROM ", maxsplit=1)[0].removeprefix("SELECT ")
        self.assertEqual(tuple(selected_columns.split(", ")), CLINICAL_STUDY_COLUMN_KEYS)
        self.assertEqual(tuple(source._columns.split(", ")), CLINICAL_STUDY_COLUMN_KEYS)
        self.assertIn("patient_id_num", selected_columns)
        self.assertIn("visit_datetime", selected_columns)
        self.assertNotIn("*", selected_columns)
        self.assertEqual(len(selected_columns.split(", ")), len(set(CLINICAL_STUDY_COLUMN_KEYS)))
        self.assertIn("FROM staging.gx_analytics", query)
        self.assertIn("WHERE patient_id_num = %s", query)
        self.assertIn("ORDER BY visit_datetime DESC", query)
        self.assertEqual(parameters, ("90000001",))
        self.assertTrue(query.lstrip().upper().startswith("SELECT"))
        self.assertNotIn("get_app_db", GXPostgresDataSource.search_studies.__globals__)
        get_clinical.assert_called_once_with()
        connection.transaction.assert_called_once_with()
        self.assertEqual(rows[0]["visit_datetime"], visit)
        self.assertEqual(set(rows[0]), set(CLINICAL_STUDY_COLUMN_KEYS))

    def test_exact_study_lookup_uses_patient_and_visit_identity(self) -> None:
        visit = datetime(2026, 8, 20, 17, 43, 15)
        connection, cursor = clinical_connection(rows=[synthetic_row(visit_datetime=visit)])
        source = GXPostgresDataSource()

        with patch("services.gx_data_source.get_clinical_db", return_value=connection):
            study = source.get_study("90000001", visit)

        query, parameters = cursor.execute.call_args.args
        self.assertIn("FROM staging.gx_analytics", query)
        self.assertIn("WHERE patient_id_num = %s AND visit_datetime = %s", query)
        self.assertIn("LIMIT 2", query)
        self.assertEqual(parameters, ("90000001", visit))
        self.assertTrue(query.lstrip().upper().startswith("SELECT"))
        self.assertEqual(study["patient_id_num"], "90000001")
        self.assertEqual(study["visit_datetime"], visit)

    def test_exact_study_lookup_rejects_an_ambiguous_clinical_result(self) -> None:
        visit = datetime(2026, 8, 20, 17, 43, 15)
        connection, cursor = clinical_connection(
            rows=[synthetic_row(visit_datetime=visit), synthetic_row(visit_datetime=visit)]
        )

        with patch("services.gx_data_source.get_clinical_db", return_value=connection), self.assertRaises(
            AmbiguousGXStudyError
        ):
            GXPostgresDataSource().get_study("90000001", visit)

        query = cursor.execute.call_args.args[0]
        self.assertTrue(query.lstrip().upper().startswith("SELECT"))
        self.assertNotIn("INSERT", query.upper())
        self.assertNotIn("UPDATE", query.upper())
        self.assertNotIn("DELETE", query.upper())


class StudyRepositoryTests(TestCase):
    def test_repository_delegates_to_the_gx_datasource_with_exact_identity(self) -> None:
        visit = datetime(2026, 8, 20, 17, 43, 15)
        datasource = Mock()
        datasource.search_studies.return_value = ["synthetic-row"]
        datasource.get_study.return_value = {"patient_id_num": "90000001"}

        with patch("repositories.studies.gx_data_source", datasource):
            searched = search_studies_by_patient_id_num("90000001")
            selected = get_study_by_identity(" 90000001 ", visit.isoformat(sep=" "))
            missing_patient = get_study_by_identity(" ", visit)
            missing_visit = get_study_by_identity("90000001", " ")

        self.assertEqual(searched, ["synthetic-row"])
        self.assertEqual(selected, {"patient_id_num": "90000001"})
        self.assertIsNone(missing_patient)
        self.assertIsNone(missing_visit)
        datasource.search_studies.assert_called_once_with("90000001")
        datasource.get_study.assert_called_once_with("90000001", visit)


class SearchServiceTests(TestCase):
    def test_empty_patient_id_is_rejected_without_clinical_lookup(self) -> None:
        with patch("services.search.search_studies_by_patient_id_num") as search:
            result = search_by_patient_id_num("   ")

        self.assertEqual(result.studies, [])
        self.assertEqual(result.error, "Introduce un ID de paciente válido.")
        self.assertEqual(result.patient_id_num, "")
        search.assert_not_called()

    def test_search_formats_valid_results_without_technical_identifiers(self) -> None:
        rows = [
            {
                "patient_id_num": "90000001",
                "patient_first_name": "Ana",
                "patient_middle_name": "Lucía",
                "patient_last_name": "Sintética",
                "visit_datetime": datetime(2026, 8, 20, 17, 43, 15),
                "internal_study_id": "not-rendered-or-used",
            }
        ]
        with patch("services.search.search_studies_by_patient_id_num", return_value=rows) as search:
            result = search_by_patient_id_num(" 90000001 ")

        self.assertEqual(result.error, None)
        self.assertEqual(result.patient_id_num, "90000001")
        self.assertEqual(
            result.studies,
            [
                StudySummary(
                    patient_id_num="90000001",
                    full_name="Sintética, Ana Lucía",
                    visit_datetime="2026-08-20 17:43:15",
                )
            ],
        )
        self.assertFalse(hasattr(result.studies[0], "internal_study_id"))
        search.assert_called_once_with("90000001")

    def test_empty_clinical_search_result_has_a_safe_message(self) -> None:
        with patch("services.search.search_studies_by_patient_id_num", return_value=[]):
            result = search_by_patient_id_num("90000001")

        self.assertEqual(result.studies, [])
        self.assertEqual(result.error, "No se encontraron estudios para ese ID.")
        self.assertEqual(result.patient_id_num, "90000001")


class StudySelectionRouteTests(TestCase):
    def setUp(self) -> None:
        self.user = AuthUser(
            id=11,
            username="synthetic-doctor",
            full_name="Médica sintética",
            password_hash="stored-hash",
            active=True,
            role="MEDICO",
        )
        self.user_loader = patch("app.get_user_by_id", return_value=self.user)
        self.user_loader.start()
        self.addCleanup(self.user_loader.stop)
        self.app = create_app("testing")
        self.client = self.app.test_client()
        login_page = self.client.get("/login")
        with patch("routes.auth.authenticate_user", return_value=self.user):
            self.client.post(
                "/login",
                data={
                    "username": self.user.username,
                    "password": "synthetic-password",
                    "csrf_token": extract_csrf(login_page.get_data(as_text=True)),
                },
            )

    def _csrf_token(self) -> str:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        return extract_csrf(response.get_data(as_text=True))

    def test_search_page_uses_visible_selection_identity_without_internal_id(self) -> None:
        results = SearchResult(
            studies=[
                StudySummary("90000001", "Sintética, Ana Lucía", "2026-08-20 17:43:15"),
                StudySummary("90000001", "Sintética, Ana Lucía", "2026-08-19 09:00:00"),
            ],
            patient_id_num="90000001",
        )

        with patch("routes.home.search_by_patient_id_num", return_value=results):
            response = self.client.post(
                "/", data={"patient_id_num": "90000001", "csrf_token": self._csrf_token()}
            )

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('name="study_patient_id_num" value="90000001"', body)
        self.assertIn('name="study_visit_datetime" value="2026-08-20 17:43:15"', body)
        self.assertNotIn("pat_visit_id", body)
        self.assertLess(body.index("2026-08-20 17:43:15"), body.index("2026-08-19 09:00:00"))

    def test_search_page_rejects_an_empty_patient_id_without_clinical_access(self) -> None:
        with patch("services.search.search_studies_by_patient_id_num") as search:
            response = self.client.post(
                "/", data={"patient_id_num": "   ", "csrf_token": self._csrf_token()}
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Introduce un ID de paciente válido.", response.get_data(as_text=True))
        search.assert_not_called()

    def test_selection_rejects_invalid_csrf_before_clinical_lookup(self) -> None:
        with patch("routes.studies.gx_data_source.get_study") as get_study:
            response = self.client.post(
                "/studies/select",
                data={
                    "csrf_token": "invalid",
                    "study_patient_id_num": "90000001",
                    "study_visit_datetime": "2026-08-20 17:43:15",
                },
            )

        self.assertEqual(response.status_code, 400)
        get_study.assert_not_called()

    def test_selection_rejects_invalid_visit_before_clinical_lookup(self) -> None:
        with patch("routes.studies.gx_data_source.get_study") as get_study:
            response = self.client.post(
                "/studies/select",
                data={
                    "csrf_token": self._csrf_token(),
                    "study_patient_id_num": "90000001",
                    "study_visit_datetime": "not-a-datetime",
                },
            )

        self.assertEqual(response.status_code, 409)
        get_study.assert_not_called()

    def test_selection_handles_missing_or_ambiguous_studies_without_persisting(self) -> None:
        form = {
            "csrf_token": self._csrf_token(),
            "study_patient_id_num": "90000001",
            "study_visit_datetime": "2026-08-20 17:43:15",
        }
        with patch("routes.studies.open_persistent_draft") as open_draft, patch(
            "routes.studies.gx_data_source.get_study", return_value=None
        ):
            missing = self.client.post("/studies/select", data=form)

        self.assertEqual(missing.status_code, 404)
        open_draft.assert_not_called()

        form["csrf_token"] = self._csrf_token()
        with patch("routes.studies.open_persistent_draft") as open_draft, patch(
            "routes.studies.gx_data_source.get_study",
            side_effect=AmbiguousGXStudyError("selección ambigua"),
        ):
            ambiguous = self.client.post("/studies/select", data=form)

        self.assertEqual(ambiguous.status_code, 409)
        self.assertIn("selección ambigua", ambiguous.get_data(as_text=True))
        open_draft.assert_not_called()

    def test_selection_uses_exact_identity_then_opens_the_durable_draft(self) -> None:
        visit = datetime(2026, 8, 20, 17, 43, 15)
        clinical_row = {"patient_id_num": "90000001", "visit_datetime": visit}
        with patch("routes.studies.gx_data_source.get_study", return_value=clinical_row) as get_study, patch(
            "routes.studies.open_persistent_draft", return_value=(sentinel.draft, sentinel.report)
        ) as open_draft, patch("routes.studies._render_draft", return_value=("synthetic draft", 200)):
            response = self.client.post(
                "/studies/select",
                data={
                    "csrf_token": self._csrf_token(),
                    "study_patient_id_num": "90000001",
                    "study_visit_datetime": "2026-08-20 17:43:15",
                },
            )

        self.assertEqual(response.status_code, 200)
        get_study.assert_called_once_with("90000001", visit)
        open_draft.assert_called_once_with(
            patient_id_num="90000001", visit_datetime=visit, clinical_row=clinical_row
        )
