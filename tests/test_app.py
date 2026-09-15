"""Unit tests for the durable stateful workflow (synthetic data only)."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from repositories.drafts import EN_FIRMA, PRELIMINAR, PRELIMINAR_BLOQUEADO, DraftValue, PersistedDraft
from repositories.users import AuthUser
from services.draft_workflow import (
    DraftPermissionError,
    editable_control_ids,
    open_persistent_draft,
    save_draft_values,
    take_draft_for_signature,
)
from services.report_controls import AUXILIAR, CALCULADO, CONTROL_TYPES, COORDINADORA, DIRECTO, INTERPRETACION, MANUAL, MEDICO
from services.study_report import INITIAL_CONCLUSIONES_DEFINITIVAS, REPORT_CONTROL_IDS, build_derived_values


def draft(*, state: str = PRELIMINAR, owner: int | None = None, version: int = 1) -> PersistedDraft:
    values = {
        key: DraftValue(key, CONTROL_TYPES[key], "origen" if CONTROL_TYPES[key] in {DIRECTO, CALCULADO} else "", "origen" if CONTROL_TYPES[key] in {DIRECTO, CALCULADO} else "", False)
        for key in REPORT_CONTROL_IDS
    }
    return PersistedDraft(uuid4(), uuid4(), version, "12345678", datetime(2026, 1, 2, 10, 30), values, state, owner, datetime(2026, 1, 2, 10, 30) if owner else None, 4)


class ClassificationTests(TestCase):
    def test_approved_types_cover_exactly_94_controls(self) -> None:
        self.assertEqual(set(CONTROL_TYPES), set(REPORT_CONTROL_IDS))
        self.assertEqual(Counter(CONTROL_TYPES.values()), {DIRECTO: 46, CALCULADO: 8, MANUAL: 17, INTERPRETACION: 23})
        self.assertEqual(CONTROL_TYPES["medico_remitente"], MANUAL)

    def test_existing_calculations_are_unchanged(self) -> None:
        values = build_derived_values({"gx_vo2_max_hr_bpm": "160", "gx_predicted_hr_bpm": "170", "gx_vo2_max_vo2_ml_per_min": "1800", "gx_predicted_vo2_ml_per_min": "2000", "gx_vo2_max_work_watts": "150", "gx_predicted_work_watts": "170", "gx_vo2_max_vo2_per_hr_ml_per_beat": "11.2", "gx_predicted_vo2_per_hr_ml_per_beat": "9.8", "gx_at_vo2_ml_per_min": "720", "pf_pre_mvv_l_per_min": "70", "gx_vo2_max_ve_btps_l_per_min": "55", "gx_rest_ph": "7.4", "gx_vo2_max_ph": "7.3"})
        self.assertEqual(values["porc_fc_maxima"], "94.12")
        self.assertEqual(values["reserva_respiratoria_pico_l"], "15")


class PermissionTests(TestCase):
    def test_editability_follows_state_and_medical_owner(self) -> None:
        preliminary = draft()
        in_signature = draft(state=EN_FIRMA, owner=7)
        blocked = draft(state=PRELIMINAR_BLOQUEADO)
        self.assertEqual(len(editable_control_ids(AUXILIAR, preliminary, user_id=1)), 15)
        self.assertEqual(editable_control_ids(MEDICO, preliminary, user_id=7), frozenset())
        self.assertEqual(editable_control_ids(AUXILIAR, blocked, user_id=1), frozenset())
        self.assertEqual(editable_control_ids(MEDICO, in_signature, user_id=7), frozenset(REPORT_CONTROL_IDS))
        self.assertEqual(editable_control_ids(MEDICO, in_signature, user_id=8), frozenset())
        self.assertEqual(editable_control_ids(COORDINADORA, preliminary, user_id=9), frozenset())
        self.assertIn("medico_remitente", editable_control_ids(AUXILIAR, preliminary, user_id=1))
        self.assertIn("medico_remitente", editable_control_ids(MEDICO, in_signature, user_id=7))
        self.assertNotIn("conclusiones_definitivas", editable_control_ids(AUXILIAR, preliminary, user_id=1))
        self.assertIn("conclusiones_definitivas", editable_control_ids(MEDICO, in_signature, user_id=7))

    def test_auxiliar_can_save_referring_physician_in_preliminary(self) -> None:
        preliminary = draft()
        with patch("services.draft_workflow.save_values", return_value=preliminary) as save:
            save_draft_values(
                draft=preliminary,
                user_id=1,
                role=AUXILIAR,
                submitted_values={"medico_remitente": "Dra. Remitente sintética"},
            )
        self.assertEqual(
            save.call_args.kwargs["updates"]["medico_remitente"],
            ("Dra. Remitente sintética", False),
        )

    def test_auxiliar_cannot_save_after_medical_phase(self) -> None:
        with self.assertRaises(DraftPermissionError):
            save_draft_values(
                draft=draft(state=PRELIMINAR_BLOQUEADO),
                user_id=1,
                role=AUXILIAR,
                submitted_values={"medico_remitente": "Dra. Remitente sintética"},
            )

    def test_backend_rejects_forced_unauthorized_control(self) -> None:
        with self.assertRaises(DraftPermissionError):
            save_draft_values(
                draft=draft(),
                user_id=1,
                role=AUXILIAR,
                submitted_values={"conclusiones_definitivas": "Cambio forzado sintético"},
            )

    def test_owner_save_uses_optimistic_workflow_revision(self) -> None:
        active = draft(state=EN_FIRMA, owner=7)
        with patch("services.draft_workflow.save_values", return_value=active) as save:
            save_draft_values(
                draft=active,
                user_id=7,
                role=MEDICO,
                submitted_values={"medico_remitente": "Dr. Remitente sintético"},
            )
        self.assertEqual(save.call_args.kwargs["expected_revision"], 4)
        self.assertEqual(save.call_args.kwargs["expected_state"], EN_FIRMA)
        self.assertEqual(save.call_args.kwargs["expected_owner_user_id"], 7)
        self.assertEqual(
            save.call_args.kwargs["updates"]["medico_remitente"],
            ("Dr. Remitente sintético", False),
        )


class InitialValuesTests(TestCase):
    def test_new_v1_starts_with_empty_conclusions(self) -> None:
        persisted = draft()
        with patch("services.draft_workflow.get_or_create_draft", return_value=persisted) as create:
            open_persistent_draft(
                patient_id_num="90000001",
                visit_datetime=datetime(2026, 1, 2, 10, 30),
                clinical_row={
                    "patient_id_num": "90000001",
                    "visit_datetime": datetime(2026, 1, 2, 10, 30),
                },
            )

        initial = create.call_args.kwargs["initial_values"]["conclusiones_definitivas"]
        self.assertEqual(initial.original_value, "")
        self.assertEqual(initial.current_value, "")
        self.assertEqual(initial.variable_type, INTERPRETACION)

    def test_medical_take_supplies_the_exact_conclusions_template(self) -> None:
        persisted = draft()
        expected = (
            "1. Capacidad de esfuerzo cardiopulmonar según consumo de oxígeno pico:\n\n"
            "2. Respuesta cronotrópica y carga máxima alcanzada:\n\n"
            "3. Clase funcional, VO₂ pico y relación VO₂/trabajo:\n\n"
            "4. Limitación ventilatoria al ejercicio:\n\n"
            "5. Respuesta cardiovascular, oxígeno latido y umbral anaerobio:\n\n"
            "6. Evaluación de posible limitación vascular pulmonar:\n\n"
            "7. Síntesis global e interpretación final de la prueba:"
        )
        self.assertEqual(INITIAL_CONCLUSIONES_DEFINITIVAS, expected)
        with patch("services.draft_workflow.take_for_signature", return_value=persisted) as take:
            result = take_draft_for_signature(
                draft=persisted,
                user_id=7,
                username="medico-sintetico",
                role=MEDICO,
            )
        self.assertIs(result, persisted)
        self.assertEqual(take.call_args.kwargs["initial_conclusions"], expected)


class SchemaAndDocumentationTests(TestCase):
    def test_incremental_migration_models_roles_states_audit_and_pdf_events(self) -> None:
        sql = Path("migrations/005_workflow_states_pdf_events.sql").read_text(encoding="utf-8")
        for term in ("COORDINADORA", "PRELIMINAR_BLOQUEADO", "medical_owner_user_id", "medical_taken_at", "report_workflow_audits", "report_pdf_events", "version_id"):
            self.assertIn(term, sql)

    def test_runtime_never_imports_legacy_report_draft_module(self) -> None:
        runtime = "\n".join(Path(path).read_text(encoding="utf-8") for path in ("routes/studies.py", "services/draft_workflow.py", "services/gx_data_source.py"))
        self.assertNotIn("services.report_draft", runtime)

    def test_logout_only_cleans_technical_locks(self) -> None:
        source = Path("repositories/drafts.py").read_text(encoding="utf-8")
        self.assertIn("technical locks", source)
        self.assertIn("DELETE FROM ergo_app.draft_locks", source)
