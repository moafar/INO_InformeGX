"""Server-side reconstruction of the approved clinical narratives.

The browser editor and this module deliberately apply the same presentation
rules.  PDF generation only receives validated form controls and never accepts
rendered HTML from the client.
"""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata

from services.study_report import StudyReportView


SECTION_TITLES = (
    "Antecedentes clínicos y remisión",
    "Protocolo",
    "Capacidad funcional",
    "Respuesta cardiovascular",
    "Respuesta ventilatoria",
    "Conclusiones",
)

WEBER_CITATION = (
    "(Weber KT, Janicki JS. Exercise Testing in the Evaluation of the Patient "
    "with Chronic Cardiac Failure. Am Rev Respir Dis. 1984; 129: S60–S62)"
)


@dataclass(frozen=True, slots=True)
class NarrativeSection:
    """Plain-text fragments for one approved report section."""

    title: str
    fragments: tuple[str, ...]
    bulleted: bool = False
    citation: str | None = None


class _Values:
    """Read form-visible values with the same trimming rules as the editor."""

    _TRUE_VALUES = frozenset({"1", "true", "si", "sí"})

    def __init__(self, report: StudyReportView) -> None:
        self.report = report

    def value(self, key: str) -> str:
        value = self.report.field(key).value
        text = "" if value is None else str(value).strip()
        if key == "medicion_gases":
            return "true" if text.casefold() in self._TRUE_VALUES else ""
        return text

    def has(self, key: str) -> bool:
        return bool(self.value(key))

    def any(self, *keys: str) -> bool:
        return any(self.has(key) for key in keys)


def _antecedents(v: _Values) -> NarrativeSection:
    fragments: list[str] = []
    if v.has("motivo_remision"):
        fragments.append(f"Motivo de la remisión: {v.value('motivo_remision')}")
    if v.has("diagnosis"):
        fragments.append(f"Diagnóstico: {v.value('diagnosis')}")
    if v.has("disnea_mrc"):
        fragments.append(f"Disnea MRC: {v.value('disnea_mrc')}")

    tobacco: list[str] = []
    if v.has("tbco_prod"):
        tobacco.append(f"Tabaquismo: {v.value('tbco_prod')}")
    if v.has("pk_yrs"):
        tobacco.append(f"IPA: {v.value('pk_yrs')}")
    if v.has("biomasa"):
        tobacco.append(f"Exposición a biomasa: {v.value('biomasa')}")
    if v.has("oxigeno"):
        tobacco.append(f"Oxígeno: {v.value('oxigeno')}")
    if tobacco:
        fragments.append("  ".join(tobacco))

    if v.has("medicamentos"):
        fragments.append(f"Medicamentos: {v.value('medicamentos')}")

    anthropometry: list[str] = []
    if v.has("weight"):
        anthropometry.append(f"Peso: {v.value('weight')} kg")
    if v.has("height"):
        anthropometry.append(f"Estatura: {v.value('height')} cm")
    if v.has("bmi"):
        anthropometry.append(f"Índice de masa corporal: {v.value('bmi')} kg/m²")
    if anthropometry:
        fragments.append("Medidas antropométricas: " + "  ".join(anthropometry))

    laboratories: list[str] = []
    if v.has("hb"):
        laboratories.append(f"Hb: {v.value('hb')} g/dL")
    if v.has("hc"):
        laboratories.append(f"Hc: {v.value('hc')} %")
    if laboratories:
        fragments.append("  ".join(laboratories))

    return NarrativeSection(SECTION_TITLES[0], tuple(fragments))


