"""Current narrative and signed-version PDF coverage with synthetic data only."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from app import create_app
from repositories.drafts import PersistedReportVersion
from repositories.users import AuthUser
from services.pdf_report import format_generation_time_bogota, generate_report_pdf
from services.report_narratives import SECTION_TITLES, build_report_narratives
from services.signature_profile import SignatureProfile
from services.study_report import build_study_report_view


def report_with_snapshot_values():
    return build_study_report_view(
        {
            "patient_id_num": "90000001",
            "patient_first_name": "Ana",
            "patient_middle_name": "",
            "patient_last_name": "Sintética",
            "visit_datetime": datetime(2026, 8, 20, 17, 43, 15),
            "weight": "0",
            "gx_vo2_max_work_watts": "150",
            "gx_vo2_max_vo2_ml_per_kg_per_min": "26.5",
            "gx_vo2_max_vo2workslope_ml_per_min_per_watt": "10.2",
            "gx_vo2_max_rr_br_per_min": "30",
        },
        submitted_values={
            "motivo_remision": "Control sintético",
            "hb": "0",
            "umbral_anaerobio_alcanzado": "NO",
            "gx_at_ve_per_vco2": "99",
            "gx_at_ve_per_vo2": "88",
            "conclusiones_definitivas": "Conclusión firmada <script>alert(1)</script>",
        },
    )


class NarrativeTests(TestCase):
    def test_narratives_use_current_manual_zero_and_interpretation_values(self) -> None:
        narratives = build_report_narratives(report_with_snapshot_values())

        self.assertEqual(tuple(section.title for section in narratives), SECTION_TITLES)
        self.assertIn("Motivo de la remisión: Control sintético", narratives[0].fragments)
        self.assertIn("Hb: 0 g/dL", narratives[0].fragments)
        self.assertIn("Peso: 0 kg", " ".join(narratives[0].fragments))
        ventilatory = " ".join(narratives[4].fragments)
        self.assertIn("no aplica", ventilatory)
        self.assertNotIn("99", ventilatory)
        self.assertNotIn("88", ventilatory)
        self.assertEqual(
            narratives[5].fragments[-1],
            "Conclusión firmada <script>alert(1)</script>",
        )

    def test_empty_values_do_not_create_spurious_optional_narrative_fragments(self) -> None:
        report = build_study_report_view({"patient_id_num": "90000001"})
        narratives = build_report_narratives(report)

        self.assertEqual(narratives[0].fragments, ())
        self.assertEqual(narratives[2].fragments, ())
        self.assertEqual(narratives[3].fragments, ())
        self.assertEqual(narratives[4].fragments, ())
        self.assertEqual(narratives[5].fragments, ())


class PdfRenderingTests(TestCase):
    def setUp(self) -> None:
        self.app = create_app("testing")

    def test_pdf_template_escapes_dynamic_content_and_uses_signer_profile(self) -> None:
        report = report_with_snapshot_values()
        profile = SignatureProfile(
            name="Dra. Firmante sintética",
            profession_specialty="Especialidad sintética",
            professional_registration="RM-900",
            institutional_line="Institución sintética",
        )
        with self.app.app_context(), patch("weasyprint.HTML") as html, patch("weasyprint.CSS"):
            html.return_value.write_pdf.return_value = b"%PDF-synthetic"
            pdf_bytes = generate_report_pdf(
                report,
                build_report_narratives(report),
                generated_at=datetime(2026, 8, 24, 15, 30, tzinfo=timezone.utc),
                signature_profile=profile,
            )

        rendered_html = html.call_args.kwargs["string"]
        self.assertEqual(pdf_bytes, b"%PDF-synthetic")
        self.assertIn("Conclusión firmada &lt;script&gt;alert(1)&lt;/script&gt;", rendered_html)
        self.assertNotIn("Conclusión firmada <script>alert(1)</script>", rendered_html)
        self.assertIn("Dra. Firmante sintética", rendered_html)
        self.assertIn("Especialidad sintética", rendered_html)
        self.assertIn("Registro profesional: RM-900", rendered_html)
        self.assertNotIn("Guardar ahora", rendered_html)
        self.assertNotIn("GX · EDITADO", rendered_html)

    def test_pdf_renders_in_memory_when_letterhead_assets_are_missing(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            with (
                self.app.app_context(),
                patch("services.pdf_report.WIDE_LETTERHEAD_PATH", temporary_path / "missing-wide.svg"),
                patch("services.pdf_report.COMPACT_LETTERHEAD_PATH", temporary_path / "missing-compact.svg"),
            ):
                pdf_bytes = generate_report_pdf(
                    report_with_snapshot_values(),
                    build_report_narratives(report_with_snapshot_values()),
                    generated_at=datetime(2026, 8, 24, 15, 30, tzinfo=timezone.utc),
                    signature_profile=SignatureProfile(name="Dra. Firmante sintética"),
                )

            self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
            self.assertEqual(list(temporary_path.iterdir()), [])

    def test_generation_time_uses_bogota_and_rejects_naive_instants(self) -> None:
        self.assertEqual(
            format_generation_time_bogota(
                datetime(2026, 8, 24, 15, 30, 45, tzinfo=timezone.utc)
            ),
            "2026-08-24 10:30:45",
        )
        with self.assertRaisesRegex(ValueError, "zona horaria"):
            format_generation_time_bogota(datetime(2026, 8, 24, 15, 30, 45))


class SignedVersionPdfRouteTests(TestCase):
    def setUp(self) -> None:
        self.coordinator = AuthUser(
            id=41,
            username="synthetic-coordinator",
            full_name="Coordinadora sintética",
            password_hash="unused",
            active=True,
            role="COORDINADORA",
        )
        self.user_loader = patch("app.get_user_by_id", return_value=self.coordinator)
        self.user_loader.start()
        self.addCleanup(self.user_loader.stop)
        self.app = create_app("testing")
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.coordinator.id)
            session["_fresh"] = True
            session["_csrf_token"] = "synthetic-csrf"

    @staticmethod
    def _signed_version() -> PersistedReportVersion:
        return PersistedReportVersion(
            id=uuid4(),
            study_id=uuid4(),
            version_number=3,
            signed_by_user_id=7,
            signed_by_username="synthetic-doctor",
            signed_at=datetime(2026, 8, 20, 20, 0, tzinfo=timezone.utc),
            lookup_patient_id_num="90000001",
            lookup_visit_datetime=datetime(2026, 8, 20, 17, 43, 15),
            values={},
            signer_signature_profile={
                "name": "Dra. Firmante sintética",
                "profession_specialty": "Especialidad sintética",
                "professional_registration": "RM-900",
                "institutional_line": "Institución sintética",
            },
            source_version_id=None,
        )

    def test_coordinator_generates_exact_signed_snapshot_bytes_and_events(self) -> None:
        version = self._signed_version()
        report = report_with_snapshot_values()
        pdf_bytes = b"%PDF-signed-snapshot\n%%EOF"
        generated_at = datetime(2026, 8, 24, 15, 30, tzinfo=timezone.utc)
        browser_injection = "No debe entrar al snapshot"

        with (
            patch("routes.studies.get_report_version", return_value=version) as get_version,
            patch("routes.studies.report_view_for_version", return_value=report) as report_view,
            patch("routes.studies.generate_report_pdf", return_value=pdf_bytes) as generate,
            patch("routes.studies.record_pdf_event") as record_event,
            patch("routes.studies._generation_instant", return_value=generated_at),
        ):
            responses = [
                self.client.post(
                    "/studies/versions/report.pdf",
                    data={
                        "csrf_token": "synthetic-csrf",
                        "version_id": str(version.id),
                        "conclusiones_definitivas": browser_injection,
                    },
                )
                for _ in range(2)
            ]

        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertTrue(all(response.data == pdf_bytes for response in responses))
        self.assertTrue(all(response.headers["Content-Type"] == "application/pdf" for response in responses))
        self.assertTrue(all(response.headers["Cache-Control"] == "no-store" for response in responses))
        self.assertTrue(all(response.headers["X-Content-Type-Options"] == "nosniff" for response in responses))
        self.assertEqual(get_version.call_count, 2)
        self.assertEqual(report_view.call_args.args, (version,))
        self.assertEqual(generate.call_count, 2)
        for generated_call in generate.call_args_list:
            generated_report, generated_narratives = generated_call.args
            self.assertIs(generated_report, report)
            self.assertIn("Conclusión firmada <script>alert(1)</script>", generated_narratives[-1].fragments)
            self.assertNotIn(browser_injection, " ".join(generated_narratives[-1].fragments))
            self.assertEqual(
                generated_call.kwargs["signature_profile"],
                SignatureProfile(
                    name="Dra. Firmante sintética",
                    profession_specialty="Especialidad sintética",
                    professional_registration="RM-900",
                    institutional_line="Institución sintética",
                ),
            )
            self.assertEqual(generated_call.kwargs["generated_at"], generated_at)
        self.assertEqual(record_event.call_count, 2)
        for event_call in record_event.call_args_list:
            self.assertEqual(event_call.kwargs["version_id"], version.id)
            self.assertEqual(event_call.kwargs["user_id"], self.coordinator.id)
            self.assertEqual(event_call.kwargs["username"], self.coordinator.username)
            self.assertEqual(event_call.kwargs["pdf_sha256"], hashlib.sha256(pdf_bytes).hexdigest())
            self.assertEqual(event_call.kwargs["pdf_size_bytes"], len(pdf_bytes))
            self.assertEqual(event_call.kwargs["generated_at"], generated_at)

    def test_non_coordinator_or_invalid_csrf_cannot_load_a_signed_version(self) -> None:
        version = self._signed_version()
        with patch("routes.studies.get_report_version", return_value=version) as get_version:
            invalid_csrf = self.client.post(
                "/studies/versions/report.pdf",
                data={"csrf_token": "invalid", "version_id": str(version.id)},
            )

        self.assertEqual(invalid_csrf.status_code, 400)
        get_version.assert_not_called()

        non_coordinator = AuthUser(
            id=42,
            username="synthetic-doctor",
            full_name="Médico sintético",
            password_hash="unused",
            active=True,
            role="MEDICO",
        )
        with patch("app.get_user_by_id", return_value=non_coordinator), patch(
            "routes.studies.get_report_version", return_value=version
        ) as get_version:
            with self.client.session_transaction() as session:
                session["_user_id"] = str(non_coordinator.id)
                session["_csrf_token"] = "synthetic-csrf"
            denied = self.client.post(
                "/studies/versions/report.pdf",
                data={"csrf_token": "synthetic-csrf", "version_id": str(version.id)},
            )

        self.assertEqual(denied.status_code, 403)
        get_version.assert_not_called()
