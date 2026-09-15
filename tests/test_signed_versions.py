"""Signed-version browser coverage using synthetic data only."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from app import create_app
from repositories.users import AuthUser
from services.study_report import build_study_report_view


STUDY_DATE = datetime(2026, 8, 20, 17, 43, 15)


def signed_version(number: int):
    return SimpleNamespace(
        id=uuid4(),
        version_number=number,
        signed_by_username=f"medico-sintetico-{number}",
        signed_at=datetime(2026, 8, 20 + number, 20, 0, tzinfo=timezone.utc),
        lookup_patient_id_num="90000001",
        lookup_visit_datetime=STUDY_DATE,
    )


def report_view():
    return build_study_report_view(
        {
            "patient_id_num": "90000001",
            "patient_first_name": "Paciente",
            "patient_last_name": "Sintético",
            "visit_datetime": STUDY_DATE,
        },
        submitted_values={"motivo_remision": "Control sintético persistido"},
    )


class SignedVersionBrowserTests(TestCase):
    def setUp(self) -> None:
        self.user = AuthUser(
            id=17,
            username="medico-sintetico",
            full_name="Médico sintético",
            password_hash="unused",
            active=True,
            role="MEDICO",
        )
        self.user_loader = patch("app.get_user_by_id", return_value=self.user)
        self.user_loader.start()
        self.addCleanup(self.user_loader.stop)
        self.app = create_app("testing")
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.user.id)
            session["_fresh"] = True
            session["_csrf_token"] = "synthetic-csrf"

    def get_versions(self):
        return self.client.get(
            "/studies/versions",
            query_string={
                "patient_id_num": "90000001",
                "visit_datetime": STUDY_DATE.isoformat(),
            },
        )

    def test_medico_can_open_versions_screen_and_empty_state(self) -> None:
        with (
            patch("routes.studies.list_report_versions", return_value=[]),
            patch("routes.studies.get_existing_draft_for_study", return_value=None),
        ):
            response = self.get_versions()

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Versiones firmadas", html)
        self.assertIn("No hay versiones firmadas", html)
        self.assertNotIn("Crear nueva versión", html)

    def test_medico_sees_all_signed_versions_and_can_create_only_from_latest(self) -> None:
        versions = [signed_version(number) for number in (3, 2, 1)]
        with (
            patch("routes.studies.list_report_versions", return_value=versions),
            patch("routes.studies.get_existing_draft_for_study", return_value=None),
        ):
            response = self.get_versions()

        html = response.get_data(as_text=True)
        for version in versions:
            self.assertIn(f"Versión {version.version_number}", html)
            self.assertIn(version.signed_by_username, html)
            self.assertIn(f'/studies/versions/{version.id}', html)
        self.assertEqual(html.count("Ver informe"), 3)
        self.assertIn("Crear nueva versión", html)
        self.assertIn(f'name="version_id" value="{versions[0].id}"', html)
        self.assertNotIn(f'name="version_id" value="{versions[1].id}"', html)
        self.assertNotIn(f'name="version_id" value="{versions[2].id}"', html)

    def test_active_signature_or_blocked_draft_is_shown_and_blocks_creation(self) -> None:
        versions = [signed_version(1)]
        for state in ("EN_FIRMA", "PRELIMINAR_BLOQUEADO"):
            active_draft_id = uuid4()
            with self.subTest(state=state), patch(
                "routes.studies.list_report_versions", return_value=versions
            ), patch(
                "routes.studies.get_existing_draft_for_study",
                return_value=SimpleNamespace(
                    id=active_draft_id,
                    next_version_number=2,
                    state=state,
                    medical_owner_user_id=(
                        self.user.id if state == "EN_FIRMA" else None
                    ),
                ),
            ):
                html = self.get_versions().get_data(as_text=True)

            self.assertIn("Versión activa 2", html)
            self.assertIn(f"Estado actual: {state}", html)
            self.assertIn("Continuar editando", html)
            self.assertIn(f'href="/studies/drafts/{active_draft_id}"', html)
            self.assertNotIn("En edición por:", html)
            self.assertNotIn("Crear nueva versión", html)

    def test_active_signature_owned_by_another_medico_is_read_only(self) -> None:
        active_draft_id = uuid4()
        owner = SimpleNamespace(
            id=29,
            full_name="Médica propietaria sintética",
            username="medica-propietaria-sintetica",
        )
        active_draft = SimpleNamespace(
            id=active_draft_id,
            next_version_number=2,
            state="EN_FIRMA",
            medical_owner_user_id=owner.id,
        )
        with (
            patch("routes.studies.list_report_versions", return_value=[signed_version(1)]),
            patch(
                "routes.studies.get_existing_draft_for_study",
                return_value=active_draft,
            ),
            patch("routes.studies.get_user_by_id", return_value=owner) as get_owner,
        ):
            html = self.get_versions().get_data(as_text=True)

        self.assertIn("En edición por: Médica propietaria sintética", html)
        self.assertIn("Ver en solo lectura", html)
        self.assertIn(f'href="/studies/drafts/{active_draft_id}"', html)
        self.assertNotIn("Continuar editando", html)
        self.assertIn("Ver informe", html)
        get_owner.assert_called_once_with(owner.id)

    def test_signed_html_uses_persisted_report_and_has_no_mutating_action(self) -> None:
        version = signed_version(2)
        persisted_report = report_view()
        with (
            patch("routes.studies.get_report_version", return_value=version),
            patch("routes.studies.report_view_for_version", return_value=persisted_report),
        ):
            response = self.client.get(f"/studies/versions/{version.id}")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Control sintético persistido", html)
        self.assertIn("Esta versión es inmutable", html)
        self.assertIn("Volver a versiones firmadas", html)
        self.assertNotIn("Crear nueva versión", html)
        self.assertNotIn("data-report-control", html)

    def test_active_link_opens_draft_without_workflow_transition(self) -> None:
        for state in ("EN_FIRMA", "PRELIMINAR_BLOQUEADO"):
            owner_user_id = 29 if state == "EN_FIRMA" else None
            active_draft = SimpleNamespace(
                id=uuid4(),
                revision=4,
                state=state,
                medical_owner_user_id=owner_user_id,
            )
            with self.subTest(state=state), patch(
                "routes.studies.get_draft", return_value=active_draft
            ), patch(
                "routes.studies.report_view_for_draft", return_value=report_view()
            ), patch(
                "routes.studies.take_draft_for_signature"
            ) as take_draft, patch(
                "routes.studies.release_draft"
            ) as release_draft, patch(
                "routes.studies.sign_report_draft"
            ) as sign_draft:
                response = self.client.get(f"/studies/drafts/{active_draft.id}")

            self.assertEqual(response.status_code, 200)
            self.assertNotIn('data-editable="true"', response.get_data(as_text=True))
            self.assertEqual(active_draft.state, state)
            self.assertEqual(active_draft.medical_owner_user_id, owner_user_id)
            take_draft.assert_not_called()
            release_draft.assert_not_called()
            sign_draft.assert_not_called()

    def test_medico_main_study_screen_links_to_signed_versions(self) -> None:
        draft = SimpleNamespace(
            id=uuid4(),
            revision=4,
            state="EN_FIRMA",
            medical_owner_user_id=self.user.id,
        )
        with (
            patch("routes.studies.get_draft", return_value=draft),
            patch("routes.studies.report_view_for_draft", return_value=report_view()),
        ):
            response = self.client.get(f"/studies/drafts/{draft.id}")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Ver versiones firmadas", response.get_data(as_text=True))

    def test_leader_keeps_pdf_action_and_auxiliary_gains_no_access(self) -> None:
        version = signed_version(1)
        self.user.role = "COORDINADORA"
        with (
            patch("routes.studies.list_report_versions", return_value=[version]),
            patch("routes.studies.get_existing_draft_for_study", return_value=None),
        ):
            leader_html = self.get_versions().get_data(as_text=True)
        self.assertIn("Ver informe", leader_html)
        self.assertIn("Generar PDF", leader_html)
        self.assertNotIn("Crear nueva versión", leader_html)

        self.user.role = "AUXILIAR"
        with patch("routes.studies.list_report_versions") as list_versions, patch(
            "routes.studies.get_report_version"
        ) as get_version:
            denied_list = self.get_versions()
            denied_version = self.client.get(f"/studies/versions/{version.id}")
        self.assertEqual(denied_list.status_code, 403)
        self.assertEqual(denied_version.status_code, 403)
        list_versions.assert_not_called()
        get_version.assert_not_called()