def _protocol(v: _Values) -> NarrativeSection:
    items = [
        "Se utilizó una bicicleta ergométrica, hiperbólica y medición de gases "
        "espirados respiración a respiración."
    ]
    if v.has("medicion_gases"):
        items.append(
            "Se realizó medición de gases arteriales en reposo e inmediatamente "
            "al terminar el ejercicio."
        )
    items.append(
        "Se realizó monitoreo con oximetría de pulso, frecuencia cardiaca y "
        "tensión arterial."
    )

    if v.any(
        "gx_vo2_max_time_min",
        "cambio_watts_por_etapa",
        "gx_vo2_max_work_watts",
    ):
        line = ""
        if v.has("gx_vo2_max_time_min"):
            line = (
                f"La prueba tuvo una duración de {v.value('gx_vo2_max_time_min')} "
                "minutos. "
            )
        line += (
            "Inicia con 3 minutos de reposo, luego 3 minutos de ejercicio sin "
            "carga y continúa con pedaleo con carga"
        )
        if v.has("cambio_watts_por_etapa"):
            line += (
                " en incrementos progresivos de "
                f"{v.value('cambio_watts_por_etapa')} vatios"
            )
        if v.has("gx_vo2_max_work_watts"):
            line += (
                f", llegando a {v.value('gx_vo2_max_work_watts')} vatios, carga "
                "máxima tolerada por el paciente"
            )
        line += ", y finaliza con 1 minuto de recuperación."
        items.append(line)

    effort_keys = (
        "disnea_borg_inicial",
        "fatiga_borg_inicial",
        "disnea_borg_final",
        "fatiga_borg_final",
        "porc_fc_maxima",
        "porc_o2_predicho",
        "gx_vo2_max_rer",
        "sugerencia_rer",
    )
    if v.any(*effort_keys):
        line = ""
        if v.any("disnea_borg_inicial", "fatiga_borg_inicial"):
            line += "Se inicia"
            if v.has("disnea_borg_inicial"):
                line += f" con disnea {v.value('disnea_borg_inicial')}"
            if v.has("fatiga_borg_inicial"):
                line += (
                    " y" if v.has("disnea_borg_inicial") else " con"
                ) + f" fatiga {v.value('fatiga_borg_inicial')}"
            line += " por escala de Borg. "
        if v.any("disnea_borg_final", "fatiga_borg_final"):
            line += "Se suspendió la prueba"
            if v.has("disnea_borg_final"):
                line += f" con disnea {v.value('disnea_borg_final')}"
            if v.has("fatiga_borg_final"):
                line += (
                    " y" if v.has("disnea_borg_final") else " con"
                ) + f" fatiga {v.value('fatiga_borg_final')}"
            line += " por escala de Borg. "
        if v.any("porc_fc_maxima", "porc_o2_predicho"):
            line += "Se alcanzó"
            if v.has("porc_fc_maxima"):
                line += f" el {v.value('porc_fc_maxima')}% de la frecuencia cardiaca máxima"
            if v.has("porc_fc_maxima") and v.has("porc_o2_predicho"):
                line += " y"
            if v.has("porc_o2_predicho"):
                line += (
                    " un consumo de oxígeno pico del "
                    f"{v.value('porc_o2_predicho')}% del predicho"
                )
            line += ". "
        if v.has("gx_vo2_max_rer"):
            line += f"El RER en ejercicio pico fue {v.value('gx_vo2_max_rer')}. "
        if v.has("sugerencia_rer"):
            line += v.value("sugerencia_rer")
        items.append(line.strip())

    return NarrativeSection(SECTION_TITLES[1], tuple(items), bulleted=True)


