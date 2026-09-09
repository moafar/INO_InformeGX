"""Regression and mapping tests for the approved 93 report controls."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest import TestCase

from werkzeug.datastructures import MultiDict

from services.clinical_columns import CLINICAL_STUDY_COLUMN_KEYS
from services.report_controls import CALCULADO, CONTROL_TYPES, DIRECTO, INTERPRETACION, MANUAL
from services.study_report import (
    DERIVED_FIELD_SOURCES,
    DIRECT_FIELD_SOURCES,
    MAX_REPORT_FIELD_LENGTH,
    REPORT_CONTROL_IDS,
    VDVT_FIELD_SOURCES,
    ReportFormValidationError,
    build_derived_values,
    build_study_report_from_persisted,
    build_study_report_view,
    validated_field_values_from_form,
)


def clinical_row(**overrides: object) -> dict[str, object]:
    """Return a synthetic GX row with distinct VD/VT source alternatives."""
    row: dict[str, object] = {key: "" for key in CLINICAL_STUDY_COLUMN_KEYS}
    row.update(
        patient_id_num="90000001",
        patient_first_name="Ana",
        patient_last_name="Sintética",
        visit_datetime=datetime(2026, 8, 20, 17, 43, 15),
        gx_rest_ph="7.40",
        gx_vo2_max_ph="7.32",
        gx_rest_vd_per_vt_meas="25",
        gx_rest_vd_per_vt_est="30",
        gx_vo2_max_vd_per_vt_meas="18",
        gx_vo2_max_vd_per_vt_est="22",
    )
    row.update(overrides)
    return row


class VdvtPersistenceRegressionTests(TestCase):
    def test_persisted_view_preserves_measured_vdvt_values_and_provenance(self) -> None:
        initial = build_study_report_view(clinical_row())
        persisted = build_study_report_from_persisted(
            values={key: field.value for key, field in initial.fields.items()},
            originals={key: field.original_value for key, field in initial.fields.items()},
            edited={key: field.edited for key, field in initial.fields.items()},
            lookup_patient_id_num=initial.lookup_patient_id_num,
            lookup_visit_datetime=initial.lookup_visit_datetime,
            vdvt_metadata=initial.vdvt_metadata,
        )

        self.assertEqual(
            initial.field("gx_rest_vd_per_vt_meas").source_columns,
            ("gx_rest_vd_per_vt_meas",),
        )
        self.assertEqual(
            persisted.field("gx_rest_vd_per_vt_meas").source_columns,
            ("gx_rest_vd_per_vt_meas",),
        )
        self.assertEqual(
            persisted.vdvt_source_values["gx_rest_vd_per_vt_meas"],
            ("25", "30"),
        )
        self.assertEqual(
            persisted.vdvt_source_values["gx_vo2_max_vd_per_vt_meas"],
            ("18", "22"),
        )

    def test_vdvt_selection_switches_to_the_real_estimated_values(self) -> None:
        estimated = build_study_report_view(
            clinical_row(), submitted_values={"medicion_gases": "false"}
        )
        rebuilt = build_study_report_from_persisted(
            values={key: field.value for key, field in estimated.fields.items()},
            originals={key: field.original_value for key, field in estimated.fields.items()},
            edited={key: field.edited for key, field in estimated.fields.items()},
            lookup_patient_id_num=estimated.lookup_patient_id_num,
            lookup_visit_datetime=estimated.lookup_visit_datetime,
            vdvt_metadata=estimated.vdvt_metadata,
        )

        for report in (estimated, rebuilt):
            self.assertEqual(report.field("gx_rest_vd_per_vt_meas").value, "30")
            self.assertEqual(
                report.field("gx_rest_vd_per_vt_meas").source_columns,
                ("gx_rest_vd_per_vt_est",),
            )
            self.assertEqual(report.field("gx_vo2_max_vd_per_vt_meas").value, "22")
            self.assertEqual(
                report.field("gx_vo2_max_vd_per_vt_meas").source_columns,
                ("gx_vo2_max_vd_per_vt_est",),
            )

    def test_legacy_persisted_view_does_not_invent_vdvt_alternatives(self) -> None:
        persisted = build_study_report_from_persisted(
            values={"gx_rest_vd_per_vt_meas": "25", "medicion_gases": "true"},
            originals={"gx_rest_vd_per_vt_meas": "25", "medicion_gases": "true"},
            edited={},
            lookup_patient_id_num="90000001",
            lookup_visit_datetime="2026-08-20 17:43:15",
        )

        self.assertEqual(persisted.field("gx_rest_vd_per_vt_meas").value, "25")
        self.assertEqual(persisted.field("gx_rest_vd_per_vt_meas").source_columns, ())
        self.assertEqual(persisted.vdvt_source_values["gx_rest_vd_per_vt_meas"], ("", ""))

    def test_vdvt_switch_keeps_an_unavailable_alternative_empty(self) -> None:
        report = build_study_report_view(
            clinical_row(gx_rest_vd_per_vt_est=None, gx_vo2_max_vd_per_vt_est=""),
            submitted_values={"medicion_gases": "false"},
        )

        self.assertEqual(report.field("gx_rest_vd_per_vt_meas").value, "")
        self.assertEqual(
            report.field("gx_rest_vd_per_vt_meas").source_columns,
            ("gx_rest_vd_per_vt_est",),
        )
        self.assertEqual(report.vdvt_source_values["gx_rest_vd_per_vt_meas"], ("25", ""))


class ReportMappingTests(TestCase):
    def test_declared_sources_match_the_current_control_and_clinical_catalogues(self) -> None:
        direct_sources = set(DIRECT_FIELD_SOURCES) | set(VDVT_FIELD_SOURCES)
        calculated_sources = set(DERIVED_FIELD_SOURCES)

        self.assertEqual(direct_sources, {key for key, kind in CONTROL_TYPES.items() if kind == DIRECTO})
        self.assertEqual(
            calculated_sources,
            {key for key, kind in CONTROL_TYPES.items() if kind == CALCULADO},
        )
        for sources in (*DIRECT_FIELD_SOURCES.values(), *DERIVED_FIELD_SOURCES.values(), *VDVT_FIELD_SOURCES.values()):
            self.assertTrue(set(sources).issubset(CLINICAL_STUDY_COLUMN_KEYS))
        self.assertTrue(
            all(
                key not in direct_sources | calculated_sources
                for key, kind in CONTROL_TYPES.items()
                if kind in {MANUAL, INTERPRETACION}
            )
        )

    def test_direct_values_preserve_zero_and_convert_null_without_fallbacks(self) -> None:
        report = build_study_report_view(
            clinical_row(weight=Decimal("0"), diagnosis=None, gx_rest_hr_bpm=0, height=Decimal("1.72"))
        )

        self.assertEqual(report.field("weight").source_columns, ("weight",))
        self.assertEqual(report.field("weight").original_value, "0")
        self.assertEqual(report.field("weight").value, "0")
        self.assertFalse(report.field("weight").edited)
        self.assertEqual(report.field("gx_rest_hr_bpm").value, "0")
        self.assertEqual(report.field("diagnosis").value, "")
        self.assertEqual(report.field("height").value, "172")
        self.assertEqual(report.field("diagnosis").origin, "GX")

    def test_existing_calculated_formulas_cover_all_eight_controls(self) -> None:
        values = build_derived_values(
            clinical_row(
                gx_vo2_max_hr_bpm="160",
                gx_predicted_hr_bpm="170",
                gx_vo2_max_vo2_ml_per_min="1800",
                gx_predicted_vo2_ml_per_min="2000",
                gx_vo2_max_work_watts="150",
                gx_predicted_work_watts="170",
                gx_vo2_max_vo2_per_hr_ml_per_beat="11.2",
                gx_predicted_vo2_per_hr_ml_per_beat="9.8",
                gx_at_vo2_ml_per_min="720",
                pf_pre_mvv_l_per_min="70",
                gx_vo2_max_ve_btps_l_per_min="55",
            )
        )

        self.assertEqual(
            values,
            {
                "porc_fc_maxima": "94.12",
                "medicion_gases": True,
                "porc_o2_predicho": "90",
                "porc_vo2_predicho": "90",
                "carga_max_w": "88.24",
                "porc_pred_o2_latido_6": "114.29",
                "porc_vo2_at_predicho": "36",
                "reserva_respiratoria_pico_l": "15",
            },
        )

    def test_calculated_formulas_handle_absence_zero_denominators_and_zero_numerators(self) -> None:
        invalid = build_derived_values(
            clinical_row(
                gx_vo2_max_hr_bpm="0",
                gx_predicted_hr_bpm="170",
                gx_vo2_max_vo2_ml_per_min="0",
                gx_predicted_vo2_ml_per_min=None,
                gx_vo2_max_work_watts="150",
                gx_predicted_work_watts="0",
                gx_vo2_max_vo2_per_hr_ml_per_beat="11.2",
                gx_predicted_vo2_per_hr_ml_per_beat="",
                gx_at_vo2_ml_per_min=None,
                pf_pre_mvv_l_per_min="0",
                gx_vo2_max_ve_btps_l_per_min="0",
                gx_rest_ph=None,
            )
        )

        self.assertEqual(invalid["porc_fc_maxima"], "0")
        self.assertEqual(invalid["porc_o2_predicho"], "")
        self.assertEqual(invalid["porc_vo2_predicho"], "")
        self.assertEqual(invalid["carga_max_w"], "")
        self.assertEqual(invalid["porc_pred_o2_latido_6"], "")
        self.assertEqual(invalid["porc_vo2_at_predicho"], "")
        self.assertEqual(invalid["reserva_respiratoria_pico_l"], "0")
        self.assertFalse(invalid["medicion_gases"])

    def test_manual_and_interpretation_controls_start_empty_and_keep_explicit_values(self) -> None:
        empty = build_study_report_view(clinical_row())
        self.assertTrue(
            all(empty.field(key).value == "" for key, kind in CONTROL_TYPES.items() if kind in {MANUAL, INTERPRETACION})
        )

        report = build_study_report_view(
            clinical_row(),
            submitted_values={
                "hb": "13.2",
                "conclusiones_definitivas": "Conclusión sintética",
            },
        )
        self.assertEqual(report.field("hb").variable_type, MANUAL)
        self.assertEqual(report.field("hb").value, "13.2")
        self.assertEqual(report.field("hb").original_value, "")
        self.assertFalse(report.field("hb").edited)
        self.assertEqual(report.field("conclusiones_definitivas").variable_type, INTERPRETACION)
        self.assertEqual(report.field("conclusiones_definitivas").value, "Conclusión sintética")
        self.assertFalse(report.field("conclusiones_definitivas").edited)

    def test_direct_and_calculated_edits_keep_original_values_intact(self) -> None:
        report = build_study_report_view(
            clinical_row(gx_vo2_max_hr_bpm="160", gx_predicted_hr_bpm="170"),
            submitted_values={
                "diagnosis": "Corrección explícita",
                "porc_fc_maxima": "95",
                "hb": "13.2",
                "conclusiones_definitivas": "Conclusión sintética",
            },
        )

        direct = report.field("diagnosis")
        calculated = report.field("porc_fc_maxima")
        self.assertEqual((direct.original_value, direct.value, direct.edited), ("", "Corrección explícita", True))
        self.assertEqual((calculated.original_value, calculated.value, calculated.edited), ("94.12", "95", True))
        self.assertEqual(report.field("hb").origin_label, MANUAL)
        self.assertEqual(report.field("conclusiones_definitivas").origin_label, INTERPRETACION)

    def test_form_validation_ignores_unknown_metadata_and_resolves_checkbox_default(self) -> None:
        values = validated_field_values_from_form(
            MultiDict([("unknown_request_metadata", "ignored"), ("diagnosis", "DX")])
        )

        self.assertEqual(values, {"diagnosis": "DX", "medicion_gases": "false"})
        self.assertTrue(set(values).issubset(REPORT_CONTROL_IDS))

    def test_form_validation_rejects_duplicate_or_invalid_approved_controls(self) -> None:
        with self.assertRaisesRegex(ReportFormValidationError, "duplicado"):
            validated_field_values_from_form(
                MultiDict([("conclusiones_definitivas", "Uno"), ("conclusiones_definitivas", "Dos")])
            )
        with self.assertRaisesRegex(ReportFormValidationError, "no es válido"):
            validated_field_values_from_form(
                MultiDict([("conclusiones_definitivas", "x" * (MAX_REPORT_FIELD_LENGTH + 1))])
            )
