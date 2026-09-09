"""Integration coverage against the explicitly configured isolated app database."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import os
import subprocess
import sys
from unittest import TestCase, skipUnless
from unittest.mock import patch

import psycopg

from app import create_app
from repositories.drafts import (
    EN_FIRMA,
    PRELIMINAR,
    PRELIMINAR_BLOQUEADO,
    DraftOwnershipError,
    create_next_version,
    get_draft,
    get_report_version,
    record_pdf_event,
    release_from_signature,
    sign_draft,
    take_for_signature,
)
from services.draft_workflow import open_persistent_draft
from services.draft_workflow import report_view_for_draft, report_view_for_version, save_draft_values
from services.passwords import hash_password
from services.report_controls import AUXILIAR, COORDINADORA, MEDICO


TEST_DATABASE_URL = os.getenv("INFORMEGX_TEST_DATABASE_URL")
DESTRUCTIVE_TEST_OPT_IN_ENV = "INFORMEGX_ALLOW_DESTRUCTIVE_TESTS"


def destructive_test_database_url(environ: dict[str, str] | None = None) -> str:
    """Return a deliberately confirmed, clearly isolated PostgreSQL test URL."""
    environment = os.environ if environ is None else environ
    database_url = environment.get("INFORMEGX_TEST_DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("INFORMEGX_TEST_DATABASE_URL debe configurarse.")
    try:
        database_name = psycopg.conninfo.conninfo_to_dict(database_url).get("dbname", "")
    except psycopg.ProgrammingError as error:
        raise RuntimeError("INFORMEGX_TEST_DATABASE_URL no contiene una conexión PostgreSQL válida.") from error
    if not database_name.endswith("_test"):
        raise RuntimeError(
            "INFORMEGX_TEST_DATABASE_URL debe apuntar a una base PostgreSQL cuyo nombre termine en _test."
        )
    if environment.get(DESTRUCTIVE_TEST_OPT_IN_ENV) != "1":
        raise RuntimeError(
            f"Debe confirmar las pruebas destructivas con {DESTRUCTIVE_TEST_OPT_IN_ENV}=1."
        )
    return database_url


def destructive_test_configuration_error() -> str | None:
    try:
        destructive_test_database_url()
    except RuntimeError as error:
        return str(error)
    return None


DESTRUCTIVE_TEST_CONFIGURATION_ERROR = destructive_test_configuration_error()


class PostgresDestructiveSafetyTests(TestCase):
    def test_rejects_a_database_name_without_test_suffix(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "termine en _test"):
            destructive_test_database_url(
                {
                    "INFORMEGX_TEST_DATABASE_URL": "postgresql://localhost/informegx",
                    DESTRUCTIVE_TEST_OPT_IN_ENV: "1",
                }
            )

    def test_rejects_missing_explicit_destructive_opt_in(self) -> None:
        with self.assertRaisesRegex(RuntimeError, DESTRUCTIVE_TEST_OPT_IN_ENV):
            destructive_test_database_url(
                {"INFORMEGX_TEST_DATABASE_URL": "postgresql://localhost/informegx_test"}
            )

    def test_accepts_an_explicitly_enabled_isolated_database(self) -> None:
        database_url = "postgresql://localhost/informegx_test"
        self.assertEqual(
            destructive_test_database_url(
                {
                    "INFORMEGX_TEST_DATABASE_URL": database_url,
                    DESTRUCTIVE_TEST_OPT_IN_ENV: "1",
                }
            ),
            database_url,
        )


def clinical_row() -> dict[str, object]:
    return {
        "patient_id_num": "90000001", "patient_first_name": "Ana", "patient_middle_name": "",
        "patient_last_name": "Sintética", "visit_datetime": datetime(2026, 1, 2, 10, 30),
        "gx_vo2_max_hr_bpm": "160", "gx_predicted_hr_bpm": "170", "gx_vo2_max_vo2_ml_per_min": "1800",
        "gx_predicted_vo2_ml_per_min": "2000", "gx_vo2_max_work_watts": "150", "gx_predicted_work_watts": "170",
        "gx_vo2_max_vo2_per_hr_ml_per_beat": "11.2", "gx_predicted_vo2_per_hr_ml_per_beat": "9.8",
        "gx_at_vo2_ml_per_min": "720", "pf_pre_mvv_l_per_min": "70", "gx_vo2_max_ve_btps_l_per_min": "55",
        "gx_rest_ph": "7.4", "gx_vo2_max_ph": "7.3",
        "gx_rest_vd_per_vt_meas": "25", "gx_rest_vd_per_vt_est": "30",
        "gx_vo2_max_vd_per_vt_meas": "18", "gx_vo2_max_vd_per_vt_est": "22",
    }


@skipUnless(
    TEST_DATABASE_URL and DESTRUCTIVE_TEST_CONFIGURATION_ERROR is None,
    DESTRUCTIVE_TEST_CONFIGURATION_ERROR or "INFORMEGX_TEST_DATABASE_URL no configurada",
)
class PostgresWorkflowTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        test_database_url = destructive_test_database_url()
        with psycopg.connect(test_database_url, autocommit=True) as connection:
            connection.execute("DROP SCHEMA IF EXISTS ergo_app CASCADE")
        environment = {
            **os.environ,
            "APP_ENV": "testing",
            "APP_DATABASE_URL": test_database_url,
            "ALLOW_APP_MIGRATIONS": "1",
        }
        subprocess.run([sys.executable, "-m", "migrations"], check=True, env=environment)
        cls.app = create_app("testing")
        cls.app.config.update(APP_DATABASE_URL=TEST_DATABASE_URL, SECRET_KEY="synthetic-test-secret")

    def setUp(self) -> None:
        test_database_url = destructive_test_database_url()
        with psycopg.connect(test_database_url, autocommit=True) as connection:
            connection.execute("TRUNCATE ergo_app.report_pdf_events, ergo_app.report_workflow_audits, ergo_app.report_versions, ergo_app.draft_values, ergo_app.report_drafts, ergo_app.studies, ergo_app.user_signature_profiles, ergo_app.users RESTART IDENTITY CASCADE")
            for username, role in (("aux", AUXILIAR), ("med_a", MEDICO), ("med_b", MEDICO), ("coord", COORDINADORA)):
                connection.execute("INSERT INTO ergo_app.users (username, full_name, password_hash, role) VALUES (%s, %s, %s, %s)", (username, f"{username} sintético", hash_password("secret"), role))

    def _draft(self):
        with self.app.app_context():
            return open_persistent_draft(patient_id_num="90000001", visit_datetime=datetime(2026, 1, 2, 10, 30), clinical_row=clinical_row())[0]

    def test_state_transitions_and_release_are_durable(self) -> None:
        draft = self._draft()
        self.assertEqual(draft.state, PRELIMINAR)
        with self.app.app_context():
            taken = take_for_signature(draft_id=draft.id, user_id=2, username="med_a")
            self.assertEqual(taken.state, EN_FIRMA)
            self.assertEqual(taken.medical_owner_user_id, 2)
            with self.assertRaises(DraftOwnershipError):
                release_from_signature(draft_id=draft.id, user_id=3, username="med_b")
            released = release_from_signature(draft_id=draft.id, user_id=2, username="med_a")
        self.assertEqual(released.state, PRELIMINAR_BLOQUEADO)
        self.assertIsNone(released.medical_owner_user_id)

    def test_expiration_is_not_renewed_and_is_audited_once(self) -> None:
        draft = self._draft()
        taken_at = datetime.now(timezone.utc) - timedelta(days=30, seconds=1)
        with self.app.app_context():
            taken = take_for_signature(draft_id=draft.id, user_id=2, username="med_a", taken_at=taken_at)
            expired = get_draft(taken.id, now=datetime.now(timezone.utc))
            again = get_draft(taken.id, now=datetime.now(timezone.utc))
        self.assertEqual(expired.state, PRELIMINAR_BLOQUEADO)
        self.assertEqual(again.state, PRELIMINAR_BLOQUEADO)
        with psycopg.connect(TEST_DATABASE_URL) as connection:
            count = connection.execute("SELECT count(*) FROM ergo_app.report_workflow_audits WHERE event_type='MEDICAL_OWNERSHIP_EXPIRED'").fetchone()[0]
        self.assertEqual(count, 1)

    def test_sign_is_independent_from_pdf_and_v2_copies_snapshot(self) -> None:
        draft = self._draft()
        profile = {"name": "Dra. Sintética", "profession_specialty": "Especialidad", "professional_registration": "RM-1", "institutional_line": ""}
        with self.app.app_context():
            taken = take_for_signature(draft_id=draft.id, user_id=2, username="med_a")
            signed = sign_draft(draft_id=taken.id, user_id=2, username="med_a", signer_signature_profile=profile, expected_values=taken.values)
            self.assertIsNotNone(get_report_version(signed.id))
            v2 = create_next_version(source_version_id=signed.id, user_id=3, username="med_b")
        self.assertEqual(v2.next_version_number, 2)
        self.assertEqual(v2.state, EN_FIRMA)
        self.assertEqual(v2.medical_owner_user_id, 3)
        self.assertEqual(v2.values, signed.values)
        with psycopg.connect(TEST_DATABASE_URL) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM ergo_app.report_pdf_events").fetchone()[0], 0)

    def test_vdvt_metadata_survives_draft_signature_and_new_version(self) -> None:
        draft = self._draft()
        initial_view = report_view_for_draft(draft)
        self.assertEqual(
            initial_view.field("gx_rest_vd_per_vt_meas").source_columns,
            ("gx_rest_vd_per_vt_meas",),
        )
        self.assertEqual(initial_view.vdvt_source_values["gx_rest_vd_per_vt_meas"], ("25", "30"))

        with self.app.app_context():
            taken = take_for_signature(draft_id=draft.id, user_id=2, username="med_a")
            estimated = save_draft_values(
                draft=taken,
                user_id=2,
                role=MEDICO,
                submitted_values={"medicion_gases": "false"},
            )
            estimated_view = report_view_for_draft(estimated)
            signed = sign_draft(
                draft_id=estimated.id,
                user_id=2,
                username="med_a",
                signer_signature_profile={"name": "Dra. Sintética"},
                expected_values=estimated.values,
            )
            stored_signed = get_report_version(signed.id)
            assert stored_signed is not None
            signed_view = report_view_for_version(stored_signed)
            v2 = create_next_version(source_version_id=signed.id, user_id=3, username="med_b")
            v2_view = report_view_for_draft(v2)

        for view in (estimated_view, signed_view, v2_view):
            self.assertEqual(view.field("gx_rest_vd_per_vt_meas").value, "30")
            self.assertEqual(
                view.field("gx_rest_vd_per_vt_meas").source_columns,
                ("gx_rest_vd_per_vt_est",),
            )
            self.assertEqual(view.field("gx_vo2_max_vd_per_vt_meas").value, "22")
            self.assertEqual(
                view.field("gx_vo2_max_vd_per_vt_meas").source_columns,
                ("gx_vo2_max_vd_per_vt_est",),
            )
            self.assertEqual(view.vdvt_source_values["gx_rest_vd_per_vt_meas"], ("25", "30"))

    def test_pdf_events_are_many_per_signed_version(self) -> None:
        draft = self._draft()
        with self.app.app_context():
            taken = take_for_signature(draft_id=draft.id, user_id=2, username="med_a")
            signed = sign_draft(draft_id=taken.id, user_id=2, username="med_a", signer_signature_profile={"name": "Dra. Sintética"}, expected_values=taken.values)
            for suffix in ("a", "b"):
                record_pdf_event(version_id=signed.id, user_id=4, username="coord", generated_at=datetime.now(timezone.utc), filename=f"synthetic-{suffix}.pdf", pdf_sha256="a" * 64, pdf_size_bytes=10)
        with psycopg.connect(TEST_DATABASE_URL) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM ergo_app.report_pdf_events").fetchone()[0], 2)

    def test_coordinator_pdf_route_records_delivered_bytes_for_signed_version(self) -> None:
        draft = self._draft()
        profile = {"name": "Dra. Firmante sintética", "profession_specialty": "Especialidad"}
        with self.app.app_context():
            taken = take_for_signature(draft_id=draft.id, user_id=2, username="med_a")
            signed = sign_draft(
                draft_id=taken.id,
                user_id=2,
                username="med_a",
                signer_signature_profile=profile,
                expected_values=taken.values,
            )

        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = "4"
            session["_fresh"] = True
            session["_csrf_token"] = "synthetic-csrf"
        pdf_bytes = b"%PDF-coordinator-synthetic\n%%EOF"
        generated_at = datetime(2026, 8, 24, 15, 30, tzinfo=timezone.utc)
        with patch("routes.studies.generate_report_pdf", return_value=pdf_bytes) as generate, patch(
            "routes.studies._generation_instant", return_value=generated_at
        ):
            responses = [
                client.post(
                    "/studies/versions/report.pdf",
                    data={"csrf_token": "synthetic-csrf", "version_id": str(signed.id)},
                )
                for _ in range(2)
            ]

        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertTrue(all(response.data == pdf_bytes for response in responses))
        self.assertEqual(generate.call_args.kwargs["signature_profile"].name, "Dra. Firmante sintética")
        with psycopg.connect(TEST_DATABASE_URL) as connection:
            events = connection.execute(
                """SELECT version_id, generated_by_user_id, generated_by_username,
                          pdf_sha256, pdf_size_bytes
                     FROM ergo_app.report_pdf_events WHERE version_id=%s""",
                (signed.id,),
            ).fetchall()
        self.assertEqual(len(events), 2)
        self.assertTrue(
            all(
                event == (
                    signed.id,
                    4,
                    "coord",
                    hashlib.sha256(pdf_bytes).hexdigest(),
                    len(pdf_bytes),
                )
                for event in events
            )
        )
