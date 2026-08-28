"""Preparation of the approved 87-control study report form.

The clinical row is treated as immutable source data.  Values submitted by the
ephemeral form may temporarily correct a GX control, but the original GX value
and its source columns remain available to the view so the correction is never
silent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from typing import Iterable, Mapping, Protocol

from services.names import format_visit_datetime


REPORT_CONTROL_IDS = (
    "patient_first_name", "patient_middle_name", "patient_last_name", "age", "sex",
    "visit_date", "patient_id_num", "motivo_remision", "diagnosis", "weight", "height",
    "bmi", "hb", "hc", "disnea_mrc", "tbco_prod", "pk_yrs", "biomasa", "oxigeno",
    "medicamentos", "gx_vo2_max_time_min", "gx_vo2_max_work_watts", "porc_fc_maxima",
    "disnea_borg_inicial", "disnea_borg_final", "fatiga_borg_inicial", "fatiga_borg_final",
    "cambio_watts_por_etapa", "medicion_gases", "gx_vo2_max_rer", "porc_o2_predicho",
    "sugerencia_rer", "gx_rest_vo2_ml_per_min", "gx_rest_vo2_ml_per_kg_per_min",
    "interpretacion_consumo_vo2", "porc_vo2_predicho", "carga_max_w",
    "interpretacion_prueba_cp", "gx_vo2_max_vo2_ml_per_min",
    "gx_vo2_max_vo2_ml_per_kg_per_min_1", "clase_funcional", "relacion_consumo_trabajo",
    "interpretacion_relacion_consumo_trabajo", "ritmo_cardio_inicial", "gx_rest_hr_bpm",
    "gx_vo2_max_hr_bpm", "calif_fc", "ritmo_ekg", "gx_rest_sysbp_mmhg",
    "gx_rest_diabp_mmhg", "gx_vo2_max_sysbp_mmhg", "gx_vo2_max_diabp_mmhg",
    "latidos_recuperados_minuto", "vo2_minuto", "porc_pred_o2_latido_6",
    "interpretacion_o2_latido_6", "umbral_anaerobio_alcanzado",
    "interpretacion_curva_flujo_volumen", "pf_pre_mvv_l_per_min",
    "gx_rest_ve_btps_l_per_min", "comportamiento_vvm", "gx_vo2_max_ve_btps_l_per_min",
    "reserva_respiratoria_pico_l", "interpretacion_reserva_pico_vvm",
    "gx_vo2_max_ve_per_mvv_pct", "gx_vo2_max_vt_per_ic_pct", "gx_rest_rr_br_per_min",
    "gx_vo2_max_rr_br_per_min_1", "observaciones_asa_volumen_corriente",
    "observaciones_volumen_minuto", "interpretacion_fr_maxima", "gx_rest_spo2_pct",
    "gx_vo2_max_spo2_pct", "gx_rest_vd_per_vt_meas", "gx_vo2_max_vd_per_vt_meas",
    "relacion_vdvt_reposo", "comportamiento_relacion_vdvt", "gx_at_ve_per_vco2",
    "gx_at_ve_per_vo2", "gx_rest_petco2_mmhg", "comportamiento_petco2_rest_ejercicio_total",
    "comportamiento_petco2_rest_ejercicio_maximo", "interpretacion_petco2_pico_reposo",
    "gx_vo2_max_vo2_ml_per_kg_per_min_2",
    "gx_vo2_max_vo2workslope_ml_per_min_per_watt", "gx_vo2_max_rr_br_per_min_2",
    "conclusiones_definitivas",
)


DIRECT_FIELD_SOURCES: dict[str, tuple[str, ...]] = {
    "patient_first_name": ("patient_first_name",),
    "patient_middle_name": ("patient_middle_name",),
    "patient_last_name": ("patient_last_name",),
    "age": ("age",),
    "sex": ("sex",),
    "visit_date": ("visit_datetime",),
    "patient_id_num": ("patient_id_num",),
    "diagnosis": ("diagnosis",),
    "weight": ("weight",),
    "height": ("height",),
    "bmi": ("bmi",),
    "tbco_prod": ("tbco_prod",),
    "pk_yrs": ("pk_yrs",),
    "gx_vo2_max_time_min": ("gx_vo2_max_time_min",),
    "gx_vo2_max_work_watts": ("gx_vo2_max_work_watts",),
    "gx_vo2_max_rer": ("gx_vo2_max_rer",),
    "gx_rest_vo2_ml_per_min": ("gx_rest_vo2_ml_per_min",),
    "gx_rest_vo2_ml_per_kg_per_min": ("gx_rest_vo2_ml_per_kg_per_min",),
    "gx_vo2_max_vo2_ml_per_min": ("gx_vo2_max_vo2_ml_per_min",),
    "gx_vo2_max_vo2_ml_per_kg_per_min_1": ("gx_vo2_max_vo2_ml_per_kg_per_min",),
    "relacion_consumo_trabajo": ("gx_vo2_max_vo2workslope_ml_per_min_per_watt",),
    "gx_rest_hr_bpm": ("gx_rest_hr_bpm",),
    "gx_vo2_max_hr_bpm": ("gx_vo2_max_hr_bpm",),
    "gx_rest_sysbp_mmhg": ("gx_rest_sysbp_mmhg",),
    "gx_rest_diabp_mmhg": ("gx_rest_diabp_mmhg",),
    "gx_vo2_max_sysbp_mmhg": ("gx_vo2_max_sysbp_mmhg",),
    "gx_vo2_max_diabp_mmhg": ("gx_vo2_max_diabp_mmhg",),
    "pf_pre_mvv_l_per_min": ("pf_pre_mvv_l_per_min",),
    "gx_rest_ve_btps_l_per_min": ("gx_rest_ve_btps_l_per_min",),
    "gx_vo2_max_ve_btps_l_per_min": ("gx_vo2_max_ve_btps_l_per_min",),
    "gx_vo2_max_ve_per_mvv_pct": ("gx_vo2_max_ve_per_mvv_pct",),
    "gx_vo2_max_vt_per_ic_pct": ("gx_vo2_max_vt_per_ic_pct",),
    "gx_rest_rr_br_per_min": ("gx_rest_rr_br_per_min",),
    "gx_vo2_max_rr_br_per_min_1": ("gx_vo2_max_rr_br_per_min",),
    "gx_rest_spo2_pct": ("gx_rest_spo2_pct",),
    "gx_vo2_max_spo2_pct": ("gx_vo2_max_spo2_pct",),
    "gx_rest_vd_per_vt_meas": ("gx_rest_vd_per_vt_meas",),
    "gx_vo2_max_vd_per_vt_meas": ("gx_vo2_max_vd_per_vt_meas",),
    "gx_at_ve_per_vco2": ("gx_at_ve_per_vco2",),
    "gx_at_ve_per_vo2": ("gx_at_ve_per_vo2",),
    "gx_rest_petco2_mmhg": ("gx_rest_petco2_mmhg",),
    "gx_vo2_max_vo2_ml_per_kg_per_min_2": ("gx_vo2_max_vo2_ml_per_kg_per_min",),
    "gx_vo2_max_vo2workslope_ml_per_min_per_watt": (
        "gx_vo2_max_vo2workslope_ml_per_min_per_watt",
    ),
    "gx_vo2_max_rr_br_per_min_2": ("gx_vo2_max_rr_br_per_min",),
}


DERIVED_FIELD_SOURCES: dict[str, tuple[str, ...]] = {
    "porc_fc_maxima": ("gx_vo2_max_hr_bpm", "gx_predicted_hr_bpm"),
    "medicion_gases": ("gx_rest_ph", "gx_vo2_max_ph"),
    "porc_o2_predicho": ("gx_vo2_max_vo2_ml_per_min", "gx_predicted_vo2_ml_per_min"),
    "porc_vo2_predicho": ("gx_vo2_max_vo2_ml_per_min", "gx_predicted_vo2_ml_per_min"),
    "carga_max_w": ("gx_vo2_max_work_watts", "gx_predicted_work_watts"),
    "porc_pred_o2_latido_6": (
        "gx_vo2_max_vo2_per_hr_ml_per_beat",
        "gx_predicted_vo2_per_hr_ml_per_beat",
    ),
    "reserva_respiratoria_pico_l": (
        "pf_pre_mvv_l_per_min",
        "gx_vo2_max_ve_btps_l_per_min",
    ),
}

MANUAL_CONTROL_IDS = frozenset(REPORT_CONTROL_IDS) - DIRECT_FIELD_SOURCES.keys() - DERIVED_FIELD_SOURCES.keys()

MAX_REPORT_FIELD_LENGTH = 20_000


class ReportFormValidationError(ValueError):
    """Raised when a report POST cannot represent one unambiguous form state."""


class _MultiValueForm(Protocol):
    def getlist(self, key: str) -> list[str]: ...


@dataclass(frozen=True, slots=True)
class ReportField:
    """One report control with its resolved value and traceability."""

    key: str
    origin: str
    source_columns: tuple[str, ...]
    original_value: object
    value: object
    edited: bool

    @property
    def source_label(self) -> str:
        return ", ".join(self.source_columns) if self.source_columns else "Sin columna fuente"

    @property
    def origin_label(self) -> str:
        if self.origin == "GX" and self.edited:
            return "GX · Editado"
        return self.origin


@dataclass(frozen=True, slots=True)
class StudyReportView:
    """Complete state used by the approved Jinja report form."""

    fields: Mapping[str, ReportField]
    lookup_patient_id_num: str
    lookup_visit_datetime: str
    patient_full_name: str

    def field(self, key: str) -> ReportField:
        return self.fields[key]


def _serialize(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return format_visit_datetime(value)
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def _decimal(value: object) -> Decimal | None:
    text = _serialize(value).strip()
    if not text:
        return None
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def _height_centimeters(value: object) -> str:
    """Apply the pre-existing presentation rule for metre-like height values."""
    text = _serialize(value)
    number = _decimal(value)
    if number is None or number > 10:
        return text
    return _format_derived(number * Decimal(100))


def _format_derived(value: Decimal, *, places: int | None = None) -> str:
    if places is not None:
        quantum = Decimal(1).scaleb(-places)
        value = value.quantize(quantum, rounding=ROUND_HALF_UP)
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _percentage(row: Mapping[str, object], numerator_key: str, denominator_key: str) -> str:
    numerator = _decimal(row.get(numerator_key))
    denominator = _decimal(row.get(denominator_key))
    if numerator is None or denominator is None or denominator == 0:
        return ""
    with localcontext() as context:
        context.prec = 28
        return _format_derived((numerator / denominator) * Decimal(100), places=2)


def build_derived_values(row: Mapping[str, object]) -> dict[str, object]:
    """Calculate only the seven relationships defined by the approved report.

    Percentages are measured/predicted * 100 and displayed to at most two
    decimals. Respiratory reserve is MVV minus peak VE. Gas measurement is true
    only when both the rest and peak pH source values are present.
    """
    mvv = _decimal(row.get("pf_pre_mvv_l_per_min"))
    peak_ve = _decimal(row.get("gx_vo2_max_ve_btps_l_per_min"))
    reserve = "" if mvv is None or peak_ve is None else _format_derived(mvv - peak_ve)
    measured_gases = (
        _serialize(row.get("gx_rest_ph")).strip() != ""
        and _serialize(row.get("gx_vo2_max_ph")).strip() != ""
    )
    vo2_percentage = _percentage(
        row,
        "gx_vo2_max_vo2_ml_per_min",
        "gx_predicted_vo2_ml_per_min",
    )
    return {
        "porc_fc_maxima": _percentage(row, "gx_vo2_max_hr_bpm", "gx_predicted_hr_bpm"),
        "medicion_gases": measured_gases,
        "porc_o2_predicho": vo2_percentage,
        "porc_vo2_predicho": vo2_percentage,
        "carga_max_w": _percentage(row, "gx_vo2_max_work_watts", "gx_predicted_work_watts"),
        "porc_pred_o2_latido_6": _percentage(
            row,
            "gx_vo2_max_vo2_per_hr_ml_per_beat",
            "gx_predicted_vo2_per_hr_ml_per_beat",
        ),
        "reserva_respiratoria_pico_l": reserve,
    }


def field_values_from_form(items: Iterable[tuple[str, str]]) -> dict[str, str]:
    """Keep only approved controls from an ephemeral report submission."""
    submitted = {key: value for key, value in items if key in REPORT_CONTROL_IDS}
    if submitted and "medicion_gases" not in submitted:
        submitted["medicion_gases"] = "false"
    return submitted


def validated_field_values_from_form(form: _MultiValueForm) -> dict[str, str]:
    """Validate and resolve one value for every submitted approved control.

    Unknown request metadata is ignored, but duplicated approved controls and
    oversized values are rejected so the PDF cannot be built from an ambiguous
    or unbounded submission.
    """
    submitted: dict[str, str] = {}
    for key in REPORT_CONTROL_IDS:
        values = form.getlist(key)
        if len(values) > 1:
            raise ReportFormValidationError(f"El campo {key} está duplicado.")
        if not values:
            continue
        value = values[0]
        if not isinstance(value, str):
            raise ReportFormValidationError(f"El campo {key} no es válido.")
        if len(value) > MAX_REPORT_FIELD_LENGTH or "\x00" in value:
            raise ReportFormValidationError(f"El campo {key} no es válido.")
        submitted[key] = value

    if submitted and "medicion_gases" not in submitted:
        submitted["medicion_gases"] = "false"
    return submitted


def build_study_report_view(
    row: Mapping[str, object],
    submitted_values: Mapping[str, str] | None = None,
) -> StudyReportView:
    """Resolve GX, derived and manual controls without changing the source row."""
    submitted = submitted_values or {}
    derived = build_derived_values(row)
    fields: dict[str, ReportField] = {}
    for key in REPORT_CONTROL_IDS:
        if key in DIRECT_FIELD_SOURCES:
            sources = DIRECT_FIELD_SOURCES[key]
            original = _serialize(row.get(sources[0]))
            if key == "visit_date":
                original = format_visit_datetime(row.get(sources[0]))
            elif key == "height":
                original = _height_centimeters(row.get(sources[0]))
            origin = "GX"
        elif key in DERIVED_FIELD_SOURCES:
            sources = DERIVED_FIELD_SOURCES[key]
            original = _serialize(derived[key])
            origin = "GX"
        else:
            sources = ()
            original = ""
            origin = "MANUAL"

        value: object = submitted[key] if key in submitted else original
        fields[key] = ReportField(
            key=key,
            origin=origin,
            source_columns=sources,
            original_value=original,
            value=value,
            edited=origin == "GX" and key in submitted and _serialize(value) != _serialize(original),
        )

    return StudyReportView(
        fields=fields,
        lookup_patient_id_num=_serialize(row.get("patient_id_num")).strip(),
        lookup_visit_datetime=format_visit_datetime(row.get("visit_datetime")),
        patient_full_name=" ".join(
            part
            for part in (
                _serialize(row.get("patient_first_name")).strip(),
                _serialize(row.get("patient_middle_name")).strip(),
                _serialize(row.get("patient_last_name")).strip(),
            )
            if part
        ),
    )
