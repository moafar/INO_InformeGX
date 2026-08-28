"""Unittest suite for authentication, search and guided draft flow."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from html.parser import HTMLParser
import re
from unittest.mock import MagicMock, Mock, call, patch
from werkzeug.datastructures import MultiDict

from app import create_app
from db import get_auth_db, get_clinical_db
from repositories.studies import STUDY_COLUMNS, get_study_by_identity, search_studies_by_patient_id_num
from repositories.report_audits import record_pdf_generation
from repositories.users import AuthUser, get_user_by_id, get_user_by_username
from services.draft import (
    CLINICAL_STUDY_COLUMN_KEYS,
    REPORT_SECTION_SPECS,
    build_study_draft_view,
    field_values_from_form,
    generate_structure_markdown,
    render_narrative_section,
)
from services.names import format_full_name, format_visit_datetime
from services.pdf_report import format_generation_time_bogota, generate_report_pdf
from services.passwords import hash_password, verify_password
from services.report_narratives import SECTION_TITLES, build_report_narratives
from services.signature_profile import (
    SIGNATURE_PROFILE_SESSION_KEY,
    SignatureProfile,
)
from services.search import SearchResult, StudySummary
from services.study_report import (
    DERIVED_FIELD_SOURCES,
    DIRECT_FIELD_SOURCES,
    MANUAL_CONTROL_IDS,
    REPORT_CONTROL_IDS,
    build_derived_values,
    build_study_report_view,
    validated_field_values_from_form,
)


PDF_RUNTIME_AVAILABLE = (
    importlib.util.find_spec("weasyprint") is not None
    and importlib.util.find_spec("fitz") is not None
)


def extract_csrf(html: str) -> str:
    """Extract the hidden CSRF token from rendered HTML."""
    marker = 'name="csrf_token" value="'
    start = html.index(marker) + len(marker)
    end = html.index('"', start)
    return html[start:end]


class ReportHtmlParser(HTMLParser):
    """Collect rendered identifiers and approved report controls."""

    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.report_controls: list[dict[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.append(attributes["id"])
        if "data-report-control" in attributes:
            self.report_controls.append(attributes)


def synthetic_clinical_row() -> dict[str, object]:
    """Build a fully populated synthetic clinical row."""
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
        "gx_rest_ph": "7.40",
        "gx_vo2_max_ph": "7.32",
        "gx_at_ve_per_vco2": "28",
        "gx_at_ve_per_vo2": "24",
    }


class AppConfigTests(unittest.TestCase):
    """Configuration and cookie policy tests."""

    def test_separate_database_urls_are_loaded_from_environment(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "development",
                "AUTH_DATABASE_URL": "postgresql://auth-db",
                "CLINICAL_DATABASE_URL": "postgresql://clinical-db",
                "SECRET_KEY": "test-secret",
                "SESSION_COOKIE_SECURE": "true",
            },
            clear=True,
        ):
            app = create_app()

        self.assertEqual(app.config["AUTH_DATABASE_URL"], "postgresql://auth-db")
        self.assertEqual(app.config["CLINICAL_DATABASE_URL"], "postgresql://clinical-db")
        self.assertTrue(app.config["SESSION_COOKIE_SECURE"])
        self.assertTrue(app.config["SESSION_COOKIE_HTTPONLY"])
        self.assertEqual(app.config["SESSION_COOKIE_SAMESITE"], "Lax")

    def test_testing_environment_does_not_require_databases(self) -> None:
        with patch.dict(os.environ, {"APP_ENV": "testing"}, clear=True):
            app = create_app("testing")

        self.assertTrue(app.config["TESTING"])
        self.assertIsNone(app.config["AUTH_DATABASE_URL"])
        self.assertIsNone(app.config["CLINICAL_DATABASE_URL"])
        self.assertFalse(app.config["SESSION_COOKIE_SECURE"])


class DatabaseConnectionTests(unittest.TestCase):
    """Request-scoped database connection lifecycle tests."""

    def test_connections_are_created_reused_and_closed_per_request(self) -> None:
        auth_connection = Mock(name="auth_connection")
        clinical_connection = Mock(name="clinical_connection")

        with patch.dict(
            os.environ,
            {
                "APP_ENV": "testing",
                "SECRET_KEY": "test-secret",
            },
            clear=True,
        ):
            app = create_app("testing")

        app.config["AUTH_DATABASE_URL"] = "postgresql://auth-db"
        app.config["CLINICAL_DATABASE_URL"] = "postgresql://clinical-db"

        with patch("db.psycopg.connect", side_effect=[auth_connection, clinical_connection]) as connect_mock:
            with app.test_request_context("/"):
                first_auth_connection = get_auth_db()
                second_auth_connection = get_auth_db()
                first_clinical_connection = get_clinical_db()
                second_clinical_connection = get_clinical_db()

                self.assertIs(first_auth_connection, second_auth_connection)
                self.assertIs(first_clinical_connection, second_clinical_connection)
                self.assertIsNot(first_auth_connection, first_clinical_connection)
                self.assertEqual(
                    connect_mock.call_args_list,
                    [
                        call("postgresql://auth-db"),
                        call(
                            "postgresql://clinical-db",
                            options="-c default_transaction_read_only=on",
                        ),
                    ],
                )

        auth_connection.close.assert_called_once()
        clinical_connection.close.assert_called_once()


class ClinicalRepositoryTests(unittest.TestCase):
    """Clinical repository compatibility tests."""

    def test_study_queries_use_the_authorized_columns_only_and_normal_transactions(self) -> None:
        connection = MagicMock(name="clinical_connection")
        transaction_context = MagicMock(name="transaction_context")
        cursor = MagicMock(name="cursor")

        cursor.description = [("patient_id_num",), ("visit_datetime",)]
        cursor.fetchall.return_value = [("12345678", "2026-08-20 17:43:15")]
        cursor.fetchone.return_value = ("12345678", "2026-08-20 17:43:15")
        connection.__enter__.return_value = connection
        connection.__exit__.return_value = None
        connection.transaction.return_value = transaction_context
        transaction_context.__enter__.return_value = transaction_context
        transaction_context.__exit__.return_value = None
        connection.cursor.return_value = cursor
        cursor.__enter__.return_value = cursor
        cursor.__exit__.return_value = None

        with patch("repositories.studies.get_clinical_db", return_value=connection):
            search_result = search_studies_by_patient_id_num("12345678")
            identity_result = get_study_by_identity("12345678", "2026-08-20 17:43:15")

        self.assertEqual(
            search_result,
            [{"patient_id_num": "12345678", "visit_datetime": "2026-08-20 17:43:15"}],
        )
        self.assertEqual(
            identity_result,
            {"patient_id_num": "12345678", "visit_datetime": "2026-08-20 17:43:15"},
        )
        self.assertEqual(STUDY_COLUMNS, ", ".join(CLINICAL_STUDY_COLUMN_KEYS))
        self.assertEqual(tuple(part.strip() for part in STUDY_COLUMNS.split(",")), CLINICAL_STUDY_COLUMN_KEYS)
        self.assertEqual(connection.transaction.call_args_list, [call(), call()])

        first_query, first_params = cursor.execute.call_args_list[0].args
        second_query, second_params = cursor.execute.call_args_list[1].args
        self.assertIn("SELECT", first_query)
        self.assertIn(f"SELECT {STUDY_COLUMNS}", first_query)
        self.assertIn("FROM staging.gx_analytics", first_query)
        self.assertIn("WHERE patient_id_num = %s", first_query)
        self.assertIn("ORDER BY visit_datetime DESC", first_query)
        self.assertNotIn("readonly", first_query.lower())
        self.assertEqual(first_params, ("12345678",))
        self.assertIn(f"SELECT {STUDY_COLUMNS}", second_query)
        self.assertIn("FROM staging.gx_analytics", second_query)
        self.assertIn("WHERE patient_id_num = %s", second_query)
        self.assertIn("AND visit_datetime = %s", second_query)
        self.assertNotIn("readonly", second_query.lower())
        self.assertEqual(second_params, ("12345678", datetime(2026, 8, 20, 17, 43, 15)))


class AuthUserRepositoryTests(unittest.TestCase):
    """Authentication reads include the optional textual signature profile."""

    def test_user_queries_left_join_signature_profile(self) -> None:
        connection = MagicMock(name="auth_connection")
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            (
                7,
                "synthetic-user",
                "Nombre de cuenta",
                "hash",
                True,
                datetime(2026, 1, 1),
                "Dra. Nombre de Firma",
                "Neumología",
                "RM 12345",
                "Instituto sintético",
            ),
            (
                7,
                "synthetic-user",
                "Nombre de cuenta",
                "hash",
                True,
                datetime(2026, 1, 1),
                None,
                None,
                None,
                None,
            ),
        ]
        with patch("repositories.users.get_auth_db", return_value=connection):
            profiled = get_user_by_username("synthetic-user")
            fallback = get_user_by_id(7)

        first_query, first_params = cursor.execute.call_args_list[0].args
        second_query, second_params = cursor.execute.call_args_list[1].args
        self.assertIn("LEFT JOIN ergo_app.user_signature_profiles", first_query)
        self.assertIn("WHERE u.username = %s", first_query)
        self.assertEqual(first_params, ("synthetic-user",))
        self.assertIn("LEFT JOIN ergo_app.user_signature_profiles", second_query)
        self.assertIn("WHERE u.id = %s", second_query)
        self.assertEqual(second_params, (7,))
        self.assertEqual(profiled.signature_name, "Dra. Nombre de Firma")
        self.assertEqual(profiled.profession_specialty, "Neumología")
        self.assertEqual(profiled.professional_registration, "RM 12345")
        self.assertEqual(profiled.institutional_line, "Instituto sintético")
        self.assertIsNone(fallback.signature_name)


class PdfAuditRepositoryTests(unittest.TestCase):
    """Transactional audit writes use only the authentication connection."""

    def _record(self) -> None:
        record_pdf_generation(
            patient_id_num="12345678",
            visit_datetime=datetime(2026, 8, 20, 17, 43, 15),
            user_id=7,
            username="synthetic-user",
            generated_at=datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc),
            filename="informe_gx_12345678_2026-08-20.pdf",
            pdf_sha256="a" * 64,
            pdf_size_bytes=321,
        )

    def test_audit_insert_is_parameterized_and_committed(self) -> None:
        connection = MagicMock(name="auth_connection")
        cursor = connection.cursor.return_value.__enter__.return_value
        with patch("repositories.report_audits.get_auth_db", return_value=connection):
            self._record()

        query, params = cursor.execute.call_args.args
        self.assertIn("INSERT INTO ergo_app.report_pdf_audits", query)
        self.assertEqual(
            params,
            (
                "12345678",
                datetime(2026, 8, 20, 17, 43, 15),
                7,
                "synthetic-user",
                datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc),
                "informe_gx_12345678_2026-08-20.pdf",
                "a" * 64,
                321,
            ),
        )
        connection.commit.assert_called_once_with()
        connection.rollback.assert_not_called()

    def test_audit_failure_rolls_back_and_does_not_commit(self) -> None:
        connection = MagicMock(name="auth_connection")
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.execute.side_effect = RuntimeError("insert failed")
        with (
            patch("repositories.report_audits.get_auth_db", return_value=connection),
            self.assertRaisesRegex(RuntimeError, "insert failed"),
        ):
            self._record()

        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()

    def test_audit_commit_failure_is_rolled_back(self) -> None:
        connection = MagicMock(name="auth_connection")
        connection.commit.side_effect = RuntimeError("commit failed")
        with (
            patch("repositories.report_audits.get_auth_db", return_value=connection),
            self.assertRaisesRegex(RuntimeError, "commit failed"),
        ):
            self._record()

        connection.commit.assert_called_once_with()
        connection.rollback.assert_called_once_with()

    def test_manual_migration_has_required_non_unique_indexes(self) -> None:
        sql = Path("migrations/002_create_report_pdf_audits.sql").read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS ergo_app.report_pdf_audits", sql)
        self.assertIn("report_pdf_audits_study_idx", sql)
        self.assertIn("report_pdf_audits_user_idx", sql)
        self.assertIn("report_pdf_audits_hash_idx", sql)
        self.assertNotRegex(sql, r"(?is)UNIQUE\s*\([^)]*pdf_sha256")

    def test_signature_profile_migration_is_manual_and_text_only(self) -> None:
        sql = Path("migrations/003_create_user_signature_profiles.sql").read_text(
            encoding="utf-8"
        )
        self.assertIn("CREATE TABLE IF NOT EXISTS ergo_app.user_signature_profiles", sql)
        self.assertIn("user_id BIGINT PRIMARY KEY", sql)
        self.assertIn("signature_name TEXT NOT NULL", sql)
        self.assertIn("profession_specialty TEXT NOT NULL", sql)
        self.assertIn("professional_registration TEXT NOT NULL", sql)
        self.assertIn("institutional_line TEXT", sql)
        self.assertNotRegex(sql, r"(?i)(bytea|signature_image|image_url)")


class PasswordTests(unittest.TestCase):
    """Argon2id hashing tests."""

    def test_hash_and_verify_uses_argon2id(self) -> None:
        hashed = hash_password("secret-password")
        self.assertTrue(hashed.startswith("$argon2id$"))
        self.assertTrue(verify_password(hashed, "secret-password"))
        self.assertFalse(verify_password(hashed, "wrong-password"))


class AuthFlowTests(unittest.TestCase):
    """Login, logout and protected page tests."""

    def setUp(self) -> None:
        self.env_patch = patch.dict(
            os.environ,
            {
                "APP_ENV": "testing",
                "SECRET_KEY": "test-secret",
            },
            clear=True,
        )
        self.env_patch.start()
        self.user = AuthUser(
            id=1,
            username="alice",
            full_name="Alice Example",
            password_hash=hash_password("secret-password"),
            active=True,
            signature_name="Dra. Alice Firma",
            profession_specialty="Medicina interna",
            professional_registration="RM 9876",
            institutional_line="Instituto sintético",
        )
        self.user_loader_patch = patch("app.get_user_by_id", return_value=self.user)
        self.user_loader_patch.start()
        self.app = create_app("testing")
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        self.user_loader_patch.stop()
        self.env_patch.stop()

    def test_home_is_protected(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_study_report_is_protected(self) -> None:
        response = self.client.get("/studies/preview")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_report_pdf_is_protected(self) -> None:
        response = self.client.post("/studies/report.pdf")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_login_rejects_invalid_credentials(self) -> None:
        login_page = self.client.get("/login")
        csrf_token = extract_csrf(login_page.get_data(as_text=True))

        with patch("routes.auth.authenticate_user", return_value=None):
            response = self.client.post(
                "/login",
                data={
                    "username": "alice",
                    "password": "wrong",
                    "csrf_token": csrf_token,
                },
            )

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Credenciales incorrectas.", body)

    def test_login_logout_flow(self) -> None:
        login_page = self.client.get("/login")
        csrf_token = extract_csrf(login_page.get_data(as_text=True))

        with patch("routes.auth.authenticate_user", return_value=self.user):
            response = self.client.post(
                "/login",
                data={
                    "username": "alice",
                    "password": "secret-password",
                    "csrf_token": csrf_token,
                },
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/", response.headers["Location"])
        with self.client.session_transaction() as session:
            self.assertEqual(
                session[SIGNATURE_PROFILE_SESSION_KEY],
                {
                    "name": "Dra. Alice Firma",
                    "profession_specialty": "Medicina interna",
                    "professional_registration": "RM 9876",
                    "institutional_line": "Instituto sintético",
                },
            )

        home_response = self.client.get("/")
        self.assertEqual(home_response.status_code, 200)
        body = home_response.get_data(as_text=True)
        self.assertIn("Búsqueda de estudios", body)

        logout_csrf = extract_csrf(body)
        logout_response = self.client.post(
            "/logout",
            data={"csrf_token": logout_csrf},
            follow_redirects=False,
        )
        self.assertEqual(logout_response.status_code, 302)
        self.assertIn("/login", logout_response.headers["Location"])
        with self.client.session_transaction() as session:
            self.assertNotIn(SIGNATURE_PROFILE_SESSION_KEY, session)

        post_logout_home = self.client.get("/")
        self.assertEqual(post_logout_home.status_code, 302)


class SearchAndDraftTests(unittest.TestCase):
    """Search and draft flow with simulated repositories."""

    def setUp(self) -> None:
        self.env_patch = patch.dict(
            os.environ,
            {
                "APP_ENV": "testing",
                "SECRET_KEY": "test-secret",
            },
            clear=True,
        )
        self.env_patch.start()
        self.user = AuthUser(
            id=1,
            username="alice",
            full_name="Alice Example",
            password_hash=hash_password("secret-password"),
            active=True,
        )
        self.user_loader_patch = patch("app.get_user_by_id", return_value=self.user)
        self.user_loader_patch.start()
        self.app = create_app("testing")
        self.client = self.app.test_client()
        login_page = self.client.get("/login")
        csrf_token = extract_csrf(login_page.get_data(as_text=True))
        with patch("routes.auth.authenticate_user", return_value=self.user):
            self.client.post(
                "/login",
                data={
                    "username": "alice",
                    "password": "secret-password",
                    "csrf_token": csrf_token,
                },
            )

    def tearDown(self) -> None:
        self.user_loader_patch.stop()
        self.env_patch.stop()

    def _search_page_csrf(self) -> str:
        response = self.client.get("/")
        return extract_csrf(response.get_data(as_text=True))

    def _select_study(self, row: dict[str, object], submitted_values: dict[str, str] | None = None):
        with patch("services.search.get_study_by_identity", return_value=row):
            return self.client.post(
                "/studies/select",
                data={
                    "csrf_token": self._search_page_csrf(),
                    "study_patient_id_num": str(row["patient_id_num"]),
                    "study_visit_datetime": str(row["visit_datetime"]),
                    **(submitted_values or {}),
                },
            )

    def test_search_rejects_empty_id(self) -> None:
        csrf_token = self._search_page_csrf()
        response = self.client.post(
            "/",
            data={"patient_id_num": "   ", "csrf_token": csrf_token},
        )
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Introduce un ID de paciente válido.", body)

    def test_search_displays_studies_without_visible_study_id(self) -> None:
        csrf_token = self._search_page_csrf()
        results = SearchResult(
            studies=[
                StudySummary(
                    patient_id_num="12345678",
                    full_name="García, Ana María",
                    visit_datetime="2026-08-20 17:43:15",
                ),
                StudySummary(
                    patient_id_num="12345678",
                    full_name="García, Ana María",
                    visit_datetime="2026-08-19 09:00:00",
                ),
            ],
            patient_id_num="12345678",
        )

        with patch("routes.home.search_by_patient_id_num", return_value=results):
            response = self.client.post(
                "/",
                data={"patient_id_num": "12345678", "csrf_token": csrf_token},
            )

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("García, Ana María", body)
        self.assertIn('name="study_patient_id_num" value="12345678"', body)
        self.assertIn('name="study_visit_datetime" value="2026-08-20 17:43:15"', body)
        self.assertNotIn("pat_visit_id", body)
        self.assertLess(body.index("2026-08-20 17:43:15"), body.index("2026-08-19 09:00:00"))

    def test_report_renders_approved_form_and_selected_gx_values(self) -> None:
        row = synthetic_clinical_row()
        response = self._select_study(
            row,
            submitted_values={"conclusiones_definitivas": "Conclusión de prueba."},
        )

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Borrador del informe", body)
        self.assertIn("Formulario clínico compacto", body)
        self.assertIn('id="sticky-patient-name">Ana María García<', body)
        self.assertIn('name="study_patient_id_num" value="12345678"', body)
        self.assertIn('name="study_visit_datetime" value="2026-08-20 17:43:15"', body)
        self.assertIn("Actualizar borrador", body)
        self.assertIn(">Ver informe<", body)
        self.assertIn(">Mostrar detalle<", body)
        self.assertIn(">Generar PDF<", body)
        self.assertIn("Confirmar generación del informe", body)
        self.assertIn(
            "Se generará el PDF con la información que aparece actualmente en el informe. ¿Deseas continuar?",
            body,
        )
        self.assertEqual(body.count('class="clinical-section"'), 6)
        self.assertIn('id="gx_vo2_max_work_watts" name="gx_vo2_max_work_watts" value="150"', body)
        self.assertIn('id="gx_at_ve_per_vco2" name="gx_at_ve_per_vco2" value="28"', body)
        self.assertIn('id="porc_fc_maxima" name="porc_fc_maxima" value="94.12"', body)
        self.assertIn('id="conclusiones_definitivas" name="conclusiones_definitivas"', body)
        self.assertIn("Conclusión de prueba.", body)
        self.assertIn('src="/static/study_report.js"', body)
        self.assertIn('href="/static/study_report.css"', body)
        with self.client.session_transaction() as session:
            self.assertNotIn("draft", session)
            self.assertNotIn("study", session)

    def test_draft_rejects_missing_study(self) -> None:
        csrf_token = self._search_page_csrf()
        with patch("services.search.get_study_by_identity", return_value=None):
            response = self.client.post(
                "/studies/select",
                data={
                    "csrf_token": csrf_token,
                    "study_patient_id_num": "12345678",
                    "study_visit_datetime": "2026-08-20 17:43:15",
                },
            )

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("El estudio ya no está disponible.", body)

    def test_select_uses_the_exact_unique_study_identity(self) -> None:
        row = synthetic_clinical_row()
        with patch("services.search.get_study_by_identity", return_value=row) as lookup:
            response = self.client.post(
                "/studies/select",
                data={
                    "csrf_token": self._search_page_csrf(),
                    "study_patient_id_num": "12345678",
                    "study_visit_datetime": "2026-08-20 17:43:15",
                },
            )

        self.assertEqual(response.status_code, 200)
        lookup.assert_called_once_with("12345678", "2026-08-20 17:43:15")
        self.assertIn('id="diagnosis" name="diagnosis" value="DX"', response.get_data(as_text=True))

    def test_select_rejects_invalid_csrf_before_clinical_lookup(self) -> None:
        with patch("services.search.get_study_by_identity") as lookup:
            response = self.client.post(
                "/studies/select",
                data={
                    "csrf_token": "invalid",
                    "study_patient_id_num": "12345678",
                    "study_visit_datetime": "2026-08-20 17:43:15",
                },
            )

        self.assertEqual(response.status_code, 400)
        lookup.assert_not_called()

    def test_preview_route_uses_the_same_approved_layout(self) -> None:
        response = self.client.get("/studies/preview")

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Vista previa con datos sintéticos", body)
        self.assertIn('id="study-report-form"', body)
        self.assertIn('id="sticky-patient-name">Ana María García<', body)
        self.assertIn('name="study_patient_id_num" value="12345678"', body)
        self.assertEqual(body.count('class="clinical-section"'), 6)
        self.assertLess(body.index(">Capacidad funcional<"), body.index(">Respuesta cardiovascular<"))

    def test_preview_and_normal_share_the_same_layout_structure(self) -> None:
        normal_body = self._select_study(synthetic_clinical_row()).get_data(as_text=True)
        preview_body = self.client.get("/studies/preview").get_data(as_text=True)

        def layout_signature(body: str) -> list[str]:
            return re.findall(
                r'class="([^"]*(?:clinical-section|group-grid|group--|clinical-report)[^"]*)"',
                body,
            )

        self.assertEqual(layout_signature(normal_body), layout_signature(preview_body))
        for key in REPORT_CONTROL_IDS:
            self.assertEqual(normal_body.count(f'name="{key}"'), 1, key)
            self.assertEqual(preview_body.count(f'name="{key}"'), 1, key)

    def test_report_has_87_matching_controls_and_no_duplicate_ids(self) -> None:
        body = self._select_study(synthetic_clinical_row()).get_data(as_text=True)
        parser = ReportHtmlParser()
        parser.feed(body)

        self.assertEqual(len(parser.report_controls), 87)
        self.assertEqual(
            {control["id"] for control in parser.report_controls},
            set(REPORT_CONTROL_IDS),
        )
        self.assertTrue(all(control["id"] == control["name"] for control in parser.report_controls))
        self.assertEqual(len(parser.ids), len(set(parser.ids)))

    def test_conclusions_and_gx_correction_survive_ephemeral_post(self) -> None:
        response = self._select_study(
            synthetic_clinical_row(),
            submitted_values={
                "conclusiones_definitivas": "Texto <clínico>",
                "gx_vo2_max_work_watts": "151",
            },
        )
        body = response.get_data(as_text=True)

        self.assertIn("Texto &lt;clínico&gt;", body)
        self.assertIn('id="gx_vo2_max_work_watts" name="gx_vo2_max_work_watts" value="151"', body)
        self.assertIn("GX · Editado", body)
        self.assertIn('data-original-value="150"', body)

    def test_zero_and_null_render_without_fallback_values(self) -> None:
        row = synthetic_clinical_row()
        row.update({"weight": Decimal("0"), "diagnosis": None, "gx_rest_hr_bpm": 0})
        body = self._select_study(row).get_data(as_text=True)

        self.assertIn('id="weight" name="weight" value="0"', body)
        self.assertIn('id="gx_rest_hr_bpm" name="gx_rest_hr_bpm" value="0"', body)
        self.assertIn('id="diagnosis" name="diagnosis" value=""', body)

    def test_detail_contains_exact_gx_sources_and_manual_labels(self) -> None:
        body = self._select_study(synthetic_clinical_row()).get_data(as_text=True)

        self.assertIn('title="gx_vo2_max_hr_bpm, gx_predicted_hr_bpm"', body)
        self.assertIn('title="gx_at_ve_per_vco2">gx_at_ve_per_vco2<', body)
        self.assertIn('data-origin="MANUAL"', body)
        self.assertIn('class="field-origin field-origin--manual">MANUAL<', body)

    def test_pdf_response_audits_the_exact_delivered_bytes_and_current_values(self) -> None:
        row = synthetic_clinical_row()
        pdf_bytes = b"%PDF-1.7\nsynthetic selectable report\n%%EOF"
        generated_at = datetime(2026, 8, 24, 15, 30, tzinfo=timezone.utc)
        submitted = {
            "gx_vo2_max_work_watts": "151",
            "hb": "0",
            "conclusiones_definitivas": "Conclusión actual",
            "signature_name": "Nombre inyectado desde formulario",
        }
        with (
            patch("services.search.get_study_by_identity", return_value=row) as lookup,
            patch("routes.studies.generate_report_pdf", return_value=pdf_bytes) as renderer,
            patch("routes.studies.record_pdf_generation") as audit,
            patch("routes.studies._generation_instant", return_value=generated_at),
        ):
            response = self.client.post(
                "/studies/report.pdf",
                data={
                    "csrf_token": self._search_page_csrf(),
                    "study_patient_id_num": "12345678",
                    "study_visit_datetime": "2026-08-20 17:43:15",
                    **submitted,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, pdf_bytes)
        self.assertEqual(response.headers["Content-Type"], "application/pdf")
        self.assertEqual(
            response.headers["Content-Disposition"],
            'attachment; filename="informe_gx_12345678_2026-08-20.pdf"',
        )
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        lookup.assert_called_once_with("12345678", "2026-08-20 17:43:15")
        rendered_report, rendered_narratives = renderer.call_args.args
        self.assertEqual(rendered_report.field("gx_vo2_max_work_watts").value, "151")
        self.assertTrue(rendered_report.field("gx_vo2_max_work_watts").edited)
        self.assertEqual(rendered_report.field("hb").value, "0")
        self.assertIn("Conclusión actual", rendered_narratives[-1].fragments)
        self.assertEqual(renderer.call_args.kwargs["generated_at"], generated_at)
        self.assertEqual(
            renderer.call_args.kwargs["signature_profile"],
            SignatureProfile(name="Alice Example"),
        )
        audit_kwargs = audit.call_args.kwargs
        self.assertEqual(audit_kwargs["patient_id_num"], "12345678")
        self.assertEqual(audit_kwargs["visit_datetime"], datetime(2026, 8, 20, 17, 43, 15))
        self.assertEqual(audit_kwargs["user_id"], 1)
        self.assertEqual(audit_kwargs["username"], "alice")
        self.assertEqual(audit_kwargs["pdf_sha256"], hashlib.sha256(response.data).hexdigest())
        self.assertEqual(audit_kwargs["pdf_size_bytes"], len(response.data))
        self.assertEqual(audit_kwargs["filename"], "informe_gx_12345678_2026-08-20.pdf")
        self.assertIs(audit_kwargs["generated_at"], renderer.call_args.kwargs["generated_at"])
        self.assertEqual(audit_kwargs["generated_at"], generated_at)

    def test_pdf_rejects_csrf_before_study_render_and_audit(self) -> None:
        with (
            patch("services.search.get_study_by_identity") as lookup,
            patch("routes.studies.generate_report_pdf") as renderer,
            patch("routes.studies.record_pdf_generation") as audit,
        ):
            response = self.client.post(
                "/studies/report.pdf",
                data={
                    "csrf_token": "invalid",
                    "study_patient_id_num": "12345678",
                    "study_visit_datetime": "2026-08-20 17:43:15",
                },
            )

        self.assertEqual(response.status_code, 400)
        lookup.assert_not_called()
        renderer.assert_not_called()
        audit.assert_not_called()

    def test_pdf_rejects_missing_study_before_render_and_audit(self) -> None:
        with (
            patch("services.search.get_study_by_identity", return_value=None),
            patch("routes.studies.generate_report_pdf") as renderer,
            patch("routes.studies.record_pdf_generation") as audit,
        ):
            response = self.client.post(
                "/studies/report.pdf",
                data={
                    "csrf_token": self._search_page_csrf(),
                    "study_patient_id_num": "12345678",
                    "study_visit_datetime": "2026-08-20 17:43:15",
                },
            )

        self.assertEqual(response.status_code, 404)
        renderer.assert_not_called()
        audit.assert_not_called()

    def test_pdf_is_not_delivered_when_audit_fails(self) -> None:
        pdf_bytes = b"%PDF-1.7\nnot delivered\n%%EOF"
        with (
            patch("services.search.get_study_by_identity", return_value=synthetic_clinical_row()),
            patch("routes.studies.generate_report_pdf", return_value=pdf_bytes),
            patch(
                "routes.studies.record_pdf_generation",
                side_effect=RuntimeError("audit unavailable"),
            ) as audit,
            self.assertRaisesRegex(RuntimeError, "audit unavailable"),
        ):
            self.client.post(
                "/studies/report.pdf",
                data={
                    "csrf_token": self._search_page_csrf(),
                    "study_patient_id_num": "12345678",
                    "study_visit_datetime": "2026-08-20 17:43:15",
                    "conclusiones_definitivas": "No entregar",
                },
            )
        audit.assert_called_once()


class DraftMappingTests(unittest.TestCase):
    """Service-level draft mapping tests with synthetic data."""

    def test_empty_results_are_pending_and_editable(self) -> None:
        row = {key: "" for key in CLINICAL_STUDY_COLUMN_KEYS}
        draft = build_study_draft_view(row)

        self.assertEqual(draft.global_completed_count, 0)
        self.assertEqual(draft.global_total_count, 44)
        self.assertEqual([section.completed_count for section in draft.sections], [0, 0, 0, 0, 0, 0, 0, 0])
        self.assertTrue(all(element.status_label == "Pendiente" for section in draft.sections for element in section.elements))
        self.assertTrue(all(value.input_type in {"text", "textarea"} for section in draft.sections for element in section.elements for value in element.values))
        self.assertEqual(draft.sections[0].elements[0].spec.title, "Motivo de la remisión")
        self.assertEqual(draft.sections[0].elements[0].values[0].presentation_width, "full")
        self.assertEqual(draft.sections[0].elements[1].spec.title, "Médico remitente")
        self.assertEqual(draft.sections[0].elements[1].values[0].presentation_width, "long")
        self.assertEqual(draft.sections[1].elements[0].spec.presentation_layout, "grouped")
        self.assertEqual(draft.sections[2].elements[0].spec.presentation_layout, "grouped")
        self.assertEqual(draft.sections[-1].elements[0].spec.presentation_layout, "full")
        self.assertEqual(draft.sections[-1].elements[0].values[0].presentation_width, "full")

    def test_full_study_counts_and_gx_statuses(self) -> None:
        row = synthetic_clinical_row()
        draft = build_study_draft_view(row)

        self.assertEqual(draft.global_completed_count, 28)
        self.assertEqual(draft.global_total_count, 44)
        self.assertEqual([section.completed_count for section in draft.sections], [11, 1, 1, 3, 4, 6, 2, 0])
        self.assertEqual(draft.lookup_patient_full_name, "Ana María García")
        self.assertEqual(draft.sections[0].elements[0].status_label, "Pendiente")
        self.assertEqual(draft.sections[2].elements[0].status_label, "Diligenciado desde GX")
        self.assertEqual(draft.sections[3].elements[0].status_label, "Diligenciado desde GX")
        cardiovascular = draft.sections[3]
        first_cardio_row = cardiovascular.elements[0]
        self.assertEqual(cardiovascular.spec.order, 4)
        self.assertEqual(first_cardio_row.spec.title, "")
        self.assertEqual(first_cardio_row.spec.presentation_layout, "grouped")
        self.assertEqual(
            [value.label for value in first_cardio_row.values],
            ["Ritmo", "FC inicial", "FC final"],
        )
        self.assertEqual(first_cardio_row.values[0].source_state, "absent")
        self.assertEqual([value.source_state for value in first_cardio_row.values[1:]], ["gx", "gx"])
        self.assertEqual(draft.sections[1].elements[0].values[1].value, "172")
        self.assertEqual(
            draft.sections[2].elements[0].narrative_text,
            "Protocolo: duración 12 min, carga máxima 150 W y RER 0.98.",
        )
        self.assertEqual(render_narrative_section(draft.sections[2]), "La prueba tuvo una duración de 12 minutos, alcanzó una carga máxima de 150 W y registró un RER de 0.98.")

    def test_manual_override_is_ephemeral_and_zero_is_preserved(self) -> None:
        row = synthetic_clinical_row()
        draft = build_study_draft_view(
            row,
            submitted_values={
                "tbco_prod": "0",
                "pk_yrs": "0",
                "gx_vo2_max_rer": "0",
                "conclusions": "Primera línea\n\nSegunda línea",
            },
        )

        identification = draft.sections[0]
        protocol = draft.sections[2]
        conclusions = draft.sections[-1]

        self.assertEqual(identification.elements[6].values[0].value, "0")
        self.assertEqual(identification.elements[7].values[0].value, "0")
        self.assertEqual(protocol.elements[0].values[2].value, "0")
        self.assertEqual(protocol.elements[0].values[2].initial_value, "0.98")
        self.assertEqual(protocol.elements[0].status_label, "Modificado")
        self.assertIn("Tabaquismo: 0.", identification.elements[6].narrative_text)
        self.assertIn("Índice paquetes-año: 0.", identification.elements[7].narrative_text)
        self.assertIn("RER 0", protocol.elements[0].narrative_text)
        self.assertIn("tabaquismo 0", render_narrative_section(identification))
        self.assertIn("índice paquetes-año 0", render_narrative_section(identification))
        self.assertIn("RER de 0", render_narrative_section(protocol))
        self.assertEqual(render_narrative_section(conclusions), "Primera línea\n\nSegunda línea")
        self.assertEqual(
            field_values_from_form([("unknown", "x"), ("diagnosis", "DX"), ("conclusions", "Notas")]),
            {"diagnosis": "DX", "conclusions": "Notas"},
        )

    def test_documentation_generation_matches_the_declarative_spec(self) -> None:
        documentation = generate_structure_markdown()
        self.assertIn("## 1. Antecedentes clínicos y remisión", documentation)
        self.assertIn("## 4. Respuesta cardiovascular", documentation)
        self.assertIn("## 9. Conclusiones", documentation)
        self.assertIn("## Metadatos de Elaboración", documentation)
        self.assertIn("hoja clínica en paneles", documentation)
        self.assertIn("* Presentación de fila: grouped", documentation)
        self.assertIn("* Anchuras semánticas: patient_first_name=flex", documentation)
        self.assertEqual(len(REPORT_SECTION_SPECS), 8)
        self.assertEqual(sum(len(section.elements) for section in REPORT_SECTION_SPECS), 44)


class ApprovedReportMappingTests(unittest.TestCase):
    """Mapping, provenance, derived-value and precedence tests for the 87 controls."""

    def test_all_controls_have_one_declared_origin(self) -> None:
        gx_keys = set(DIRECT_FIELD_SOURCES) | set(DERIVED_FIELD_SOURCES)
        self.assertEqual(len(REPORT_CONTROL_IDS), 87)
        self.assertEqual(len(set(REPORT_CONTROL_IDS)), 87)
        self.assertFalse(set(DIRECT_FIELD_SOURCES) & set(DERIVED_FIELD_SOURCES))
        self.assertFalse(gx_keys & MANUAL_CONTROL_IDS)
        self.assertEqual(gx_keys | MANUAL_CONTROL_IDS, set(REPORT_CONTROL_IDS))

    def test_direct_derived_and_manual_values_are_resolved(self) -> None:
        row = synthetic_clinical_row()
        report = build_study_report_view(
            row,
            submitted_values={
                "hb": "13.2",
                "conclusiones_definitivas": "Conclusión manual",
                "diagnosis": "Corrección explícita",
            },
        )

        self.assertEqual(report.field("gx_vo2_max_work_watts").value, "150")
        self.assertEqual(report.field("porc_fc_maxima").value, "94.12")
        self.assertEqual(report.field("hb").value, "13.2")
        self.assertEqual(report.field("conclusiones_definitivas").value, "Conclusión manual")
        self.assertEqual(report.field("diagnosis").value, "Corrección explícita")
        self.assertEqual(report.field("diagnosis").original_value, "DX")
        self.assertTrue(report.field("diagnosis").edited)
        self.assertEqual(report.field("diagnosis").origin_label, "GX · Editado")
        self.assertEqual(report.field("height").value, "172")

    def test_derived_formulas_use_decimal_and_handle_missing_or_zero_denominators(self) -> None:
        derived = build_derived_values(synthetic_clinical_row())
        self.assertEqual(derived["porc_fc_maxima"], "94.12")
        self.assertEqual(derived["porc_o2_predicho"], "90")
        self.assertEqual(derived["porc_vo2_predicho"], "90")
        self.assertEqual(derived["carga_max_w"], "88.24")
        self.assertEqual(derived["porc_pred_o2_latido_6"], "114.29")
        self.assertEqual(derived["reserva_respiratoria_pico_l"], "15")
        self.assertIs(derived["medicion_gases"], True)

        invalid = synthetic_clinical_row()
        invalid.update(
            {
                "gx_predicted_hr_bpm": Decimal("0"),
                "gx_predicted_vo2_ml_per_min": None,
                "gx_predicted_work_watts": "0",
                "gx_predicted_vo2_per_hr_ml_per_beat": "",
                "pf_pre_mvv_l_per_min": None,
                "gx_rest_ph": None,
            }
        )
        missing = build_derived_values(invalid)
        for key in (
            "porc_fc_maxima",
            "porc_o2_predicho",
            "porc_vo2_predicho",
            "carga_max_w",
            "porc_pred_o2_latido_6",
            "reserva_respiratoria_pico_l",
        ):
            self.assertEqual(missing[key], "", key)
        self.assertIs(missing["medicion_gases"], False)

    def test_zero_is_preserved_and_null_is_empty(self) -> None:
        row = synthetic_clinical_row()
        row.update({"weight": Decimal("0"), "diagnosis": None, "gx_rest_hr_bpm": 0})
        report = build_study_report_view(row)

        self.assertEqual(report.field("weight").value, "0")
        self.assertEqual(report.field("gx_rest_hr_bpm").value, "0")
        self.assertEqual(report.field("diagnosis").value, "")

    def test_manual_controls_do_not_receive_gx_or_demo_defaults(self) -> None:
        report = build_study_report_view(synthetic_clinical_row())
        self.assertTrue(all(report.field(key).value == "" for key in MANUAL_CONTROL_IDS))

    def test_provenance_lists_exact_source_columns(self) -> None:
        report = build_study_report_view(synthetic_clinical_row())
        self.assertEqual(
            report.field("porc_fc_maxima").source_columns,
            ("gx_vo2_max_hr_bpm", "gx_predicted_hr_bpm"),
        )
        self.assertEqual(
            report.field("gx_at_ve_per_vco2").source_columns,
            ("gx_at_ve_per_vco2",),
        )
        self.assertEqual(report.field("hb").source_columns, ())
        self.assertEqual(report.field("hb").origin, "MANUAL")
        self.assertEqual(report.field("gx_at_ve_per_vco2").origin, "GX")

    def test_pdf_form_validation_rejects_duplicate_controls(self) -> None:
        form = MultiDict(
            [
                ("study_patient_id_num", "12345678"),
                ("conclusiones_definitivas", "Primera"),
                ("conclusiones_definitivas", "Segunda"),
            ]
        )
        with self.assertRaisesRegex(ValueError, "duplicado"):
            validated_field_values_from_form(form)

    def test_server_narratives_match_visible_threshold_and_escaping_rules(self) -> None:
        report = build_study_report_view(
            {},
            submitted_values={
                "conclusiones_definitivas": "<img src=x onerror=alert(1)>",
                "umbral_anaerobio_alcanzado": "NO",
                "gx_at_ve_per_vco2": "99",
                "gx_at_ve_per_vo2": "88",
                "gx_vo2_max_ve_per_mvv_pct": "58",
                "hb": "0",
            },
        )
        narratives = build_report_narratives(report)

        self.assertEqual(tuple(section.title for section in narratives), SECTION_TITLES)
        self.assertIn("Hb: 0 g/dL", narratives[0].fragments)
        ventilatory = " ".join(narratives[4].fragments)
        self.assertIn("La relación VE/VVM fue de 58%", ventilatory)
        self.assertIn("no aplica", ventilatory)
        self.assertNotIn("99", ventilatory)
        self.assertEqual(
            narratives[5].fragments[-1],
            "<img src=x onerror=alert(1)>",
        )

        reached = build_study_report_view(
            {},
            submitted_values={
                "umbral_anaerobio_alcanzado": "SÍ",
                "gx_at_ve_per_vco2": "99",
                "gx_at_ve_per_vo2": "88",
            },
        )
        reached_text = " ".join(build_report_narratives(reached)[4].fragments)
        self.assertIn("fue de 99", reached_text)
        self.assertIn("fue de 88", reached_text)
        self.assertNotIn("no aplica", reached_text)

    def test_pdf_footer_time_uses_america_bogota(self) -> None:
        self.assertEqual(
            format_generation_time_bogota(
                datetime(2026, 8, 24, 15, 30, 45, tzinfo=timezone.utc)
            ),
            "2026-08-24 10:30:45",
        )
        with self.assertRaisesRegex(ValueError, "zona horaria"):
            format_generation_time_bogota(datetime(2026, 8, 24, 15, 30, 45))


@unittest.skipUnless(PDF_RUNTIME_AVAILABLE, "WeasyPrint/PyMuPDF no instalados")
class PdfRenderingTests(unittest.TestCase):
    """Render and inspect a synthetic selectable A4 report."""

    def setUp(self) -> None:
        self.env_patch = patch.dict(
            os.environ,
            {"APP_ENV": "testing", "SECRET_KEY": "test-secret"},
            clear=True,
        )
        self.env_patch.start()
        self.app = create_app("testing")

    def tearDown(self) -> None:
        self.env_patch.stop()

    def test_pdf_contains_only_report_content_and_escapes_dynamic_text(self) -> None:
        import fitz

        long_conclusions = "\n\n".join(
            f"Conclusión sintética {index}. Texto extendido para validar la paginación del documento."
            for index in range(1, 13)
        )
        report = build_study_report_view(
            synthetic_clinical_row(),
            submitted_values={
                "motivo_remision": "Control manual",
                "gx_vo2_max_work_watts": "151",
                "hb": "0",
                "umbral_anaerobio_alcanzado": "NO",
                "conclusiones_definitivas": (
                    "Conclusión <script>alert(1)</script>\n\n" + long_conclusions
                ),
            },
        )
        narratives = build_report_narratives(report)
        signature = SignatureProfile(
            name="Dra. Profesional Sintética",
            profession_specialty="Neumología clínica",
            professional_registration="RM 12345",
            institutional_line="Instituto Nacional Sintético",
        )
        generated_at = datetime(2026, 8, 24, 15, 30, 45, tzinfo=timezone.utc)

        with TemporaryDirectory() as temp_dir:
            asset_dir = Path(temp_dir)
            wide_asset = asset_dir / "wide.svg"
            compact_asset = asset_dir / "compact.svg"
            wide_asset.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="178mm" height="22mm" viewBox="0 0 1780 220">'
                '<rect width="1780" height="220" fill="#dcefed"/><text x="40" y="135" font-size="70">MEMBRETE ANCHO</text></svg>',
                encoding="utf-8",
            )
            compact_asset.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="178mm" height="10mm" viewBox="0 0 1780 100">'
                '<rect width="1780" height="100" fill="#e7e0f4"/><text x="40" y="68" font-size="42">MEMBRETE COMPACTO</text></svg>',
                encoding="utf-8",
            )
            with (
                self.app.app_context(),
                patch("services.pdf_report.WIDE_LETTERHEAD_PATH", wide_asset),
                patch("services.pdf_report.COMPACT_LETTERHEAD_PATH", compact_asset),
            ):
                pdf_bytes = generate_report_pdf(
                    report,
                    narratives,
                    generated_at=generated_at,
                    signature_profile=signature,
                )

        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
        self.assertTrue(pdf_bytes.rstrip().endswith(b"%%EOF"))
        self.assertNotIn(b"/JavaScript", pdf_bytes)
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
        self.assertGreaterEqual(document.page_count, 2)
        pages_text = [page.get_text() for page in document]
        self.assertTrue(all(text.strip() for text in pages_text))
        for page in document:
            self.assertAlmostEqual(page.rect.width, 595.28, delta=1)
            self.assertAlmostEqual(page.rect.height, 841.89, delta=1)
        normalized_text = re.sub(r"\s+", " ", " ".join(pages_text))
        for title in SECTION_TITLES:
            self.assertIn(title.upper(), normalized_text)
        self.assertIn("Motivo de la remisión: Control manual", normalized_text)
        self.assertIn("llegando a 151 vatios", normalized_text)
        self.assertIn("Hb: 0 g/dL", normalized_text)
        self.assertIn("Conclusión <script>alert(1)</script>", normalized_text)
        self.assertIn("MEMBRETE ANCHO", pages_text[0])
        self.assertNotIn("MEMBRETE COMPACTO", pages_text[0])
        for page_number, page_text in enumerate(pages_text, start=1):
            self.assertIn("Generado con ErgoApp INO v1.0 · 2026-08-24 10:30:45", page_text)
            self.assertIn(f"Página {page_number} de {document.page_count}", page_text)
            if page_number > 1:
                self.assertIn("MEMBRETE COMPACTO", page_text)
                self.assertNotIn("MEMBRETE ANCHO", page_text)
                self.assertIn("Ana María García", page_text)
                self.assertIn("ID 12345678", page_text)
                self.assertIn("Fecha 2026-08-20 17:43:15", page_text)

        signature_terms = (
            "Dra. Profesional Sintética",
            "Neumología clínica",
            "Registro profesional: RM 12345",
            "Instituto Nacional Sintético",
        )
        signature_pages = {
            index
            for index, page_text in enumerate(pages_text)
            if any(term in page_text for term in signature_terms)
        }
        self.assertEqual(len(signature_pages), 1)
        signature_page_text = pages_text[signature_pages.pop()]
        for term in signature_terms:
            self.assertIn(term, signature_page_text)
        for excluded in (
            "Actualizar borrador",
            "Generar PDF",
            "Mostrar detalle",
            "GX · Editado",
            "MANUAL",
            "gx_vo2_max_work_watts",
        ):
            self.assertNotIn(excluded, normalized_text)

    def test_pdf_renders_when_both_letterhead_files_are_missing(self) -> None:
        report = build_study_report_view(synthetic_clinical_row())
        with (
            TemporaryDirectory() as temp_dir,
            self.app.app_context(),
            patch(
                "services.pdf_report.WIDE_LETTERHEAD_PATH",
                Path(temp_dir) / "missing-wide.svg",
            ),
            patch(
                "services.pdf_report.COMPACT_LETTERHEAD_PATH",
                Path(temp_dir) / "missing-compact.svg",
            ),
        ):
            pdf_bytes = generate_report_pdf(
                report,
                build_report_narratives(report),
                generated_at=datetime(2026, 8, 24, 15, 30, tzinfo=timezone.utc),
                signature_profile=SignatureProfile(name="Alice Example"),
            )

        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))


if __name__ == "__main__":
    unittest.main()