def _functional(v: _Values) -> NarrativeSection:
    paragraphs: list[str] = []
    if v.any(
        "gx_rest_vo2_ml_per_min",
        "gx_rest_vo2_ml_per_kg_per_min",
        "interpretacion_consumo_vo2",
    ):
        line = ""
        if v.has("gx_rest_vo2_ml_per_min"):
            line += (
                "Consumo de oxígeno en reposo: "
                f"{v.value('gx_rest_vo2_ml_per_min')} ml/min"
            )
        if v.has("gx_rest_vo2_ml_per_kg_per_min"):
            line += (
                ", equivalente a"
                if v.has("gx_rest_vo2_ml_per_min")
                else "Consumo de oxígeno relativo en reposo:"
            )
            line += f" {v.value('gx_rest_vo2_ml_per_kg_per_min')} ml/kg/min"
        if v.has("interpretacion_consumo_vo2"):
            line += (
                ". Se considera "
                if v.any("gx_rest_vo2_ml_per_min", "gx_rest_vo2_ml_per_kg_per_min")
                else "Se considera "
            )
            line += v.value("interpretacion_consumo_vo2")
        paragraphs.append(f"{line}.")

    assessment = (
        "interpretacion_prueba_cp",
        "gx_vo2_max_vo2_ml_per_min",
        "porc_vo2_predicho",
        "gx_vo2_max_vo2_ml_per_kg_per_min_1",
        "clase_funcional",
        "carga_max_w",
        "relacion_consumo_trabajo",
        "interpretacion_relacion_consumo_trabajo",
    )
    if v.any(*assessment):
        line = "Prueba de ejercicio cardiopulmonar"
        if v.has("interpretacion_prueba_cp"):
            line += f" {v.value('interpretacion_prueba_cp')}"
        line += ". "
        if v.has("gx_vo2_max_vo2_ml_per_min"):
            line += (
                "Se alcanzó un consumo de oxígeno pico (VO₂ pico) de "
                f"{v.value('gx_vo2_max_vo2_ml_per_min')} ml/min de O₂"
            )
        if v.has("porc_vo2_predicho"):
            line += (
                ", correspondiente al"
                if v.has("gx_vo2_max_vo2_ml_per_min")
                else "El VO₂ pico correspondió al"
            )
            line += f" {v.value('porc_vo2_predicho')}% del predicho"
        if v.any("gx_vo2_max_vo2_ml_per_min", "porc_vo2_predicho"):
            line += "."
        if v.has("gx_vo2_max_vo2_ml_per_kg_per_min_1"):
            line += (
                " En relación con el peso, el VO₂ pico fue de "
                f"{v.value('gx_vo2_max_vo2_ml_per_kg_per_min_1')} ml/kg/min."
            )
        if v.has("clase_funcional"):
            line += f" Clase funcional {v.value('clase_funcional')}."
        if v.has("carga_max_w"):
            line += (
                " La carga máxima de trabajo correspondió al "
                f"{v.value('carga_max_w')}% de lo esperado."
            )
        if v.has("relacion_consumo_trabajo"):
            line += (
                " La relación consumo-trabajo (VO₂/W) fue de "
                f"{v.value('relacion_consumo_trabajo')} ml O₂/min/W"
            )
        if v.has("interpretacion_relacion_consumo_trabajo"):
            line += (
                ". Se considera "
                if v.has("relacion_consumo_trabajo")
                else " Se considera "
            )
            line += v.value("interpretacion_relacion_consumo_trabajo")
        line += "."
        paragraphs.append(line)

    return NarrativeSection(
        SECTION_TITLES[2],
        tuple(paragraphs),
        citation=WEBER_CITATION if paragraphs else None,
    )


