"""Preparation of the approved 93-control study report form.

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
from services.clinical_columns import CLINICAL_STUDY_COLUMN_KEYS
from services.report_controls import CONTROL_TYPES, DIRECTO, CALCULADO


REPORT_CONTROL_IDS = (
    "patient_first_name", "patient_middle_name", "patient_last_name", "age", "sex",
    "visit_date", "patient_id_num", "motivo_remision", "diagnosis", "weight", "height",
    "bmi", "hb", "hc", "disnea_mrc", "tbco_prod", "pk_yrs", "biomasa", "oxigeno",
    "medicamentos", "gx_vo2_max_time_min", "reposo_inicial_min", "tiempo_sin_carga_min",
    "gx_vo2_max_work_watts", "porc_fc_maxima",
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
    "gx_vo2_max_vo2_per_hr_ml_per_beat", "interpretacion_o2_latido_6",
    "umbral_anaerobio_alcanzado", "gx_at_ex_time_min", "porc_vo2_at_predicho",
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
    "comentario_petco2",
    "gx_vo2_max_vo2_ml_per_kg_per_min_2",
    "gx_vo2_max_vo2workslope_ml_per_min_per_watt", "gx_vo2_max_rr_br_per_min_2",
    "conclusiones_definitivas",
)

if set(REPORT_CONTROL_IDS) != set(CONTROL_TYPES):
    raise RuntimeError("La clasificación aprobada debe cubrir exactamente los 93 controles.")


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
    "gx_vo2_max_time_min": ("gx_vo2_max_time_sec",),
    "gx_at_ex_time_min": ("gx_at_ex_time_sec",),
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
    "gx_vo2_max_vo2_per_hr_ml_per_beat": (
        "gx_vo2_max_vo2_per_hr_ml_per_beat",
    ),
    "pf_pre_mvv_l_per_min": ("pf_pre_mvv_l_per_min",),
    "gx_rest_ve_btps_l_per_min": ("gx_rest_ve_btps_l_per_min",),
    "gx_vo2_max_ve_btps_l_per_min": ("gx_vo2_max_ve_btps_l_per_min",),
    "gx_vo2_max_ve_per_mvv_pct": ("gx_vo2_max_ve_per_mvv_pct",),
    "gx_vo2_max_vt_per_ic_pct": ("gx_vo2_max_vt_per_ic_pct",),
    "gx_rest_rr_br_per_min": ("gx_rest_rr_br_per_min",),
    "gx_vo2_max_rr_br_per_min_1": ("gx_vo2_max_rr_br_per_min",),
    "gx_rest_spo2_pct": ("gx_rest_spo2_pct",),
    "gx_vo2_max_spo2_pct": ("gx_vo2_max_spo2_pct",),
    "gx_at_ve_per_vco2": ("gx_at_ve_per_vco2",),
    "gx_at_ve_per_vo2": ("gx_at_ve_per_vo2",),
    "gx_rest_petco2_mmhg": ("gx_rest_petco2_mmhg",),
    "gx_vo2_max_vo2_ml_per_kg_per_min_2": ("gx_vo2_max_vo2_ml_per_kg_per_min",),
    "gx_vo2_max_vo2workslope_ml_per_min_per_watt": (
        "gx_vo2_max_vo2workslope_ml_per_min_per_watt",
    ),
    "gx_vo2_max_rr_br_per_min_2": ("gx_vo2_max_rr_br_per_min",),
}


VDVT_FIELD_SOURCES: dict[str, tuple[str, str]] = {
    "gx_rest_vd_per_vt_meas": ("gx_rest_vd_per_vt_meas", "gx_rest_vd_per_vt_est"),
    "gx_vo2_max_vd_per_vt_meas": (
        "gx_vo2_max_vd_per_vt_meas",
        "gx_vo2_max_vd_per_vt_est",
    ),
}

VDVT_MEASURED_SOURCE = "measured"
VDVT_ESTIMATED_SOURCE = "estimated"


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
    "porc_vo2_at_predicho": (
        "gx_at_vo2_ml_per_min",
        "gx_predicted_vo2_ml_per_min",
    ),
    "reserva_respiratoria_pico_l": (
        "pf_pre_mvv_l_per_min",
        "gx_vo2_max_ve_btps_l_per_min",
    ),
}

MANUAL_CONTROL_IDS = (
    frozenset(REPORT_CONTROL_IDS)
    - DIRECT_FIELD_SOURCES.keys()
    - DERIVED_FIELD_SOURCES.keys()
    - VDVT_FIELD_SOURCES.keys()
)

MAX_REPORT_FIELD_LENGTH = 20_000


class ReportFormValidationError(ValueError):
    """Raised when a report POST cannot represent one unambiguous form state."""


class _MultiValueForm(Protocol):
    def getlist(self, key: str) -> list[str]: ...


@dataclass(frozen=True, slots=True)
class ReportField:
    """One report control with its resolved value and traceability."""

    key: str
    variable_type: str
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
        return f"{self.variable_type} · EDITADO" if self.edited else self.variable_type


@dataclass(frozen=True, slots=True)
class StudyReportView:
    """Complete state used by the approved Jinja report form."""

    fields: Mapping[str, ReportField]
    lookup_patient_id_num: str
    lookup_visit_datetime: str
    patient_full_name: str
    vdvt_source_values: Mapping[str, tuple[str, str]]
    vdvt_metadata: Mapping[str, object] | None = None

    def field(self, key: str) -> ReportField:
        return self.fields[key]


def build_study_report_from_persisted(
    *,
    values: Mapping[str, object],
    originals: Mapping[str, object],
    edited: Mapping[str, bool],
    lookup_patient_id_num: str,
    lookup_visit_datetime: str,
    vdvt_metadata: Mapping[str, object] | None = None,
) -> StudyReportView:
    """Build the report only from a persisted draft/version snapshot.

    This intentionally does not re-query or recompute clinical values: a signed
    version must render exactly the state that was persisted.
    """
    persisted_vdvt_metadata = _normalize_vdvt_metadata(vdvt_metadata)
    fields = {
        key: ReportField(
            key=key,
            variable_type=CONTROL_TYPES[key],
            origin="GX" if CONTROL_TYPES[key] in {DIRECTO, CALCULADO} else "MANUAL",
            source_columns=(
                DIRECT_FIELD_SOURCES.get(key)
                or DERIVED_FIELD_SOURCES.get(key)
                or _vdvt_source_columns(key, persisted_vdvt_metadata)
                or ()
            ),
            original_value=_serialize(originals.get(key, "")),
            value=_serialize(values.get(key, "")),
            edited=bool(edited.get(key, False)),
        )
        for key in REPORT_CONTROL_IDS
    }
    patient_full_name = " ".join(
        value for value in (
            _serialize(values.get("patient_first_name", "")).strip(),
            _serialize(values.get("patient_middle_name", "")).strip(),
            _serialize(values.get("patient_last_name", "")).strip(),
        ) if value
    )
    return StudyReportView(
        fields=fields,
        lookup_patient_id_num=lookup_patient_id_num,
        lookup_visit_datetime=lookup_visit_datetime,
        patient_full_name=patient_full_name,
        vdvt_source_values={
            key: _vdvt_source_pair(persisted_vdvt_metadata, key)
            for key in VDVT_FIELD_SOURCES
        },
        vdvt_metadata=persisted_vdvt_metadata,
    )


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


def _format_duration_minutes_seconds(value: object) -> str:
    """Format a positive total-seconds source value as ``MM:SS``.

    The clinical source stores the total seconds as text.  Values that cannot
    unambiguously represent a positive whole number of seconds remain absent.
    """
    seconds = _decimal(value)
    if seconds is None or seconds <= 0 or seconds != seconds.to_integral_value():
        return ""
    total_seconds = int(seconds)
    minutes, remaining_seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{remaining_seconds:02d}"


def _percentage(row: Mapping[str, object], numerator_key: str, denominator_key: str) -> str:
    numerator = _decimal(row.get(numerator_key))
    denominator = _decimal(row.get(denominator_key))
    if numerator is None or denominator is None or denominator == 0:
        return ""
    with localcontext() as context:
        context.prec = 28
        return _format_derived((numerator / denominator) * Decimal(100), places=2)


def _is_checked(value: object) -> bool:
    return _serialize(value).strip().casefold() in {"1", "true", "si", "sí"}


def vdvt_source_for_medicion_gases(value: object) -> str:
    """Return the selected VD/VT clinical source for a gas-measurement value."""
    return VDVT_MEASURED_SOURCE if _is_checked(value) else VDVT_ESTIMATED_SOURCE


def _normalize_vdvt_metadata(metadata: Mapping[str, object] | None) -> dict[str, object] | None:
    """Validate the narrow VD/VT snapshot structure without inferring legacy data."""
    if not isinstance(metadata, Mapping):
        return None
    selected_source = metadata.get("selected_source")
    values = metadata.get("values")
    if selected_source not in {VDVT_MEASURED_SOURCE, VDVT_ESTIMATED_SOURCE} or not isinstance(values, Mapping):
        return None
    normalized_values: dict[str, dict[str, str]] = {}
    for key in VDVT_FIELD_SOURCES:
        pair = values.get(key)
        if not isinstance(pair, Mapping):
            return None
        measured = pair.get(VDVT_MEASURED_SOURCE)
        estimated = pair.get(VDVT_ESTIMATED_SOURCE)
        if not isinstance(measured, str) or not isinstance(estimated, str):
            return None
        normalized_values[key] = {
            VDVT_MEASURED_SOURCE: measured,
            VDVT_ESTIMATED_SOURCE: estimated,
        }
    return {"selected_source": selected_source, "values": normalized_values}


def _vdvt_metadata_from_row(row: Mapping[str, object], selected_source: str) -> dict[str, object]:
    return {
        "selected_source": selected_source,
        "values": {
            key: {
                VDVT_MEASURED_SOURCE: _serialize(row.get(measured_source)),
                VDVT_ESTIMATED_SOURCE: _serialize(row.get(estimated_source)),
            }
            for key, (measured_source, estimated_source) in VDVT_FIELD_SOURCES.items()
        },
    }


def _vdvt_source_columns(key: str, metadata: Mapping[str, object] | None) -> tuple[str, ...]:
    if metadata is None or key not in VDVT_FIELD_SOURCES:
        return ()
    selected_source = metadata["selected_source"]
    measured_source, estimated_source = VDVT_FIELD_SOURCES[key]
    return (measured_source if selected_source == VDVT_MEASURED_SOURCE else estimated_source,)


def _vdvt_source_pair(metadata: Mapping[str, object] | None, key: str) -> tuple[str, str]:
    if metadata is None:
        return "", ""
    values = metadata["values"]
    pair = values[key]
    return pair[VDVT_MEASURED_SOURCE], pair[VDVT_ESTIMATED_SOURCE]


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
        "porc_vo2_at_predicho": _percentage(
            row,
            "gx_at_vo2_ml_per_min",
            "gx_predicted_vo2_ml_per_min",
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
    use_measured_vdvt = (
        _is_checked(submitted["medicion_gases"])
        if "medicion_gases" in submitted
        else bool(derived["medicion_gases"])
    )
    vdvt_metadata = _vdvt_metadata_from_row(
        row,
        vdvt_source_for_medicion_gases(use_measured_vdvt),
    )
    fields: dict[str, ReportField] = {}
    for key in REPORT_CONTROL_IDS:
        if key in DIRECT_FIELD_SOURCES:
            sources = DIRECT_FIELD_SOURCES[key]
            original = _serialize(row.get(sources[0]))
            if key == "visit_date":
                original = format_visit_datetime(row.get(sources[0]))
            elif key == "height":
                original = _height_centimeters(row.get(sources[0]))
            elif key in ("gx_vo2_max_time_min", "gx_at_ex_time_min"):
                original = _format_duration_minutes_seconds(row.get(sources[0]))
            origin = "GX"
        elif key in VDVT_FIELD_SOURCES:
            sources = _vdvt_source_columns(key, vdvt_metadata)
            original = _serialize(row.get(sources[0]))
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
            variable_type=CONTROL_TYPES[key],
            origin=origin,
            source_columns=sources,
            original_value=original,
            value=value,
            edited=(
                CONTROL_TYPES[key] in {DIRECTO, CALCULADO}
                and key in submitted
                and _serialize(value) != _serialize(original)
            ),
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
        vdvt_source_values={
            key: _vdvt_source_pair(vdvt_metadata, key)
            for key in VDVT_FIELD_SOURCES
        },
        vdvt_metadata=vdvt_metadata,
    )
