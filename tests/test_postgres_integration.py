"""Integration coverage against the explicitly configured isolated app database."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
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
    DraftStateError,
    create_next_version,
    get_draft,
    get_report_version,
    record_pdf_event,
    release_from_signature,
    sign_draft,
    take_for_signature,
)
from repositories.users import (
    get_user_by_id,
    get_user_signature_image,
    save_user_signature_profile,
)
from services.draft_workflow import open_persistent_draft
from services.draft_workflow import (
    report_view_for_draft,
    report_view_for_version,
    save_draft_values,
    sign_report_draft,
    take_draft_for_signature,
)
from services.passwords import hash_password
from services.report_controls import AUXILIAR, COORDINADORA, MEDICO
from services.study_report import INITIAL_CONCLUSIONES_DEFINITIVAS
from tests.synthetic_png import synthetic_png


TEST_DATABASE_URL = os.getenv("INFORMEGX_TEST_DATABASE_URL")
DESTRUCTIVE_TEST_OPT_IN_ENV = "INFORMEGX_ALLOW_DESTRUCTIVE_TESTS"
SIGNATURE_UPDATED_AT = datetime(2026, 9, 16, 10, 30, tzinfo=timezone.utc)


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
            connection.execute("TRUNCATE ergo_app.user_signature_profile_audits, ergo_app.report_pdf_events, ergo_app.report_workflow_audits, ergo_app.report_versions, ergo_app.draft_values, ergo_app.report_drafts, ergo_app.studies, ergo_app.user_signature_profiles, ergo_app.users RESTART IDENTITY CASCADE")
            for username, role in (("aux", AUXILIAR), ("med_a", MEDICO), ("med_b", MEDICO), ("coord", COORDINADORA)):
                connection.execute("INSERT INTO ergo_app.users (username, full_name, password_hash, role) VALUES (%s, %s, %s, %s)", (username, f"{username} sintético", hash_password("secret"), role))
            for username in ("med_a", "med_b"):
                connection.execute(
                    """INSERT INTO ergo_app.user_signature_profiles
                           (user_id, signature_name, profession_specialty,
                            professional_registration, institutional_line,
                            signature_image, signature_image_mime_type,
                            signature_image_updated_at)
                         SELECT id, full_name, 'Especialidad sintética', 'RM-100',
                                'Institución sintética', %s, 'image/png', %s
                           FROM ergo_app.users WHERE username=%s""",
                    (synthetic_png(), SIGNATURE_UPDATED_AT, username),
                )

    def _draft(self):
        with self.app.app_context():
            return open_persistent_draft(patient_id_num="90000001", visit_datetime=datetime(2026, 1, 2, 10, 30), clinical_row=clinical_row())[0]

    def test_test_user_rename_migration_preserves_identity_role_hash_and_history(self) -> None:
        migration_sql = Path("migrations/007_rename_test_users.sql").read_text(encoding="utf-8")
        self.assertNotIn("report_workflow_audits", migration_sql)
        self.assertNotIn("report_versions", migration_sql)
        self.assertNotIn("report_pdf_events", migration_sql)

        source_accounts = (
            ("auxiliar_test", "Auxiliar Test", "hash-auxiliar-sintetico", AUXILIAR),
            ("medico_test", "Medico Test", "hash-medico-sintetico", MEDICO),
            ("coordinadora_test", "Coordinadora Test", "hash-coordinadora-sintetico", COORDINADORA),
        )
        expected_names = (
            ("fisioterapeuta_test", "Fisioterapeuta Test"),
            ("medico_test", "Médico Test"),
            ("lider_test", "Líder Test"),
        )
        with psycopg.connect(TEST_DATABASE_URL) as connection:
            before = [
                connection.execute(
                    """INSERT INTO ergo_app.users (username, full_name, password_hash, role)
                         VALUES (%s, %s, %s, %s)
                      RETURNING id, password_hash, role""",
                    account,
                ).fetchone()
                for account in source_accounts
            ]
            connection.execute(migration_sql)
            after = [
                connection.execute(
                    """SELECT id, username, full_name, password_hash, role
                         FROM ergo_app.users WHERE id=%s""",
                    (account[0],),
                ).fetchone()
                for account in before
            ]

        self.assertEqual(
            after,
            [
                (before_row[0], username, full_name, before_row[1], before_row[2])
                for before_row, (username, full_name) in zip(before, expected_names, strict=True)
            ],
        )

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
            auxiliary_saved = save_draft_values(
                draft=draft,
                user_id=1,
                role=AUXILIAR,
                submitted_values={"medico_remitente": "Dr. Remitente auxiliar sintético"},
            )
            taken = take_for_signature(draft_id=auxiliary_saved.id, user_id=2, username="med_a")
            medical_saved = save_draft_values(
                draft=taken,
                user_id=2,
                role=MEDICO,
                submitted_values={"medico_remitente": "Dra. Remitente firmada sintética"},
            )
            signed = sign_draft(draft_id=medical_saved.id, user_id=2, username="med_a", signer_signature_profile=profile, expected_values=medical_saved.values)
            self.assertIsNotNone(get_report_version(signed.id))
            v2 = create_next_version(source_version_id=signed.id, user_id=3, username="med_b")
        self.assertEqual(v2.next_version_number, 2)
        self.assertEqual(v2.state, EN_FIRMA)
        self.assertEqual(v2.medical_owner_user_id, 3)
        self.assertEqual(v2.values, signed.values)
        self.assertEqual(
            signed.values["medico_remitente"].current_value,
            "Dra. Remitente firmada sintética",
        )
        self.assertEqual(
            v2.values["medico_remitente"].current_value,
            "Dra. Remitente firmada sintética",
        )
        with psycopg.connect(TEST_DATABASE_URL) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM ergo_app.report_pdf_events").fetchone()[0], 0)

    def test_replacing_profile_signature_is_audited_and_does_not_change_signed_version(self) -> None:
        first_image = synthetic_png(10)
        second_image = synthetic_png(220)
        first_updated_at = datetime(2026, 9, 16, 10, 0, tzinfo=timezone.utc)
        second_updated_at = datetime(2026, 9, 16, 11, 0, tzinfo=timezone.utc)
        draft = self._draft()
        with self.app.app_context():
            save_user_signature_profile(
                user_id=2,
                actor_user_id=2,
                actor_username="med_a",
                signature_name="Dra. Sintética",
                profession_specialty="Especialidad sintética",
                professional_registration="RM-100",
                institutional_line="Institución sintética",
                signature_image_content=first_image,
                signature_image_mime_type="image/png",
                updated_at=first_updated_at,
            )
            current = get_user_signature_image(2)
            self.assertIsNotNone(current)
            self.assertEqual(current.content, first_image)
            taken = take_for_signature(draft_id=draft.id, user_id=2, username="med_a")
            user = get_user_by_id(2)
            assert user is not None
            signed = sign_report_draft(draft=taken, user=user, expected_values=taken.values)
            save_user_signature_profile(
                user_id=2,
                actor_user_id=2,
                actor_username="med_a",
                signature_name="Dra. Sintética actualizada",
                profession_specialty="Especialidad actualizada",
                professional_registration="RM-200",
                institutional_line="Institución actualizada",
                signature_image_content=second_image,
                signature_image_mime_type="image/png",
                updated_at=second_updated_at,
            )
            stored_version = get_report_version(signed.id)
            current = get_user_signature_image(2)

        assert stored_version is not None and current is not None
        self.assertEqual(current.content, second_image)
        self.assertEqual(current.updated_at, second_updated_at)
        self.assertEqual(stored_version.signer_signature_image, first_image)
        self.assertEqual(
            stored_version.signer_signature_image_updated_at,
            first_updated_at,
        )
        self.assertEqual(
            stored_version.signer_signature_profile["name"],
            "Dra. Sintética",
        )
        with psycopg.connect(TEST_DATABASE_URL) as connection:
            audits = connection.execute(
                """SELECT profile_user_id, actor_user_id, actor_username, occurred_at
                     FROM ergo_app.user_signature_profile_audits
                    ORDER BY occurred_at"""
            ).fetchall()
        self.assertEqual(
            audits,
            [
                (2, 2, "med_a", first_updated_at),
                (2, 2, "med_a", second_updated_at),
            ],
        )

    def test_physician_without_profile_can_create_text_then_add_png(self) -> None:
        with psycopg.connect(TEST_DATABASE_URL) as connection:
            connection.execute(
                "DELETE FROM ergo_app.user_signature_profiles WHERE user_id=2"
            )
        text_updated_at = datetime(2026, 9, 16, 9, 0, tzinfo=timezone.utc)
        image_updated_at = datetime(2026, 9, 16, 9, 30, tzinfo=timezone.utc)
        final_text_updated_at = datetime(2026, 9, 16, 10, 0, tzinfo=timezone.utc)
        image = synthetic_png(80)
        with self.app.app_context():
            save_user_signature_profile(
                user_id=2,
                actor_user_id=2,
                actor_username="med_a",
                signature_name="med_a sintético",
                profession_specialty="Especialidad inicial",
                professional_registration="RM-001",
                institutional_line="",
                updated_at=text_updated_at,
            )
            self.assertIsNone(get_user_signature_image(2))
            save_user_signature_profile(
                user_id=2,
                actor_user_id=2,
                actor_username="med_a",
                signature_name="Dra. Actualizada",
                profession_specialty="Especialidad actualizada",
                professional_registration="RM-002",
                institutional_line="Institución sintética",
                signature_image_content=image,
                signature_image_mime_type="image/png",
                updated_at=image_updated_at,
            )
            save_user_signature_profile(
                user_id=2,
                actor_user_id=2,
                actor_username="med_a",
                signature_name="Dra. Solo texto",
                profession_specialty="Especialidad final",
                professional_registration="RM-003",
                institutional_line="Institución final",
                updated_at=final_text_updated_at,
            )
            stored_image = get_user_signature_image(2)

        assert stored_image is not None
        self.assertEqual(stored_image.content, image)
        with psycopg.connect(TEST_DATABASE_URL) as connection:
            profile = connection.execute(
                """SELECT signature_name, profession_specialty,
                          professional_registration, institutional_line
                     FROM ergo_app.user_signature_profiles WHERE user_id=2"""
            ).fetchone()
            audit_count = connection.execute(
                """SELECT COUNT(*) FROM ergo_app.user_signature_profile_audits
                    WHERE profile_user_id=2"""
            ).fetchone()[0]
        self.assertEqual(
            profile,
            (
                "Dra. Solo texto",
                "Especialidad final",
                "RM-003",
                "Institución final",
            ),
        )
        self.assertEqual(audit_count, 1)

    def test_signing_without_current_signature_image_keeps_active_draft(self) -> None:
        draft = self._draft()
        with psycopg.connect(TEST_DATABASE_URL) as connection:
            connection.execute(
                """UPDATE ergo_app.user_signature_profiles
                      SET signature_image=NULL, signature_image_mime_type=NULL,
                          signature_image_updated_at=NULL
                    WHERE user_id=2"""
            )
        with self.app.app_context():
            taken = take_for_signature(draft_id=draft.id, user_id=2, username="med_a")
            with self.assertRaisesRegex(DraftStateError, "firma manuscrita PNG"):
                sign_draft(
                    draft_id=taken.id,
                    user_id=2,
                    username="med_a",
                    signer_signature_profile={"name": "Dra. Sintética"},
                    expected_values=taken.values,
                )
            preserved = get_draft(taken.id)
        assert preserved is not None
        self.assertEqual(preserved.state, EN_FIRMA)
        self.assertEqual(preserved.medical_owner_user_id, 2)

    def test_new_version_requires_no_active_draft_and_latest_signed_source(self) -> None:
        draft = self._draft()
        with self.app.app_context():
            taken = take_for_signature(draft_id=draft.id, user_id=2, username="med_a")
            signed_v1 = sign_draft(
                draft_id=taken.id,
                user_id=2,
                username="med_a",
                signer_signature_profile={"name": "Dra. Sintética"},
                expected_values=taken.values,
            )
            v2 = create_next_version(
                source_version_id=signed_v1.id, user_id=3, username="med_b"
            )
            with self.assertRaisesRegex(DraftStateError, "versión activa"):
                create_next_version(
                    source_version_id=signed_v1.id, user_id=2, username="med_a"
                )

            blocked_v2 = release_from_signature(
                draft_id=v2.id, user_id=3, username="med_b"
            )
            self.assertEqual(blocked_v2.state, PRELIMINAR_BLOQUEADO)
            with self.assertRaisesRegex(DraftStateError, "versión activa"):
                create_next_version(
                    source_version_id=signed_v1.id, user_id=2, username="med_a"
                )

            retaken_v2 = take_for_signature(
                draft_id=blocked_v2.id, user_id=2, username="med_a"
            )
            signed_v2 = sign_draft(
                draft_id=retaken_v2.id,
                user_id=2,
                username="med_a",
                signer_signature_profile={"name": "Dra. Sintética"},
                expected_values=retaken_v2.values,
            )
            with self.assertRaisesRegex(DraftStateError, "última versión firmada"):
                create_next_version(
                    source_version_id=signed_v1.id, user_id=3, username="med_b"
                )
            v3 = create_next_version(
                source_version_id=signed_v2.id, user_id=3, username="med_b"
            )

        self.assertEqual(v3.next_version_number, 3)
        self.assertEqual(v3.created_from_version_id, signed_v2.id)

    def test_conclusions_template_is_initialized_only_on_first_v1_take(self) -> None:
        draft = self._draft()
        self.assertEqual(
            draft.values["conclusiones_definitivas"].current_value,
            "",
        )

        with self.app.app_context():
            taken = take_draft_for_signature(
                draft=draft,
                user_id=2,
                username="med_a",
                role=MEDICO,
            )
            self.assertEqual(
                taken.values["conclusiones_definitivas"].current_value,
                INITIAL_CONCLUSIONES_DEFINITIVAS,
            )
            emptied = save_draft_values(
                draft=taken,
                user_id=2,
                role=MEDICO,
                submitted_values={"conclusiones_definitivas": ""},
            )
            released = release_from_signature(
                draft_id=emptied.id,
                user_id=2,
                username="med_a",
            )
            retaken = take_draft_for_signature(
                draft=released,
                user_id=3,
                username="med_b",
                role=MEDICO,
            )
            self.assertEqual(
                retaken.values["conclusiones_definitivas"].current_value,
                "",
            )
            signed = sign_draft(
                draft_id=retaken.id,
                user_id=3,
                username="med_b",
                signer_signature_profile={"name": "Dra. Sintética"},
                expected_values=retaken.values,
            )
            v2 = create_next_version(
                source_version_id=signed.id,
                user_id=2,
                username="med_a",
            )

        self.assertEqual(
            v2.values["conclusiones_definitivas"].current_value,
            "",
        )

        other_row = clinical_row()
        other_row.update(
            patient_id_num="90000002",
            visit_datetime=datetime(2026, 1, 3, 11, 45),
        )
        with self.app.app_context():
            preexisting, _ = open_persistent_draft(
                patient_id_num="90000002",
                visit_datetime=datetime(2026, 1, 3, 11, 45),
                clinical_row=other_row,
            )
        with psycopg.connect(TEST_DATABASE_URL) as connection:
            connection.execute(
                """UPDATE ergo_app.draft_values SET current_value=%s
                     WHERE draft_id=%s AND field_key='conclusiones_definitivas'""",
                ("Conclusión previa sintética", preexisting.id),
            )
        with self.app.app_context():
            current = get_draft(preexisting.id)
            assert current is not None
            preserved = take_draft_for_signature(
                draft=current,
                user_id=2,
                username="med_a",
                role=MEDICO,
            )
        self.assertEqual(
            preserved.values["conclusiones_definitivas"].current_value,
            "Conclusión previa sintética",
        )

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
        self.assertEqual(
            generate.call_args.kwargs["signature_image"],
            synthetic_png(),
        )
        self.assertEqual(
            generate.call_args.kwargs["signature_image_mime_type"],
            "image/png",
        )
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