def _cardiovascular(v: _Values) -> NarrativeSection:
    paragraphs: list[str] = []
    primary = (
        "ritmo_cardio_inicial",
        "gx_rest_hr_bpm",
        "gx_vo2_max_hr_bpm",
        "calif_fc",
        "ritmo_ekg",
        "gx_rest_sysbp_mmhg",
        "gx_rest_diabp_mmhg",
        "gx_vo2_max_sysbp_mmhg",
        "gx_vo2_max_diabp_mmhg",
        "latidos_recuperados_minuto",
        "vo2_minuto",
    )
    if v.any(*primary):
        line = ""
        if v.any("ritmo_cardio_inicial", "gx_rest_hr_bpm"):
            line += "El paciente inició la prueba"
            if v.has("ritmo_cardio_inicial"):
                line += f" en ritmo {v.value('ritmo_cardio_inicial')}"
            if v.has("gx_rest_hr_bpm"):
                line += f" con frecuencia cardíaca de {v.value('gx_rest_hr_bpm')}/min"
            if v.has("gx_vo2_max_hr_bpm"):
                line += (
                    ", incrementando hasta el final del ejercicio a "
                    f"{v.value('gx_vo2_max_hr_bpm')}/min. "
                )
            else:
                line += ". "
        elif v.has("gx_vo2_max_hr_bpm"):
            line += (
                "La frecuencia cardíaca al final del ejercicio fue de "
                f"{v.value('gx_vo2_max_hr_bpm')}/min. "
            )
        if v.has("calif_fc"):
            line += f"Frecuencia cardíaca: {v.value('calif_fc')}. "
        if v.has("ritmo_ekg"):
            line += f"EKG en ritmo {v.value('ritmo_ekg')} durante la prueba. "
        if v.any("gx_rest_sysbp_mmhg", "gx_rest_diabp_mmhg"):
            initial_bp = "/".join(
                value
                for value in (
                    v.value("gx_rest_sysbp_mmhg"),
                    v.value("gx_rest_diabp_mmhg"),
                )
                if value
            )
            line += f"T.A. inicial: {initial_bp} mmHg. "
        if v.any("gx_vo2_max_sysbp_mmhg", "gx_vo2_max_diabp_mmhg"):
            final_bp = "/".join(
                value
                for value in (
                    v.value("gx_vo2_max_sysbp_mmhg"),
                    v.value("gx_vo2_max_diabp_mmhg"),
                )
                if value
            )
            line += f"T.A. final: {final_bp} mmHg. "
        if v.has("latidos_recuperados_minuto"):
            line += (
                f"{v.value('latidos_recuperados_minuto')} latidos recuperados al "
                "minuto de terminar. "
            )
        if v.has("vo2_minuto"):
            line += (
                "El VO₂ al minuto de finalizar el ejercicio fue de "
                f"{v.value('vo2_minuto')} ml/min."
            )
        paragraphs.append(line.strip())

    if v.any(
        "porc_pred_o2_latido_6",
        "interpretacion_o2_latido_6",
        "umbral_anaerobio_alcanzado",
    ):
        line = ""
        if v.has("porc_pred_o2_latido_6"):
            line += (
                "El oxígeno latido (ml O₂/lat) correspondió al "
                f"{v.value('porc_pred_o2_latido_6')}% del predicho. "
            )
        if v.has("interpretacion_o2_latido_6"):
            line += f"Se considera {v.value('interpretacion_o2_latido_6')}. "
        if v.has("umbral_anaerobio_alcanzado"):
            line += (
                f"El umbral anaerobio {v.value('umbral_anaerobio_alcanzado')} fue "
                "alcanzado durante el ejercicio."
            )
        paragraphs.append(line.strip())

    return NarrativeSection(SECTION_TITLES[3], tuple(paragraphs))


def _normalized_threshold(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFD", value)
        if unicodedata.category(character) != "Mn"
    ).upper()


