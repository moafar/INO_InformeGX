"""Declarative, ephemeral study report model and render helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from services.names import format_full_name, format_visit_datetime


DIRECTO = "DIRECTO"
CALCULADO = "CALCULADO"
MANUAL = "MANUAL"
INTERPRETACION = "INTERPRETACIÓN"
PENDIENTE = "Pendiente"
MODIFICADO = "Modificado"
MANUAL_DILIGENCIADO = "Diligenciado manualmente"
GX_DILIGENCIADO = "Diligenciado desde GX"


CLINICAL_STUDY_COLUMN_KEYS = (
    "patient_id_num",
    "patient_first_name",
    "patient_middle_name",
    "patient_last_name",
    "visit_datetime",
    "age",
    "sex",
    "diagnosis",
    "dyspnea",
    "cough",
    "wheez",
    "tbco_prod",
    "pk_yrs",
    "weight",
    "height",
    "bmi",
    "gx_vo2_max_time_min",
    "gx_vo2_max_work_watts",
    "gx_vo2_max_rer",
    "gx_rest_vo2_ml_per_min",
    "gx_rest_vo2_ml_per_kg_per_min",
    "gx_vo2_max_vo2_ml_per_min",
    "gx_vo2_max_vo2_ml_per_kg_per_min",
    "gx_vo2_max_vo2workslope_ml_per_min_per_watt",
    "gx_predicted_vo2_ml_per_min",
    "gx_predicted_vo2_ml_per_kg_per_min",
    "gx_predicted_work_watts",
    "gx_predicted_vo2workslope_ml_per_min_per_watt",
    "gx_rest_hr_bpm",
    "gx_vo2_max_hr_bpm",
    "gx_predicted_hr_bpm",
    "gx_rest_sysbp_mmhg",
    "gx_rest_diabp_mmhg",
    "gx_vo2_max_sysbp_mmhg",
    "gx_vo2_max_diabp_mmhg",
    "gx_rest_vo2_per_hr_ml_per_beat",
    "gx_vo2_max_vo2_per_hr_ml_per_beat",
    "gx_predicted_vo2_per_hr_ml_per_beat",
    "pf_pre_mvv_l_per_min",
    "gx_rest_ve_btps_l_per_min",
    "gx_vo2_max_ve_btps_l_per_min",
    "gx_vo2_max_ve_per_mvv_pct",
    "gx_vo2_max_vt_per_ic_pct",
    "gx_rest_rr_br_per_min",
    "gx_vo2_max_rr_br_per_min",
    "gx_rest_spo2_pct",
    "gx_vo2_max_spo2_pct",
    "gx_rest_vd_per_vt_meas",
    "gx_vo2_max_vd_per_vt_meas",
    "gx_rest_petco2_mmhg",
    "gx_vo2_max_petco2_mmhg",
    "gx_rest_ph",
    "gx_vo2_max_ph",
    "gx_at_ve_per_vco2",
    "gx_at_ve_per_vo2",
)


def _clean_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _has_text(value) -> bool:
    return _clean_text(value) != ""


def _format_height_cm(value) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    try:
        number = float(text.replace(",", "."))
    except ValueError:
        return text
    if number <= 10:
        centimeters = number * 100
        return str(int(centimeters)) if centimeters.is_integer() else f"{centimeters:g}"
    return text


def _sentence(value: str) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    if text[-1] in ".!?":
        return text
    return f"{text}."


def _strip_terminal(value: str) -> str:
    text = _clean_text(value)
    while text and text[-1] in ".!?":
        text = text[:-1]
    return text


def _format_map(template: str, context: Mapping[str, str]) -> str:
    class _SafeDict(dict):
        def __missing__(self, key):  # pragma: no cover - defensive
            return ""

    return template.format_map(_SafeDict(context))


@dataclass(frozen=True, slots=True)
class NarrativePartSpec:
    template: str
    required_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReportValueSpec:
    key: str
    label: str
    source_keys: tuple[str, ...]
    unit: str = ""
    input_type: str = "text"
    rows: int = 1
    transform: str = ""
    presentation_width: str = "auto"


@dataclass(frozen=True, slots=True)
class ReportElementSpec:
    key: str
    order: int
    title: str
    origin: str
    values: tuple[ReportValueSpec, ...]
    narrative_style: str
    narrative_template: str
    narrative_parts: tuple[NarrativePartSpec, ...]
    section_key: str
    section_title: str
    section_order: int
    presentation_layout: str = "single"
    narrative_always_visible: bool = False
    narrative_empty_heading_only: bool = False

    @property
    def source_columns(self) -> tuple[str, ...]:
        columns: list[str] = []
        for value in self.values:
            for source_key in value.source_keys:
                if source_key not in columns:
                    columns.append(source_key)
        return tuple(columns)

    @property
    def units(self) -> str:
        units = [value.unit for value in self.values if value.unit]
        return " / ".join(units)

    @property
    def narrative_parts_data(self) -> tuple[dict[str, object], ...]:
        return tuple(
            {
                "template": part.template,
                "required_keys": part.required_keys,
            }
            for part in self.narrative_parts
        )


@dataclass(frozen=True, slots=True)
class ReportSectionSpec:
    key: str
    title: str
    order: int
    elements: tuple[ReportElementSpec, ...]


@dataclass(slots=True)
class ReportValueView:
    key: str
    label: str
    source_keys: tuple[str, ...]
    unit: str
    input_type: str
    rows: int
    transform: str
    presentation_width: str
    width_ch: int
    value: str
    initial_value: str
    source_state: str
    status_key: str
    status_label: str
    status_badge: str


@dataclass(slots=True)
class ReportElementView:
    spec: ReportElementSpec
    values: tuple[ReportValueView, ...]
    status_key: str
    status_label: str
    narrative_text: str
    narrative_paragraphs: tuple[str, ...]
    completed: bool
    filled_count: int
    total_count: int
    status_badge: str


@dataclass(slots=True)
class ReportSectionView:
    spec: ReportSectionSpec
    elements: tuple[ReportElementView, ...]
    completed_count: int
    total_count: int
    narrative_paragraphs: tuple[str, ...]


@dataclass(slots=True)
class StudyDraftView:
    lookup_patient_id_num: str
    lookup_visit_datetime: str
    lookup_patient_full_name: str
    lookup_patient_age: str
    lookup_patient_sex: str
    sections: tuple[ReportSectionView, ...]
    global_completed_count: int
    global_total_count: int


def v(
    key: str,
    label: str,
    *,
    source_keys: tuple[str, ...] | None = None,
    unit: str = "",
    input_type: str = "text",
    rows: int = 1,
    transform: str = "",
    presentation_width: str = "auto",
) -> ReportValueSpec:
    return ReportValueSpec(
        key=key,
        label=label,
        source_keys=(key,) if source_keys is None else source_keys,
        unit=unit,
        input_type=input_type,
        rows=rows,
        transform=transform,
        presentation_width=presentation_width,
    )


def p(template: str, *required_keys: str) -> NarrativePartSpec:
    return NarrativePartSpec(template=template, required_keys=tuple(required_keys))


def e(
    section_key: str,
    section_title: str,
    section_order: int,
    key: str,
    order: int,
    title: str,
    origin: str,
    values: tuple[ReportValueSpec, ...],
    narrative_style: str,
    narrative_template: str,
    narrative_parts: tuple[NarrativePartSpec, ...],
    *,
    presentation_layout: str = "single",
    narrative_always_visible: bool = False,
    narrative_empty_heading_only: bool = False,
) -> ReportElementSpec:
    return ReportElementSpec(
        key=key,
        order=order,
        title=title,
        origin=origin,
        values=values,
        narrative_style=narrative_style,
        narrative_template=narrative_template,
        narrative_parts=narrative_parts,
        section_key=section_key,
        section_title=section_title,
        section_order=section_order,
        presentation_layout=presentation_layout,
        narrative_always_visible=narrative_always_visible,
        narrative_empty_heading_only=narrative_empty_heading_only,
    )


def s(key: str, title: str, order: int, *elements: ReportElementSpec) -> ReportSectionSpec:
    return ReportSectionSpec(key=key, title=title, order=order, elements=tuple(elements))


REPORT_SECTION_SPECS = (
    s(
        "identificacion",
        "Antecedentes clínicos y remisión",
        1,
        e(
            "identificacion",
            "Identificación",
            1,
            "identity_visit",
            12,
            "Fecha y hora del estudio",
            CALCULADO,
            (v("visit_datetime", "Fecha y hora", presentation_width="medium"),),
            "sentences",
            "Fecha y hora del estudio: {visit_datetime}.",
            (p("Fecha y hora del estudio: {visit_datetime}.", "visit_datetime"),),
        ),
        e(
            "identificacion",
            "Identificación",
            1,
            "identity_name",
            13,
            "Nombre del paciente",
            CALCULADO,
            (
                v("patient_first_name", "Nombre", presentation_width="flex"),
                v("patient_middle_name", "Segundo nombre", presentation_width="flex"),
                v("patient_last_name", "Apellido", presentation_width="flex"),
            ),
            "sentences",
            "Paciente {patient_full_name}.",
            (p("Paciente {patient_full_name}.", "patient_first_name", "patient_middle_name", "patient_last_name"),),
            presentation_layout="grouped",
        ),
        e(
            "identificacion",
            "Identificación",
            1,
            "identity_id",
            14,
            "Identificación del paciente",
            DIRECTO,
            (v("patient_id_num", "ID", presentation_width="medium"),),
            "sentences",
            "ID {patient_id_num}.",
            (p("ID {patient_id_num}.", "patient_id_num"),),
        ),
        e(
            "identificacion",
            "Identificación",
            1,
            "identity_age",
            15,
            "Edad",
            DIRECTO,
            (v("age", "Edad", unit="años", presentation_width="compact"),),
            "sentences",
            "Edad {age} años.",
            (p("Edad {age} años.", "age"),),
        ),
        e(
            "identificacion",
            "Identificación",
            1,
            "identity_sex",
            16,
            "Sexo",
            DIRECTO,
            (v("sex", "Sexo", presentation_width="medium"),),
            "sentences",
            "Sexo {sex}.",
            (p("Sexo {sex}.", "sex"),),
        ),
        e(
            "identificacion",
            "Identificación",
            1,
            "diagnosis",
            3,
            "Diagnóstico",
            DIRECTO,
            (v("diagnosis", "Diagnóstico", presentation_width="long"),),
            "sentences",
            "Diagnóstico: {diagnosis}.",
            (p("Diagnóstico: {diagnosis}.", "diagnosis"),),
        ),
        e(
            "identificacion",
            "Identificación",
            1,
            "dyspnea",
            4,
            "Disnea",
            DIRECTO,
            (v("dyspnea", "Disnea", presentation_width="long"),),
            "sentences",
            "Disnea: {dyspnea}.",
            (p("Disnea: {dyspnea}.", "dyspnea"),),
        ),
        e(
            "identificacion",
            "Identificación",
            1,
            "cough",
            5,
            "Tos",
            DIRECTO,
            (v("cough", "Tos", presentation_width="long"),),
            "sentences",
            "Tos: {cough}.",
            (p("Tos: {cough}.", "cough"),),
        ),
        e(
            "identificacion",
            "Identificación",
            1,
            "wheez",
            6,
            "Sibilancias",
            DIRECTO,
            (v("wheez", "Sibilancias", presentation_width="long"),),
            "sentences",
            "Sibilancias: {wheez}.",
            (p("Sibilancias: {wheez}.", "wheez"),),
        ),
        e(
            "identificacion",
            "Identificación",
            1,
            "tbco_prod",
            7,
            "Tabaquismo",
            DIRECTO,
            (v("tbco_prod", "Tabaquismo", presentation_width="medium"),),
            "sentences",
            "Tabaquismo: {tbco_prod}.",
            (p("Tabaquismo: {tbco_prod}.", "tbco_prod"),),
        ),
        e(
            "identificacion",
            "Identificación",
            1,
            "pk_yrs",
            8,
            "Índice paquetes-año",
            DIRECTO,
            (v("pk_yrs", "Índice paquetes-año", presentation_width="medium"),),
            "sentences",
            "Índice paquetes-año: {pk_yrs}.",
            (p("Índice paquetes-año: {pk_yrs}.", "pk_yrs"),),
        ),
        e(
            "identificacion",
            "Identificación",
            1,
            "remision_motivo",
            1,
            "Motivo de la remisión",
            MANUAL,
            (
                v(
                    "remision_motivo",
                    "Motivo de la remisión",
                    source_keys=(),
                    input_type="textarea",
                    rows=2,
                    presentation_width="full",
                ),
            ),
            "sentences",
            "Motivo de la remisión: {remision_motivo}.",
            (p("Motivo de la remisión: {remision_motivo}.", "remision_motivo"),),
        ),
        e(
            "identificacion",
            "Identificación",
            1,
            "remision_medico",
            2,
            "Médico remitente",
            MANUAL,
            (v("remision_medico", "Médico remitente", source_keys=(), presentation_width="long"),),
            "sentences",
            "Médico remitente: {remision_medico}.",
            (p("Médico remitente: {remision_medico}.", "remision_medico"),),
        ),
        e(
            "identificacion",
            "Identificación",
            1,
            "biomasa_exposure",
            9,
            "Exposición a biomasa",
            MANUAL,
            (v("biomasa_exposure", "Exposición a biomasa", source_keys=(), presentation_width="long"),),
            "sentences",
            "Exposición a biomasa: {biomasa_exposure}.",
            (p("Exposición a biomasa: {biomasa_exposure}.", "biomasa_exposure"),),
        ),
        e(
            "identificacion",
            "Identificación",
            1,
            "oxygenoterapia",
            10,
            "Oxigenoterapia",
            MANUAL,
            (v("oxygenoterapia", "Oxigenoterapia", source_keys=(), presentation_width="long"),),
            "sentences",
            "Oxigenoterapia: {oxygenoterapia}.",
            (p("Oxigenoterapia: {oxygenoterapia}.", "oxygenoterapia"),),
        ),
        e(
            "identificacion",
            "Identificación",
            1,
            "medications",
            11,
            "Medicamentos",
            MANUAL,
            (
                v(
                    "medications",
                    "Medicamentos",
                    source_keys=(),
                    input_type="textarea",
                    rows=5,
                    presentation_width="long",
                ),
            ),
            "sentences",
            "Medicamentos: {medications}.",
            (p("Medicamentos: {medications}.", "medications"),),
        ),
    ),
    s(
        "antecedentes",
        "Antecedentes",
        2,
        e(
            "antecedentes",
            "Antecedentes",
            2,
            "anthropometric",
            1,
            "Medidas antropométricas",
            CALCULADO,
            (
                v("weight", "Peso", unit="kg", presentation_width="numeric"),
                v("height", "Estatura", unit="cm", transform="height_cm", presentation_width="numeric"),
                v("bmi", "IMC", unit="kg/m²", presentation_width="numeric"),
            ),
            "prefix_clauses",
            "Medidas antropométricas: peso {weight} kg, estatura {height_cm} cm e IMC {bmi} kg/m².",
            (
                p("peso {weight} kg", "weight"),
                p("estatura {height_cm} cm", "height"),
                p("e IMC {bmi} kg/m²", "bmi"),
            ),
            presentation_layout="grouped",
        ),
        e(
            "antecedentes",
            "Antecedentes",
            2,
            "hemoglobin",
            2,
            "Hemoglobina",
            MANUAL,
            (v("hemoglobin", "Hemoglobina", source_keys=(), unit="g/dL", presentation_width="numeric"),),
            "sentences",
            "Hemoglobina: {hemoglobin} g/dL.",
            (p("Hemoglobina: {hemoglobin} g/dL.", "hemoglobin"),),
        ),
        e(
            "antecedentes",
            "Antecedentes",
            2,
            "hematocrit",
            3,
            "Hematocrito",
            MANUAL,
            (v("hematocrit", "Hematocrito", source_keys=(), unit="%", presentation_width="numeric"),),
            "sentences",
            "Hematocrito: {hematocrit} %.",
            (p("Hematocrito: {hematocrit} %.", "hematocrit"),),
        ),
    ),
    s(
        "protocolo",
        "Protocolo",
        3,
        e(
            "protocolo",
            "Protocolo",
            3,
            "protocol_intro",
            1,
            "Protocolo",
            CALCULADO,
            (
                v("gx_vo2_max_time_min", "Duración", unit="min", presentation_width="compact"),
                v("gx_vo2_max_work_watts", "Carga máxima", unit="W", presentation_width="numeric"),
                v("gx_vo2_max_rer", "RER", presentation_width="numeric"),
            ),
            "prefix_clauses",
            "Protocolo: duración {gx_vo2_max_time_min} min, carga máxima {gx_vo2_max_work_watts} W y RER {gx_vo2_max_rer}.",
            (
                p("Protocolo: duración {gx_vo2_max_time_min} min", "gx_vo2_max_time_min"),
                p("carga máxima {gx_vo2_max_work_watts} W", "gx_vo2_max_work_watts"),
                p("RER {gx_vo2_max_rer}", "gx_vo2_max_rer"),
            ),
            presentation_layout="grouped",
        ),
        e(
            "protocolo",
            "Protocolo",
            3,
            "protocol_stages",
            2,
            "Etapas",
            MANUAL,
            (v("protocol_stages", "Etapas", source_keys=(), presentation_width="long"),),
            "sentences",
            "Etapas: {protocol_stages}.",
            (p("Etapas: {protocol_stages}.", "protocol_stages"),),
        ),
        e(
            "protocolo",
            "Protocolo",
            3,
            "protocol_borg_disnea",
            3,
            "Borg disnea",
            MANUAL,
            (v("protocol_borg_disnea", "Borg disnea", source_keys=(), presentation_width="compact"),),
            "sentences",
            "Borg disnea: {protocol_borg_disnea}.",
            (p("Borg disnea: {protocol_borg_disnea}.", "protocol_borg_disnea"),),
        ),
        e(
            "protocolo",
            "Protocolo",
            3,
            "protocol_borg_fatiga",
            4,
            "Borg fatiga",
            MANUAL,
            (v("protocol_borg_fatiga", "Borg fatiga", source_keys=(), presentation_width="compact"),),
            "sentences",
            "Borg fatiga: {protocol_borg_fatiga}.",
            (p("Borg fatiga: {protocol_borg_fatiga}.", "protocol_borg_fatiga"),),
        ),
    ),
    s(
        "capacidad_funcional",
        "Capacidad funcional",
        5,
        e(
            "capacidad_funcional",
            "Capacidad funcional",
            5,
            "functional_rest",
            1,
            "VO₂ en reposo",
            CALCULADO,
            (
                v("gx_rest_vo2_ml_per_min", "VO₂ absoluto", unit="ml/min", presentation_width="numeric"),
                v("gx_rest_vo2_ml_per_kg_per_min", "VO₂ relativo", unit="ml/kg/min", presentation_width="numeric"),
            ),
            "dual_variant",
            "VO₂ en reposo {gx_rest_vo2_ml_per_min} ml/min ({gx_rest_vo2_ml_per_kg_per_min} ml/kg/min).",
            (
                p("VO₂ en reposo {gx_rest_vo2_ml_per_min} ml/min ({gx_rest_vo2_ml_per_kg_per_min} ml/kg/min)", "gx_rest_vo2_ml_per_min", "gx_rest_vo2_ml_per_kg_per_min"),
                p("VO₂ en reposo {gx_rest_vo2_ml_per_min} ml/min", "gx_rest_vo2_ml_per_min"),
                p("VO₂ en reposo {gx_rest_vo2_ml_per_kg_per_min} ml/kg/min", "gx_rest_vo2_ml_per_kg_per_min"),
            ),
            presentation_layout="grouped",
        ),
        e(
            "capacidad_funcional",
            "Capacidad funcional",
            5,
            "functional_peak",
            2,
            "VO₂ pico",
            CALCULADO,
            (
                v("gx_vo2_max_vo2_ml_per_min", "VO₂ absoluto", unit="ml/min", presentation_width="numeric"),
                v("gx_vo2_max_vo2_ml_per_kg_per_min", "VO₂ relativo", unit="ml/kg/min", presentation_width="numeric"),
            ),
            "prefix_clauses",
            "VO₂ pico absoluto {gx_vo2_max_vo2_ml_per_min} ml/min y relativo {gx_vo2_max_vo2_ml_per_kg_per_min} ml/kg/min.",
            (
                p("absoluto {gx_vo2_max_vo2_ml_per_min} ml/min", "gx_vo2_max_vo2_ml_per_min"),
                p("relativo {gx_vo2_max_vo2_ml_per_kg_per_min} ml/kg/min", "gx_vo2_max_vo2_ml_per_kg_per_min"),
            ),
            presentation_layout="grouped",
        ),
        e(
            "capacidad_funcional",
            "Capacidad funcional",
            5,
            "functional_load",
            3,
            "Carga y pendiente",
            CALCULADO,
            (
                v("gx_vo2_max_work_watts", "Carga pico", unit="W", presentation_width="numeric"),
                v("gx_vo2_max_vo2workslope_ml_per_min_per_watt", "Pendiente VO₂/carga", unit="ml/min/W", presentation_width="numeric"),
            ),
            "prefix_clauses",
            "Carga pico {gx_vo2_max_work_watts} W y pendiente VO₂/carga {gx_vo2_max_vo2workslope_ml_per_min_per_watt} ml/min/W.",
            (
                p("Carga pico {gx_vo2_max_work_watts} W", "gx_vo2_max_work_watts"),
                p("pendiente VO₂/carga {gx_vo2_max_vo2workslope_ml_per_min_per_watt} ml/min/W", "gx_vo2_max_vo2workslope_ml_per_min_per_watt"),
            ),
            presentation_layout="grouped",
        ),
        e(
            "capacidad_funcional",
            "Capacidad funcional",
            5,
            "functional_predicted",
            4,
            "Predichos",
            CALCULADO,
            (
                v("gx_predicted_vo2_ml_per_min", "VO₂", unit="ml/min", presentation_width="numeric"),
                v("gx_predicted_vo2_ml_per_kg_per_min", "VO₂ relativo", unit="ml/kg/min", presentation_width="numeric"),
                v("gx_predicted_work_watts", "Carga", unit="W", presentation_width="numeric"),
                v("gx_predicted_vo2workslope_ml_per_min_per_watt", "Pendiente", unit="ml/min/W", presentation_width="numeric"),
            ),
            "prefix_clauses",
            "Predichos: VO₂ {gx_predicted_vo2_ml_per_min} ml/min; {gx_predicted_vo2_ml_per_kg_per_min} ml/kg/min; carga {gx_predicted_work_watts} W; pendiente {gx_predicted_vo2workslope_ml_per_min_per_watt} ml/min/W.",
            (
                p("VO₂ {gx_predicted_vo2_ml_per_min} ml/min", "gx_predicted_vo2_ml_per_min"),
                p("{gx_predicted_vo2_ml_per_kg_per_min} ml/kg/min", "gx_predicted_vo2_ml_per_kg_per_min"),
                p("carga {gx_predicted_work_watts} W", "gx_predicted_work_watts"),
                p("pendiente {gx_predicted_vo2workslope_ml_per_min_per_watt} ml/min/W", "gx_predicted_vo2workslope_ml_per_min_per_watt"),
            ),
            presentation_layout="grouped",
        ),
    ),
    s(
        "respuesta_cardiovascular",
        "Respuesta cardiovascular",
        4,
        e(
            "respuesta_cardiovascular",
            "Respuesta cardiovascular",
            4,
            "cardio_rhythm",
            1,
            "",
            MANUAL,
            (
                v("cardio_rhythm", "Ritmo", source_keys=(), presentation_width="long"),
                v("gx_rest_hr_bpm", "FC inicial", unit="lpm", presentation_width="compact"),
                v("gx_vo2_max_hr_bpm", "FC final", unit="lpm", presentation_width="compact"),
            ),
            "prefix_clauses",
            "Ritmo {cardio_rhythm}; FC inicial {gx_rest_hr_bpm} lpm y final {gx_vo2_max_hr_bpm} lpm.",
            (
                p("Ritmo {cardio_rhythm}", "cardio_rhythm"),
                p("FC inicial {gx_rest_hr_bpm} lpm", "gx_rest_hr_bpm"),
                p("FC final {gx_vo2_max_hr_bpm} lpm", "gx_vo2_max_hr_bpm"),
            ),
            presentation_layout="grouped",
        ),
        e(
            "respuesta_cardiovascular",
            "Respuesta cardiovascular",
            4,
            "cardio_bp",
            2,
            "Presión arterial",
            CALCULADO,
            (
                v("gx_rest_sysbp_mmhg", "Sistólica en reposo", unit="mmHg", presentation_width="numeric"),
                v("gx_rest_diabp_mmhg", "Diastólica en reposo", unit="mmHg", presentation_width="numeric"),
                v("gx_vo2_max_sysbp_mmhg", "Sistólica máxima", unit="mmHg", presentation_width="numeric"),
                v("gx_vo2_max_diabp_mmhg", "Diastólica máxima", unit="mmHg", presentation_width="numeric"),
            ),
            "prefix_clauses",
            "Presión arterial en reposo {gx_rest_sysbp_mmhg}/{gx_rest_diabp_mmhg} mmHg y máxima {gx_vo2_max_sysbp_mmhg}/{gx_vo2_max_diabp_mmhg} mmHg.",
            (
                p("en reposo {gx_rest_sysbp_mmhg}/{gx_rest_diabp_mmhg} mmHg", "gx_rest_sysbp_mmhg", "gx_rest_diabp_mmhg"),
                p("máxima {gx_vo2_max_sysbp_mmhg}/{gx_vo2_max_diabp_mmhg} mmHg", "gx_vo2_max_sysbp_mmhg", "gx_vo2_max_diabp_mmhg"),
            ),
            presentation_layout="grouped",
        ),
        e(
            "respuesta_cardiovascular",
            "Respuesta cardiovascular",
            4,
            "cardio_pox",
            3,
            "Pulso de oxígeno",
            CALCULADO,
            (
                v("gx_rest_vo2_per_hr_ml_per_beat", "Pulso en reposo", unit="ml/latido", presentation_width="numeric"),
                v("gx_vo2_max_vo2_per_hr_ml_per_beat", "Pulso máximo", unit="ml/latido", presentation_width="numeric"),
                v("gx_predicted_vo2_per_hr_ml_per_beat", "Pulso predicho", unit="ml/latido", presentation_width="numeric"),
            ),
            "prefix_clauses",
            "Pulso de oxígeno en reposo {gx_rest_vo2_per_hr_ml_per_beat} ml/latido; máximo {gx_vo2_max_vo2_per_hr_ml_per_beat} ml/latido; predicho {gx_predicted_vo2_per_hr_ml_per_beat} ml/latido.",
            (
                p("en reposo {gx_rest_vo2_per_hr_ml_per_beat} ml/latido", "gx_rest_vo2_per_hr_ml_per_beat"),
                p("máximo {gx_vo2_max_vo2_per_hr_ml_per_beat} ml/latido", "gx_vo2_max_vo2_per_hr_ml_per_beat"),
                p("predicho {gx_predicted_vo2_per_hr_ml_per_beat} ml/latido", "gx_predicted_vo2_per_hr_ml_per_beat"),
            ),
            presentation_layout="grouped",
        ),
        e(
            "respuesta_cardiovascular",
            "Respuesta cardiovascular",
            4,
            "cardio_recovery",
            4,
            "Recuperación",
            MANUAL,
            (v("cardio_recovery", "Recuperación", source_keys=(), presentation_width="long"),),
            "sentences",
            "Recuperación: {cardio_recovery}.",
            (p("Recuperación: {cardio_recovery}.", "cardio_recovery"),),
        ),
        e(
            "respuesta_cardiovascular",
            "Respuesta cardiovascular",
            4,
            "cardio_ecg",
            5,
            "ECG",
            INTERPRETACION,
            (v("cardio_ecg", "ECG", source_keys=(), presentation_width="long"),),
            "sentences",
            "ECG: {cardio_ecg}.",
            (p("ECG: {cardio_ecg}.", "cardio_ecg"),),
        ),
        e(
            "respuesta_cardiovascular",
            "Respuesta cardiovascular",
            4,
            "cardio_valuation",
            6,
            "Valoración clínica",
            INTERPRETACION,
            (v("cardio_valuation", "Valoración clínica", source_keys=(), presentation_width="long"),),
            "sentences",
            "Valoración clínica: {cardio_valuation}.",
            (p("Valoración clínica: {cardio_valuation}.", "cardio_valuation"),),
        ),
    ),
    s(
        "respuesta_ventilatoria",
        "Respuesta ventilatoria",
        7,
        e(
            "respuesta_ventilatoria",
            "Respuesta ventilatoria",
            7,
            "vent_vvm",
            1,
            "VVM",
            CALCULADO,
            (v("pf_pre_mvv_l_per_min", "VVM", unit="L/min", presentation_width="numeric"),),
            "sentences",
            "VVM pretest {pf_pre_mvv_l_per_min} L/min.",
            (p("VVM pretest {pf_pre_mvv_l_per_min} L/min.", "pf_pre_mvv_l_per_min"),),
        ),
        e(
            "respuesta_ventilatoria",
            "Respuesta ventilatoria",
            7,
            "vent_ve",
            2,
            "Ventilación minuto",
            CALCULADO,
            (
                v("gx_rest_ve_btps_l_per_min", "VE en reposo", unit="BTPS L/min", presentation_width="numeric"),
                v("gx_vo2_max_ve_btps_l_per_min", "VE máxima", unit="BTPS L/min", presentation_width="numeric"),
            ),
            "prefix_clauses",
            "VE en reposo {gx_rest_ve_btps_l_per_min} BTPS L/min y máxima {gx_vo2_max_ve_btps_l_per_min} BTPS L/min.",
            (
                p("en reposo {gx_rest_ve_btps_l_per_min} BTPS L/min", "gx_rest_ve_btps_l_per_min"),
                p("máxima {gx_vo2_max_ve_btps_l_per_min} BTPS L/min", "gx_vo2_max_ve_btps_l_per_min"),
            ),
            presentation_layout="grouped",
        ),
        e(
            "respuesta_ventilatoria",
            "Respuesta ventilatoria",
            7,
            "vent_ve_mvv",
            3,
            "VE/MVV",
            CALCULADO,
            (v("gx_vo2_max_ve_per_mvv_pct", "VE/MVV", unit="%", presentation_width="compact"),),
            "sentences",
            "VE/MVV máxima {gx_vo2_max_ve_per_mvv_pct} %.",
            (p("VE/MVV máxima {gx_vo2_max_ve_per_mvv_pct} %.", "gx_vo2_max_ve_per_mvv_pct"),),
        ),
        e(
            "respuesta_ventilatoria",
            "Respuesta ventilatoria",
            7,
            "vent_vt_ci",
            4,
            "VT/CI",
            CALCULADO,
            (v("gx_vo2_max_vt_per_ic_pct", "VT/CI", unit="%", presentation_width="compact"),),
            "sentences",
            "VT/CI máxima {gx_vo2_max_vt_per_ic_pct} %.",
            (p("VT/CI máxima {gx_vo2_max_vt_per_ic_pct} %.", "gx_vo2_max_vt_per_ic_pct"),),
        ),
        e(
            "respuesta_ventilatoria",
            "Respuesta ventilatoria",
            7,
            "vent_rr",
            5,
            "Frecuencia respiratoria",
            CALCULADO,
            (
                v("gx_rest_rr_br_per_min", "Frecuencia en reposo", unit="br/min", presentation_width="compact"),
                v("gx_vo2_max_rr_br_per_min", "Frecuencia máxima", unit="br/min", presentation_width="compact"),
            ),
            "prefix_clauses",
            "Frecuencia respiratoria en reposo {gx_rest_rr_br_per_min} br/min y máxima {gx_vo2_max_rr_br_per_min} br/min.",
            (
                p("en reposo {gx_rest_rr_br_per_min} br/min", "gx_rest_rr_br_per_min"),
                p("máxima {gx_vo2_max_rr_br_per_min} br/min", "gx_vo2_max_rr_br_per_min"),
            ),
            presentation_layout="grouped",
        ),
        e(
            "respuesta_ventilatoria",
            "Respuesta ventilatoria",
            7,
            "vent_spo2",
            6,
            "SpO₂",
            CALCULADO,
            (
                v("gx_rest_spo2_pct", "SpO₂ en reposo", unit="%", presentation_width="compact"),
                v("gx_vo2_max_spo2_pct", "SpO₂ máxima", unit="%", presentation_width="compact"),
            ),
            "prefix_clauses",
            "SpO₂ en reposo {gx_rest_spo2_pct} % y máxima {gx_vo2_max_spo2_pct} %.",
            (
                p("en reposo {gx_rest_spo2_pct} %", "gx_rest_spo2_pct"),
                p("máxima {gx_vo2_max_spo2_pct} %", "gx_vo2_max_spo2_pct"),
            ),
            presentation_layout="grouped",
        ),
    ),
    s(
        "intercambio_gaseoso",
        "Intercambio gaseoso",
        8,
        e(
            "intercambio_gaseoso",
            "Intercambio gaseoso",
            8,
            "gas_vdvt",
            1,
            "VD/VT",
            CALCULADO,
            (
                v("gx_rest_vd_per_vt_meas", "VD/VT en reposo", presentation_width="compact"),
                v("gx_vo2_max_vd_per_vt_meas", "VD/VT máxima", presentation_width="compact"),
            ),
            "prefix_clauses",
            "VD/VT en reposo {gx_rest_vd_per_vt_meas} y máxima {gx_vo2_max_vd_per_vt_meas}.",
            (
                p("en reposo {gx_rest_vd_per_vt_meas}", "gx_rest_vd_per_vt_meas"),
                p("máxima {gx_vo2_max_vd_per_vt_meas}", "gx_vo2_max_vd_per_vt_meas"),
            ),
            presentation_layout="grouped",
        ),
        e(
            "intercambio_gaseoso",
            "Intercambio gaseoso",
            8,
            "gas_petco2",
            2,
            "PETCO₂",
            CALCULADO,
            (
                v("gx_rest_petco2_mmhg", "PETCO₂ en reposo", unit="mmHg", presentation_width="compact"),
                v("gx_vo2_max_petco2_mmhg", "PETCO₂ máxima", unit="mmHg", presentation_width="compact"),
            ),
            "prefix_clauses",
            "PETCO₂ en reposo {gx_rest_petco2_mmhg} mmHg y máxima {gx_vo2_max_petco2_mmhg} mmHg.",
            (
                p("en reposo {gx_rest_petco2_mmhg} mmHg", "gx_rest_petco2_mmhg"),
                p("máxima {gx_vo2_max_petco2_mmhg} mmHg", "gx_vo2_max_petco2_mmhg"),
            ),
            presentation_layout="grouped",
        ),
        e(
            "intercambio_gaseoso",
            "Intercambio gaseoso",
            8,
            "arterial_gases",
            3,
            "Gases arteriales",
            MANUAL,
            (v("arterial_gases", "Gases arteriales", source_keys=(), presentation_width="long"),),
            "sentences",
            "Gases arteriales: {arterial_gases}.",
            (p("Gases arteriales: {arterial_gases}.", "arterial_gases"),),
        ),
        e(
            "intercambio_gaseoso",
            "Intercambio gaseoso",
            8,
            "anaerobic_threshold",
            4,
            "Valoración clínica del umbral anaeróbico",
            INTERPRETACION,
            (v("anaerobic_threshold", "Valoración clínica del umbral anaeróbico", source_keys=(), presentation_width="long"),),
            "sentences",
            "Valoración clínica del umbral anaeróbico: {anaerobic_threshold}.",
            (p("Valoración clínica del umbral anaeróbico: {anaerobic_threshold}.", "anaerobic_threshold"),),
        ),
    ),
    s(
        "conclusiones",
        "Conclusiones",
        9,
        e(
            "conclusiones",
            "Conclusiones",
            9,
            "conclusions",
            1,
            "Conclusiones",
            MANUAL,
            (v("conclusions", "Conclusiones", source_keys=(), input_type="textarea", rows=5, presentation_width="full"),),
            "free_text",
            "",
            (),
            presentation_layout="full",
            narrative_always_visible=True,
            narrative_empty_heading_only=True,
        ),
    ),
)


def _join_phrases(parts: Iterable[str]) -> str:
    items = [part for part in parts if _has_text(part)]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} y {items[1]}"
    return f"{', '.join(items[:-1])} y {items[-1]}"


def _compose_sentence(prefix: str, parts: Iterable[str]) -> str:
    body = _join_phrases(parts)
    if not body:
        return ""
    text = f"{prefix} {body}".strip()
    return _sentence(text)


def _paragraph(*sentences: str) -> str:
    return " ".join(sentence for sentence in sentences if _has_text(sentence))


def _identification_paragraph(context: Mapping[str, str]) -> str:
    paragraphs: list[str] = []
    referral = _referral_paragraph(context)
    if referral:
        paragraphs.append(referral)
    clinical = _clinical_paragraph(context)
    if clinical:
        paragraphs.append(clinical)
    habits = _habits_paragraph(context)
    if habits:
        paragraphs.append(habits)
    return _paragraph(*paragraphs)


def _clinical_paragraph(context: Mapping[str, str]) -> str:
    clauses = []
    diagnosis = _clean_text(context.get("diagnosis"))
    dyspnea = _clean_text(context.get("dyspnea"))
    cough = _clean_text(context.get("cough"))
    wheez = _clean_text(context.get("wheez"))
    if diagnosis:
        clauses.append(f"diagnóstico {diagnosis}")
    if dyspnea:
        clauses.append(f"disnea {dyspnea}")
    if cough:
        clauses.append(f"tos {cough}")
    if wheez:
        clauses.append(f"sibilancias {wheez}")
    return _compose_sentence("Refiere", clauses)


def _habits_paragraph(context: Mapping[str, str]) -> str:
    clauses = []
    tbco_prod = _clean_text(context.get("tbco_prod"))
    pk_yrs = _clean_text(context.get("pk_yrs"))
    if tbco_prod:
        clauses.append(f"tabaquismo {tbco_prod}")
    if pk_yrs:
        clauses.append(f"índice paquetes-año {pk_yrs}")
    return _compose_sentence("", clauses)


def _referral_paragraph(context: Mapping[str, str]) -> str:
    clauses = []
    remision_motivo = _clean_text(context.get("remision_motivo"))
    remision_medico = _clean_text(context.get("remision_medico"))
    biomasa_exposure = _clean_text(context.get("biomasa_exposure"))
    oxygenoterapia = _clean_text(context.get("oxygenoterapia"))
    medications = _clean_text(context.get("medications"))
    if remision_motivo:
        clauses.append(f"Motivo de la remisión: {remision_motivo}")
    if remision_medico:
        clauses.append(f"Médico remitente: {remision_medico}")
    if biomasa_exposure:
        clauses.append(f"Exposición a biomasa: {biomasa_exposure}")
    if oxygenoterapia:
        clauses.append(f"Oxigenoterapia: {oxygenoterapia}")
    if medications:
        clauses.append(f"Medicamentos: {medications}")
    return _compose_sentence("", clauses)


def _anthropometry_paragraph(context: Mapping[str, str]) -> str:
    clauses = []
    weight = _clean_text(context.get("weight"))
    height = _clean_text(context.get("height_cm"))
    bmi = _clean_text(context.get("bmi"))
    if weight:
        clauses.append(f"Peso {weight} kg")
    if height:
        clauses.append(f"estatura {height} cm")
    if bmi:
        clauses.append(f"IMC {bmi} kg/m²")
    return _compose_sentence("", clauses)


def _hematology_paragraph(context: Mapping[str, str]) -> str:
    clauses = []
    hemoglobin = _clean_text(context.get("hemoglobin"))
    hematocrit = _clean_text(context.get("hematocrit"))
    if hemoglobin:
        clauses.append(f"Hemoglobina {hemoglobin} g/dL")
    if hematocrit:
        clauses.append(f"hematocrito {hematocrit} %")
    return _compose_sentence("", clauses)


def _protocol_paragraph(context: Mapping[str, str]) -> str:
    clauses = []
    duration = _clean_text(context.get("gx_vo2_max_time_min"))
    load = _clean_text(context.get("gx_vo2_max_work_watts"))
    rer = _clean_text(context.get("gx_vo2_max_rer"))
    if duration:
        clauses.append(f"tuvo una duración de {duration} minutos")
    if load:
        clauses.append(f"alcanzó una carga máxima de {load} W")
    if rer:
        clauses.append(f"registró un RER de {rer}")
    return _compose_sentence("La prueba", clauses)


def _protocol_support_paragraph(context: Mapping[str, str]) -> str:
    clauses = []
    stages = _clean_text(context.get("protocol_stages"))
    borg_disnea = _clean_text(context.get("protocol_borg_disnea"))
    borg_fatiga = _clean_text(context.get("protocol_borg_fatiga"))
    if stages:
        clauses.append(f"Etapas: {stages}")
    if borg_disnea:
        clauses.append(f"Borg disnea: {borg_disnea}")
    if borg_fatiga:
        clauses.append(f"borg de fatiga {borg_fatiga}")
    if borg_disnea:
        clauses.insert(1 if stages else 0, f"borg de disnea {borg_disnea}")
    return _compose_sentence("Se registraron", clauses)


def _functional_paragraph(context: Mapping[str, str]) -> str:
    clauses = []
    rest_abs = _clean_text(context.get("gx_rest_vo2_ml_per_min"))
    rest_rel = _clean_text(context.get("gx_rest_vo2_ml_per_kg_per_min"))
    peak_abs = _clean_text(context.get("gx_vo2_max_vo2_ml_per_min"))
    peak_rel = _clean_text(context.get("gx_vo2_max_vo2_ml_per_kg_per_min"))
    load = _clean_text(context.get("gx_vo2_max_work_watts"))
    slope = _clean_text(context.get("gx_vo2_max_vo2workslope_ml_per_min_per_watt"))
    pred_abs = _clean_text(context.get("gx_predicted_vo2_ml_per_min"))
    pred_rel = _clean_text(context.get("gx_predicted_vo2_ml_per_kg_per_min"))
    pred_load = _clean_text(context.get("gx_predicted_work_watts"))
    pred_slope = _clean_text(context.get("gx_predicted_vo2workslope_ml_per_min_per_watt"))

    if rest_abs:
        phrase = f"VO₂ en reposo {rest_abs} ml/min"
        if rest_rel:
            phrase += f" ({rest_rel} ml/kg/min)"
        clauses.append(phrase)
    elif rest_rel:
        clauses.append(f"VO₂ en reposo {rest_rel} ml/kg/min")

    if peak_abs:
        phrase = f"VO₂ pico {peak_abs} ml/min"
        if peak_rel:
            phrase += f" ({peak_rel} ml/kg/min)"
        clauses.append(phrase)
    elif peak_rel:
        clauses.append(f"VO₂ pico {peak_rel} ml/kg/min")

    if load:
        phrase = f"Carga pico {load} W"
        if slope:
            phrase += f" y pendiente VO₂/carga {slope} ml/min/W"
        clauses.append(phrase)
    elif slope:
        clauses.append(f"Pendiente VO₂/carga {slope} ml/min/W")

    if pred_abs or pred_rel or pred_load or pred_slope:
        predicted = []
        if pred_abs:
            predicted.append(f"VO₂ {pred_abs} ml/min")
        if pred_rel:
            predicted.append(f"{pred_rel} ml/kg/min")
        if pred_load:
            predicted.append(f"carga {pred_load} W")
        if pred_slope:
            predicted.append(f"pendiente {pred_slope} ml/min/W")
        clauses.append(f"Predichos: {_join_phrases(predicted)}")

    return _compose_sentence("", clauses)


def _cardio_paragraph(context: Mapping[str, str]) -> tuple[str, ...]:
    paragraphs: list[str] = []
    rest_hr = _clean_text(context.get("gx_rest_hr_bpm"))
    peak_hr = _clean_text(context.get("gx_vo2_max_hr_bpm"))
    rest_sys = _clean_text(context.get("gx_rest_sysbp_mmhg"))
    rest_dia = _clean_text(context.get("gx_rest_diabp_mmhg"))
    peak_sys = _clean_text(context.get("gx_vo2_max_sysbp_mmhg"))
    peak_dia = _clean_text(context.get("gx_vo2_max_diabp_mmhg"))
    rest_pox = _clean_text(context.get("gx_rest_vo2_per_hr_ml_per_beat"))
    peak_pox = _clean_text(context.get("gx_vo2_max_vo2_per_hr_ml_per_beat"))
    pred_pox = _clean_text(context.get("gx_predicted_vo2_per_hr_ml_per_beat"))
    if rest_hr and peak_hr:
        paragraphs.append(f"La frecuencia cardiaca pasó de {rest_hr} lpm en reposo a {peak_hr} lpm en el máximo esfuerzo.")
    elif rest_hr:
        paragraphs.append(f"La frecuencia cardiaca fue {rest_hr} lpm en reposo.")
    elif peak_hr:
        paragraphs.append(f"La frecuencia cardiaca alcanzó {peak_hr} lpm en el máximo esfuerzo.")
    if rest_sys and rest_dia and peak_sys and peak_dia:
        paragraphs.append(f"La presión arterial pasó de {rest_sys}/{rest_dia} mmHg en reposo a {peak_sys}/{peak_dia} mmHg en el máximo esfuerzo.")
    elif rest_sys and rest_dia:
        paragraphs.append(f"La presión arterial fue {rest_sys}/{rest_dia} mmHg en reposo.")
    elif peak_sys and peak_dia:
        paragraphs.append(f"La presión arterial alcanzó {peak_sys}/{peak_dia} mmHg en el máximo esfuerzo.")
    if rest_pox and peak_pox:
        phrase = f"El pulso de oxígeno pasó de {rest_pox} ml/latido en reposo a {peak_pox} ml/latido en el máximo esfuerzo"
        if pred_pox:
            phrase += f" y el predicho fue {pred_pox} ml/latido"
        paragraphs.append(f"{phrase}.")
    elif rest_pox:
        paragraphs.append(f"El pulso de oxígeno fue {rest_pox} ml/latido en reposo.")
    elif peak_pox:
        paragraphs.append(f"El pulso de oxígeno alcanzó {peak_pox} ml/latido en el máximo esfuerzo.")
    elif pred_pox:
        paragraphs.append(f"El pulso de oxígeno predicho fue {pred_pox} ml/latido.")
    recovery = _clean_text(context.get("cardio_recovery"))
    ecg = _clean_text(context.get("cardio_ecg"))
    valuation = _clean_text(context.get("cardio_valuation"))
    if recovery:
        paragraphs.append(f"Recuperación {recovery}.")
    if ecg:
        paragraphs.append(f"ECG {ecg}.")
    if valuation:
        paragraphs.append(f"Valoración clínica {valuation}.")
    return tuple(paragraphs)


def _ventilatory_paragraph(context: Mapping[str, str]) -> tuple[str, ...]:
    mvv = _clean_text(context.get("pf_pre_mvv_l_per_min"))
    rest_ve = _clean_text(context.get("gx_rest_ve_btps_l_per_min"))
    peak_ve = _clean_text(context.get("gx_vo2_max_ve_btps_l_per_min"))
    ve_mvv = _clean_text(context.get("gx_vo2_max_ve_per_mvv_pct"))
    vt_ci = _clean_text(context.get("gx_vo2_max_vt_per_ic_pct"))
    rest_rr = _clean_text(context.get("gx_rest_rr_br_per_min"))
    peak_rr = _clean_text(context.get("gx_vo2_max_rr_br_per_min"))
    rest_spo2 = _clean_text(context.get("gx_rest_spo2_pct"))
    peak_spo2 = _clean_text(context.get("gx_vo2_max_spo2_pct"))
    paragraphs: list[str] = []
    if mvv:
        paragraphs.append(f"VVM pretest {mvv} L/min.")
    if rest_ve and peak_ve:
        paragraphs.append(f"La ventilación minuto pasó de {rest_ve} BTPS L/min en reposo a {peak_ve} BTPS L/min en el máximo esfuerzo.")
    elif rest_ve:
        paragraphs.append(f"La ventilación minuto fue {rest_ve} BTPS L/min en reposo.")
    elif peak_ve:
        paragraphs.append(f"La ventilación minuto alcanzó {peak_ve} BTPS L/min en el máximo esfuerzo.")
    if ve_mvv:
        paragraphs.append(f"La relación VE/MVV máxima fue {ve_mvv} %.")
    if vt_ci:
        paragraphs.append(f"La relación VT/CI máxima fue {vt_ci} %.")
    if rest_rr and peak_rr:
        paragraphs.append(f"La frecuencia respiratoria pasó de {rest_rr} br/min en reposo a {peak_rr} br/min en el máximo esfuerzo.")
    elif rest_rr:
        paragraphs.append(f"La frecuencia respiratoria fue {rest_rr} br/min en reposo.")
    elif peak_rr:
        paragraphs.append(f"La frecuencia respiratoria alcanzó {peak_rr} br/min en el máximo esfuerzo.")
    if rest_spo2 and peak_spo2:
        paragraphs.append(f"La SpO₂ pasó de {rest_spo2} % en reposo a {peak_spo2} % en el máximo esfuerzo.")
    elif rest_spo2:
        paragraphs.append(f"La SpO₂ fue {rest_spo2} % en reposo.")
    elif peak_spo2:
        paragraphs.append(f"La SpO₂ alcanzó {peak_spo2} % en el máximo esfuerzo.")
    return tuple(paragraphs)


def _gas_paragraph(context: Mapping[str, str]) -> tuple[str, ...]:
    paragraphs: list[str] = []
    rest_vdvt = _clean_text(context.get("gx_rest_vd_per_vt_meas"))
    peak_vdvt = _clean_text(context.get("gx_vo2_max_vd_per_vt_meas"))
    rest_petco2 = _clean_text(context.get("gx_rest_petco2_mmhg"))
    peak_petco2 = _clean_text(context.get("gx_vo2_max_petco2_mmhg"))
    arterial = _clean_text(context.get("arterial_gases"))
    threshold = _clean_text(context.get("anaerobic_threshold"))
    if rest_vdvt or peak_vdvt:
        if rest_vdvt and peak_vdvt:
            paragraphs.append(f"VD/VT pasó de {rest_vdvt} en reposo a {peak_vdvt} en el máximo esfuerzo.")
        elif rest_vdvt:
            paragraphs.append(f"VD/VT fue {rest_vdvt} en reposo.")
        elif peak_vdvt:
            paragraphs.append(f"VD/VT alcanzó {peak_vdvt} en el máximo esfuerzo.")
    if rest_petco2 or peak_petco2:
        if rest_petco2 and peak_petco2:
            paragraphs.append(f"PETCO₂ pasó de {rest_petco2} mmHg en reposo a {peak_petco2} mmHg en el máximo esfuerzo.")
        elif rest_petco2:
            paragraphs.append(f"PETCO₂ fue {rest_petco2} mmHg en reposo.")
        elif peak_petco2:
            paragraphs.append(f"PETCO₂ alcanzó {peak_petco2} mmHg en el máximo esfuerzo.")
    if arterial:
        paragraphs.append(f"Gases arteriales {arterial}.")
    if threshold:
        paragraphs.append(f"Valoración clínica del umbral anaeróbico {threshold}.")
    return tuple(paragraphs)


def _compose_section_paragraphs(section_key: str, context: Mapping[str, str]) -> tuple[str, ...]:
    if section_key == "identificacion":
        paragraphs = [
            _identification_paragraph(context),
            _clinical_paragraph(context),
            _habits_paragraph(context),
            _referral_paragraph(context),
        ]
        return tuple(paragraph for paragraph in paragraphs if paragraph)
    if section_key == "antecedentes":
        return tuple(
            paragraph
            for paragraph in (
                _anthropometry_paragraph(context),
                _hematology_paragraph(context),
            )
            if paragraph
        )
    if section_key == "protocolo":
        return tuple(
            paragraph
            for paragraph in (
                _protocol_paragraph(context),
                _protocol_support_paragraph(context),
            )
            if paragraph
        )
    if section_key == "capacidad_funcional":
        return tuple(
            paragraph
            for paragraph in (
                _functional_paragraph(context),
            )
            if paragraph
        )
    if section_key == "respuesta_cardiovascular":
        return _cardio_paragraph(context)
    if section_key == "respuesta_ventilatoria":
        return _ventilatory_paragraph(context)
    if section_key == "intercambio_gaseoso":
        return _gas_paragraph(context)
    if section_key == "conclusiones":
        text = _clean_text(context.get("conclusions"))
        if not text:
            return ()
        return tuple(paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip())
    return ()


SECTION_NARRATIVE_DOCS = {
    "identificacion": (
        "Párrafo 1: remisión, médico remitente, exposición, oxigenoterapia y medicación en frases independientes cuando existan.",
        "Párrafo 2: diagnóstico y síntomas referidos en frases independientes cuando existan.",
        "Párrafo 3: hábitos clínicos en frases independientes cuando existan.",
    ),
    "antecedentes": (
        "Párrafo 1: medidas antropométricas con peso, estatura e IMC.",
        "Párrafo 2: hemoglobina y hematocrito.",
    ),
    "protocolo": (
        "Párrafo 1: duración, carga máxima y RER del esfuerzo.",
        "Párrafo 2: etapas y Borg.",
    ),
    "capacidad_funcional": (
        "Párrafo 1: VO₂ en reposo.",
        "Párrafo 2: VO₂ pico.",
        "Párrafo 3: carga pico y pendiente VO₂/carga.",
        "Párrafo 4: valores predichos.",
    ),
    "respuesta_cardiovascular": (
        "Párrafo 1: frecuencia cardiaca y presión arterial.",
        "Párrafo 2: pulso de oxígeno y parámetros manuales o interpretativos.",
    ),
    "respuesta_ventilatoria": (
        "Párrafo 1: VVM y ventilación minuto.",
        "Párrafo 2: VE/MVV y VT/CI.",
        "Párrafo 3: frecuencia respiratoria y SpO₂.",
    ),
    "intercambio_gaseoso": (
        "Párrafo 1: VD/VT y PETCO₂.",
        "Párrafo 2: gases arteriales y umbral anaeróbico.",
    ),
    "conclusiones": (
        "Párrafo único de texto libre con los saltos de línea del usuario.",
    ),
}


PRESENTATION_WIDTH_BOUNDS = {
    "compact": (6, 8, 7),
    "numeric": (10, 12, 11),
    "medium": (14, 20, 16),
    "flex": (18, 32, 22),
    "long": (28, 56, 34),
    "full": (40, 120, 80),
    "auto": (10, 24, 14),
}

STATUS_BADGES = {
    "gx": "GX",
    "modified": "Editado",
    "manual": "Manual",
    "pending": "Pendiente",
}


def _lookup_value(
    row: Mapping[str, object],
    submitted_values: Mapping[str, str] | None,
    spec: ReportValueSpec,
) -> tuple[str, str, str]:
    source_key = spec.source_keys[0] if spec.source_keys else ""
    row_value = _clean_text(row.get(source_key)) if source_key else ""
    if submitted_values is not None and spec.key in submitted_values:
        current_value = _clean_text(submitted_values[spec.key])
    elif source_key:
        current_value = row_value
    else:
        current_value = ""
    if row_value:
        initial_source = "gx"
    elif current_value:
        initial_source = "manual"
    else:
        initial_source = "absent"
    return row_value, current_value, initial_source


def _status_for_value(initial_source: str, initial_value: str, current_value: str) -> tuple[str, str]:
    if not _has_text(current_value):
        return "pending", PENDIENTE
    if initial_source == "gx":
        if _clean_text(current_value) == _clean_text(initial_value):
            return "gx", GX_DILIGENCIADO
        return "modified", MODIFICADO
    if initial_source == "manual":
        return "manual", MANUAL_DILIGENCIADO
    return "pending", PENDIENTE


def _status_badge(status_key: str) -> str:
    return STATUS_BADGES.get(status_key, status_key.title())


def _resolve_presentation_bounds(presentation_width: str) -> tuple[int, int, int]:
    return PRESENTATION_WIDTH_BOUNDS.get(presentation_width, PRESENTATION_WIDTH_BOUNDS["auto"])


def _control_width(value: str, *, presentation_width: str = "auto", fallback: int = 8) -> int:
    text = _clean_text(value)
    minimum, maximum, base = _resolve_presentation_bounds(presentation_width)
    length = len(text) if text else fallback
    width = max(minimum, min(maximum, length + 2))
    return max(width, base if text else minimum)


def _render_context(values: Mapping[str, str]) -> dict[str, str]:
    context = {key: _clean_text(value) for key, value in values.items()}
    context["patient_full_name"] = format_full_name(
        values.get("patient_first_name"),
        values.get("patient_middle_name"),
        values.get("patient_last_name"),
    )
    context["visit_datetime_label"] = format_visit_datetime(values.get("visit_datetime"))
    context["height_cm"] = _format_height_cm(values.get("height"))
    return context


def _display_full_name(
    first_name: object,
    middle_name: object,
    last_name: object,
) -> str:
    parts = [
        _clean_text(first_name),
        _clean_text(middle_name),
        _clean_text(last_name),
    ]
    full_name = " ".join(part for part in parts if part)
    return full_name or "No disponible"


def _render_parts(
    spec: ReportElementSpec,
    context: Mapping[str, str],
) -> tuple[str, ...]:
    rendered: list[str] = []
    for part in spec.narrative_parts:
        if any(not _has_text(context.get(key)) for key in part.required_keys):
            continue
        text = _format_map(part.template, context)
        text = _clean_text(text)
        if text:
            rendered.append(text)
    return tuple(rendered)


def _render_element_narrative(
    spec: ReportElementSpec,
    context: Mapping[str, str],
) -> str:
    if spec.narrative_style == "free_text":
        text = _clean_text(context.get("conclusions"))
        if not text:
            return ""
        paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
        return "\n\n".join(paragraphs)

    parts = _render_parts(spec, context)
    if not parts:
        return ""

    if spec.narrative_style == "sentences":
        return " ".join(_sentence(part) for part in parts)

    if spec.narrative_style == "prefix_clauses":
        first = parts[0]
        rest = list(parts[1:])
        if not rest:
            return _sentence(first)
        if len(rest) == 1:
            body = f"{first} y {rest[0]}"
        else:
            body = f"{first}, {', '.join(rest[:-1])} y {rest[-1]}"
        return _sentence(body)

    if spec.narrative_style == "dual_variant":
        return _sentence(parts[0])

    raise ValueError(f"Unknown narrative style: {spec.narrative_style}")


def _transform_value(spec: ReportValueSpec, value: str) -> str:
    if spec.transform == "height_cm":
        return _format_height_cm(value)
    return value


def _build_variable_view(
    spec: ReportValueSpec,
    row: Mapping[str, object],
    submitted_values: Mapping[str, str] | None,
) -> ReportValueView:
    initial_value, current_value, initial_source = _lookup_value(row, submitted_values, spec)
    transformed_initial = _transform_value(spec, initial_value)
    transformed_current = _transform_value(spec, current_value)
    status_key, status_label = _status_for_value(initial_source, transformed_initial, transformed_current)
    return ReportValueView(
        key=spec.key,
        label=spec.label,
        source_keys=spec.source_keys,
        unit=spec.unit,
        input_type=spec.input_type,
        rows=spec.rows,
        transform=spec.transform,
        presentation_width=spec.presentation_width,
        width_ch=_control_width(
            transformed_current or transformed_initial or spec.label,
            presentation_width=spec.presentation_width,
        ),
        value=transformed_current,
        initial_value=transformed_initial,
        source_state=initial_source,
        status_key=status_key,
        status_label=status_label,
        status_badge=_status_badge(status_key),
    )


def _build_element_view(
    spec: ReportElementSpec,
    row: Mapping[str, object],
    submitted_values: Mapping[str, str] | None,
) -> ReportElementView:
    variable_views = tuple(_build_variable_view(value_spec, row, submitted_values) for value_spec in spec.values)
    context = _render_context(
        {
            value_view.key: value_view.value
            for value_view in variable_views
        }
    )
    narrative_text = _render_element_narrative(spec, context)
    narrative_paragraphs = tuple(
        paragraph.strip()
        for paragraph in narrative_text.split("\n\n")
        if paragraph.strip()
    )
    filled_count = sum(1 for variable in variable_views if _has_text(variable.value))
    total_count = len(variable_views)
    completed = _has_text(narrative_text)
    if filled_count == 0 or not completed:
        status_key = "pending"
        status_label = PENDIENTE
    else:
        statuses = {variable.status_key for variable in variable_views if _has_text(variable.value)}
        if statuses == {"gx"}:
            status_key = "gx"
            status_label = GX_DILIGENCIADO
        elif statuses == {"manual"}:
            status_key = "manual"
            status_label = MANUAL_DILIGENCIADO
        else:
            status_key = "modified"
            status_label = MODIFICADO
    if not completed:
        status_key = "pending"
        status_label = PENDIENTE
    return ReportElementView(
        spec=spec,
        values=variable_views,
        status_key=status_key,
        status_label=status_label,
        narrative_text=narrative_text,
        narrative_paragraphs=narrative_paragraphs,
        completed=completed,
        filled_count=filled_count,
        total_count=total_count,
        status_badge=_status_badge(status_key),
    )


def _build_section_view(
    spec: ReportSectionSpec,
    row: Mapping[str, object],
    submitted_values: Mapping[str, str] | None,
) -> ReportSectionView:
    element_views = tuple(
        _build_element_view(element_spec, row, submitted_values)
        for element_spec in sorted(spec.elements, key=lambda element_spec: element_spec.order)
    )
    completed_count = sum(1 for element in element_views if element.completed)
    total_count = len(element_views)
    context = _render_context(
        {
            value.key: value.value
            for element in element_views
            for value in element.values
        }
    )
    narrative_paragraphs = _compose_section_paragraphs(spec.key, context)
    return ReportSectionView(
        spec=spec,
        elements=element_views,
        completed_count=completed_count,
        total_count=total_count,
        narrative_paragraphs=tuple(narrative_paragraphs),
    )


def field_values_from_form(items: Iterable[tuple[str, str]]) -> dict[str, str]:
    editable_keys = {element_value.key for section in REPORT_SECTION_SPECS for element in section.elements for element_value in element.values}
    values: dict[str, str] = {}
    for key, value in items:
        if key in editable_keys:
            values[key] = value
    return values


def render_narrative_section(section: ReportSectionView) -> str:
    return "\n\n".join(section.narrative_paragraphs)


def build_study_draft_view(
    row: Mapping[str, object],
    submitted_values: Mapping[str, str] | None = None,
) -> StudyDraftView:
    submitted_values = submitted_values or {}
    sections = tuple(
        _build_section_view(section_spec, row, submitted_values)
        for section_spec in sorted(REPORT_SECTION_SPECS, key=lambda spec: spec.order)
    )
    global_completed = sum(section.completed_count for section in sections)
    global_total = sum(section.total_count for section in sections)
    return StudyDraftView(
        lookup_patient_id_num=_clean_text(row.get("patient_id_num")),
        lookup_visit_datetime=format_visit_datetime(row.get("visit_datetime")),
        lookup_patient_full_name=_display_full_name(
            row.get("patient_first_name"),
            row.get("patient_middle_name"),
            row.get("patient_last_name"),
        ),
        lookup_patient_age=_clean_text(row.get("age")),
        lookup_patient_sex=_clean_text(row.get("sex")),
        sections=sections,
        global_completed_count=global_completed,
        global_total_count=global_total,
    )


def generate_structure_markdown() -> str:
    lines: list[str] = []
    lines.append("# Estructura del informe")
    lines.append("")
    lines.append("El informe es efímero, narrativo y editable. Se construye a partir de un estado canónico en memoria y no persiste fuera de la sesión actual.")
    lines.append("")
    lines.append("## Convenciones")
    lines.append("")
    lines.append("* `DIRECTO`: procede de una columna clínica sin redacción adicional.")
    lines.append("* `CALCULADO`: se compone o formatea a partir de una o varias columnas.")
    lines.append("* `MANUAL`: se escribe libremente en la interfaz.")
    lines.append("* `INTERPRETACIÓN`: es una valoración clínica redactada por la persona usuaria.")
    lines.append("")
    lines.append("## Metadatos de Elaboración")
    lines.append("")
    lines.append("* La vista de Elaboración se organiza como una hoja clínica en paneles, con encabezado resumido, navegación lateral y barra de herramientas fija.")
    lines.append("* Las secciones ocupan una cuadrícula semántica de 12 columnas con spans declarativos para priorizar Antecedentes clínicos y Conclusiones.")
    lines.append("* `compact`: campos breves como edad, RER y Borg.")
    lines.append("* `numeric`: campos numéricos con unidad.")
    lines.append("* `medium`: ID, fecha, sexo y categorías cortas.")
    lines.append("* `flex`: nombres y apellidos con crecimiento flexible.")
    lines.append("* `long`: diagnóstico, interpretación y texto clínico.")
    lines.append("* `full`: áreas multilínea y conclusiones.")
    lines.append("* `single`: una fila semántica simple.")
    lines.append("* `grouped`: varias variables relacionadas en una misma fila.")
    lines.append("")
    for section in sorted(REPORT_SECTION_SPECS, key=lambda spec: spec.order):
        lines.append(f"## {section.order}. {section.title}")
        lines.append("")
        lines.append("### Compositor narrativo")
        lines.append("")
        for paragraph in SECTION_NARRATIVE_DOCS.get(section.key, ()):
            lines.append(f"* {paragraph}")
        lines.append("")
        lines.append("### Elementos")
        lines.append("")
        for element in sorted(section.elements, key=lambda element: element.order):
            lines.append(f"{section.order}.{element.order}. {element.title}")
            lines.append(f"* Titulo: {element.title}")
            lines.append(f"* Origen: {element.origin}")
            lines.append(f"* Fuente: {', '.join(f'`{source}`' for source in element.source_columns) if element.source_columns else ''}")
            lines.append(f"* Unidad: {element.units}")
            lines.append("* Requisitos mínimos: al menos una cláusula narrativa válida.")
            lines.append(f"* Presentación de fila: {element.presentation_layout}")
            lines.append(
                "* Anchuras semánticas: "
                + ", ".join(f"{value.key}={value.presentation_width}" for value in element.values)
            )
            if len(element.values) > 1:
                lines.append("* Agrupación: " + ", ".join(value.label for value in element.values))
            lines.append(f"* Plantilla narrativa: {element.narrative_template}")
            if element.narrative_parts:
                lines.append("* Variantes parciales válidas:")
                for part in element.narrative_parts:
                    lines.append(f"  * `{part.template}`")
            lines.append("")
    lines.append("## Elementos declarados como `PENDIENTE_DE_VALIDACIÓN` que no se muestran actualmente")
    lines.append("")
    lines.append("* Ninguno declarado en la implementación inspeccionada.")
    lines.append("")
    return "\n".join(lines)