def _ventilatory(v: _Values) -> NarrativeSection:
    threshold = _normalized_threshold(v.value("umbral_anaerobio_alcanzado"))
    not_reached = threshold == "NO"
    reached = threshold == "SI"
    paragraphs: list[str] = []

    ventilation = (
        "interpretacion_curva_flujo_volumen",
        "pf_pre_mvv_l_per_min",
        "gx_rest_ve_btps_l_per_min",
        "gx_vo2_max_ve_btps_l_per_min",
        "reserva_respiratoria_pico_l",
        "interpretacion_reserva_pico_vvm",
        "gx_vo2_max_ve_per_mvv_pct",
        "gx_vo2_max_vt_per_ic_pct",
        "comportamiento_vvm",
    )
    if v.any(*ventilation):
        line = ""
        if v.has("interpretacion_curva_flujo_volumen"):
            line += (
                "Curva flujo-volumen basal "
                f"{v.value('interpretacion_curva_flujo_volumen')}. "
            )
        if v.has("pf_pre_mvv_l_per_min"):
            line += f"La VVM medida fue de {v.value('pf_pre_mvv_l_per_min')} L/min. "
        if v.any("gx_rest_ve_btps_l_per_min", "gx_vo2_max_ve_btps_l_per_min"):
            line += "La ventilación minuto (VE)"
            if v.has("gx_rest_ve_btps_l_per_min"):
                line += f" fue de {v.value('gx_rest_ve_btps_l_per_min')} L/min en reposo"
            if v.has("gx_vo2_max_ve_btps_l_per_min"):
                line += (
                    " y aumentó hasta "
                    if v.has("gx_rest_ve_btps_l_per_min")
                    else " fue de "
                )
                line += (
                    f"{v.value('gx_vo2_max_ve_btps_l_per_min')} L/min en ejercicio pico"
                )
            line += ". "
        if v.has("reserva_respiratoria_pico_l"):
            line += (
                "Esto determina una reserva respiratoria en el ejercicio pico de "
                f"{v.value('reserva_respiratoria_pico_l')} L/min. "
            )
        if v.has("interpretacion_reserva_pico_vvm"):
            line += f"Se considera {v.value('interpretacion_reserva_pico_vvm')}. "
        if v.has("gx_vo2_max_ve_per_mvv_pct"):
            line += f"La relación VE/VVM fue de {v.value('gx_vo2_max_ve_per_mvv_pct')}%"
        if v.has("gx_vo2_max_vt_per_ic_pct"):
            line += (
                " y la relación" if v.has("gx_vo2_max_ve_per_mvv_pct") else "La relación"
            )
            line += f" VT/CI fue de {v.value('gx_vo2_max_vt_per_ic_pct')}%"
        if v.any("gx_vo2_max_ve_per_mvv_pct", "gx_vo2_max_vt_per_ic_pct"):
            line += ". "
        if v.has("comportamiento_vvm"):
            line += f"{v.value('comportamiento_vvm')}."
        paragraphs.append(line.strip())

    pattern = (
        "gx_rest_rr_br_per_min",
        "gx_vo2_max_rr_br_per_min_1",
        "observaciones_asa_volumen_corriente",
        "observaciones_volumen_minuto",
        "interpretacion_fr_maxima",
        "gx_rest_spo2_pct",
        "gx_vo2_max_spo2_pct",
    )
    if v.any(*pattern):
        line = ""
        if v.any("gx_rest_rr_br_per_min", "gx_vo2_max_rr_br_per_min_1"):
            line += "La prueba inició"
            if v.has("gx_rest_rr_br_per_min"):
                line += (
                    " con una frecuencia respiratoria de "
                    f"{v.value('gx_rest_rr_br_per_min')} resp/min"
                )
            if v.has("gx_vo2_max_rr_br_per_min_1"):
                line += (
                    ", que aumentó hasta "
                    if v.has("gx_rest_rr_br_per_min")
                    else " con una frecuencia respiratoria máxima de "
                )
                line += f"{v.value('gx_vo2_max_rr_br_per_min_1')} resp/min"
            line += ". "
        if v.has("observaciones_asa_volumen_corriente"):
            line += (
                "Se observa que el asa de volumen corriente "
                f"{v.value('observaciones_asa_volumen_corriente')}. "
            )
        if v.has("observaciones_volumen_minuto"):
            line += f"El volumen minuto {v.value('observaciones_volumen_minuto')}. "
        if v.has("interpretacion_fr_maxima"):
            line += (
                "La frecuencia respiratoria máxima durante el ejercicio se considera "
                f"{v.value('interpretacion_fr_maxima')}. "
            )
        if v.any("gx_rest_spo2_pct", "gx_vo2_max_spo2_pct"):
            line += "La SpO₂ por pulso-oximetría"
            if v.has("gx_rest_spo2_pct"):
                line += f" en reposo fue de {v.value('gx_rest_spo2_pct')}%"
            if v.has("gx_vo2_max_spo2_pct"):
                line += (
                    ", mientras que al final del ejercicio fue de "
                    if v.has("gx_rest_spo2_pct")
                    else " al final del ejercicio fue de "
                )
                line += f"{v.value('gx_vo2_max_spo2_pct')}%"
            line += "."
        paragraphs.append(line.strip())

    gas = (
        "gx_rest_vd_per_vt_meas",
        "gx_vo2_max_vd_per_vt_meas",
        "relacion_vdvt_reposo",
        "comportamiento_relacion_vdvt",
        "gx_rest_petco2_mmhg",
        "comportamiento_petco2_rest_ejercicio_total",
        "comportamiento_petco2_rest_ejercicio_maximo",
        "interpretacion_petco2_pico_reposo",
    )
    if v.any(*gas) or not_reached or (
        reached and v.any("gx_at_ve_per_vco2", "gx_at_ve_per_vo2")
    ):
        line = ""
        if v.any("gx_rest_vd_per_vt_meas", "gx_vo2_max_vd_per_vt_meas"):
            line += "El espacio muerto (VD/VT) medido por gases arteriales"
            if v.has("gx_rest_vd_per_vt_meas"):
                line += f" en reposo fue de {v.value('gx_rest_vd_per_vt_meas')}"
            if v.has("gx_vo2_max_vd_per_vt_meas"):
                line += (
                    " y en el ejercicio máximo fue de "
                    if v.has("gx_rest_vd_per_vt_meas")
                    else " en el ejercicio máximo fue de "
                )
                line += v.value("gx_vo2_max_vd_per_vt_meas")
            line += ". "
        if v.has("relacion_vdvt_reposo"):
            line += (
                "La relación VD/VT en reposo se considera "
                f"{v.value('relacion_vdvt_reposo')}. "
            )
        if v.has("comportamiento_relacion_vdvt"):
            line += (
                "Entre el reposo y el ejercicio máximo, la relación VD/VT "
                f"{v.value('comportamiento_relacion_vdvt')}. "
            )
        if not_reached:
            line += (
                "El equivalente respiratorio para CO₂ (VE/VCO₂) en el umbral "
                "láctico no aplica. El equivalente respiratorio para O₂ (VE/VO₂) "
                "en el umbral láctico no aplica. "
            )
        if reached:
            if v.has("gx_at_ve_per_vco2"):
                line += (
                    "El equivalente respiratorio para CO₂ (VE/VCO₂) en el umbral "
                    f"láctico fue de {v.value('gx_at_ve_per_vco2')}. "
                )
            if v.has("gx_at_ve_per_vo2"):
                line += (
                    "El equivalente respiratorio para O₂ (VE/VO₂) en el umbral "
                    f"láctico fue de {v.value('gx_at_ve_per_vo2')}. "
                )
        if v.has("gx_rest_petco2_mmhg"):
            line += f"La PETCO₂ en reposo fue de {v.value('gx_rest_petco2_mmhg')} mmHg. "
        if v.has("comportamiento_petco2_rest_ejercicio_total"):
            line += (
                f"Durante el ejercicio, la PETCO₂ "
                f"{v.value('comportamiento_petco2_rest_ejercicio_total')}. "
            )
        if v.has("comportamiento_petco2_rest_ejercicio_maximo"):
            line += (
                f"En el ejercicio máximo, la PETCO₂ "
                f"{v.value('comportamiento_petco2_rest_ejercicio_maximo')}. "
            )
        if v.has("interpretacion_petco2_pico_reposo"):
            line += (
                "La PETCO₂ en ejercicio pico respecto al reposo se considera "
                f"{v.value('interpretacion_petco2_pico_reposo')}."
            )
        paragraphs.append(line.strip())

    return NarrativeSection(SECTION_TITLES[4], tuple(paragraphs))


def _conclusions(v: _Values) -> NarrativeSection:
    fragments: list[str] = []
    metrics = ""
    if v.has("gx_vo2_max_vo2_ml_per_kg_per_min_2"):
        metrics += (
            "VO₂ pico relativo: "
            f"{v.value('gx_vo2_max_vo2_ml_per_kg_per_min_2')} ml/kg/min. "
        )
    if v.has("gx_vo2_max_vo2workslope_ml_per_min_per_watt"):
        metrics += (
            "Pendiente VO₂/trabajo: "
            f"{v.value('gx_vo2_max_vo2workslope_ml_per_min_per_watt')} ml/min/W. "
        )
    if v.has("gx_vo2_max_rr_br_per_min_2"):
        metrics += (
            "Frecuencia respiratoria máxima: "
            f"{v.value('gx_vo2_max_rr_br_per_min_2')} rpm."
        )
    if metrics:
        fragments.append(metrics)
    if v.has("conclusiones_definitivas"):
        fragments.append(v.value("conclusiones_definitivas"))
    return NarrativeSection(SECTION_TITLES[5], tuple(fragments))


def build_report_narratives(report: StudyReportView) -> tuple[NarrativeSection, ...]:
    """Rebuild all six approved narratives from form-visible values."""
    values = _Values(report)
    return (
        _antecedents(values),
        _protocol(values),
        _functional(values),
        _cardiovascular(values),
        _ventilatory(values),
        _conclusions(values),
    )
