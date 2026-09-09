"""Authoritative classification and edit permissions for the 93 report controls."""

from __future__ import annotations

DIRECTO = "DIRECTO"
CALCULADO = "CALCULADO"
MANUAL = "MANUAL"
INTERPRETACION = "INTERPRETACIÓN"

AUXILIAR = "AUXILIAR"
MEDICO = "MEDICO"
COORDINADORA = "COORDINADORA"

DIRECT_CONTROL_IDS = frozenset(
    """patient_first_name patient_middle_name patient_last_name age sex visit_date
    patient_id_num diagnosis weight height bmi tbco_prod pk_yrs gx_vo2_max_time_min
    gx_vo2_max_work_watts gx_vo2_max_rer gx_rest_vo2_ml_per_min
    gx_rest_vo2_ml_per_kg_per_min gx_vo2_max_vo2_ml_per_min
    gx_vo2_max_vo2_ml_per_kg_per_min_1 relacion_consumo_trabajo gx_rest_hr_bpm
    gx_vo2_max_hr_bpm gx_rest_sysbp_mmhg gx_rest_diabp_mmhg
    gx_vo2_max_sysbp_mmhg gx_vo2_max_diabp_mmhg
    gx_vo2_max_vo2_per_hr_ml_per_beat gx_at_ex_time_min pf_pre_mvv_l_per_min
    gx_rest_ve_btps_l_per_min gx_vo2_max_ve_btps_l_per_min gx_vo2_max_ve_per_mvv_pct
    gx_vo2_max_vt_per_ic_pct gx_rest_rr_br_per_min gx_vo2_max_rr_br_per_min_1
    gx_rest_spo2_pct gx_vo2_max_spo2_pct gx_rest_vd_per_vt_meas
    gx_vo2_max_vd_per_vt_meas gx_at_ve_per_vco2 gx_at_ve_per_vo2
    gx_rest_petco2_mmhg gx_vo2_max_vo2_ml_per_kg_per_min_2
    gx_vo2_max_vo2workslope_ml_per_min_per_watt gx_vo2_max_rr_br_per_min_2""".split()
)

CALCULATED_CONTROL_IDS = frozenset(
    """porc_fc_maxima medicion_gases porc_o2_predicho porc_vo2_predicho carga_max_w
    porc_pred_o2_latido_6 porc_vo2_at_predicho reserva_respiratoria_pico_l""".split()
)

AUXILIAR_MANUAL_CONTROL_IDS = frozenset(
    """motivo_remision hb hc disnea_mrc biomasa oxigeno medicamentos reposo_inicial_min
    tiempo_sin_carga_min disnea_borg_inicial disnea_borg_final fatiga_borg_inicial
    fatiga_borg_final cambio_watts_por_etapa""".split()
)

MEDICO_MANUAL_CONTROL_IDS = frozenset("latidos_recuperados_minuto vo2_minuto".split())

INTERPRETATION_CONTROL_IDS = frozenset(
    """sugerencia_rer interpretacion_consumo_vo2 interpretacion_prueba_cp clase_funcional
    interpretacion_relacion_consumo_trabajo ritmo_cardio_inicial calif_fc ritmo_ekg
    interpretacion_o2_latido_6 umbral_anaerobio_alcanzado
    interpretacion_curva_flujo_volumen comportamiento_vvm
    interpretacion_reserva_pico_vvm observaciones_asa_volumen_corriente
    observaciones_volumen_minuto interpretacion_fr_maxima relacion_vdvt_reposo
    comportamiento_relacion_vdvt comportamiento_petco2_rest_ejercicio_total
    comportamiento_petco2_rest_ejercicio_maximo interpretacion_petco2_pico_reposo
    comentario_petco2 conclusiones_definitivas""".split()
)

MANUAL_CONTROL_IDS = AUXILIAR_MANUAL_CONTROL_IDS | MEDICO_MANUAL_CONTROL_IDS

CONTROL_TYPES = {
    **{key: DIRECTO for key in DIRECT_CONTROL_IDS},
    **{key: CALCULADO for key in CALCULATED_CONTROL_IDS},
    **{key: MANUAL for key in MANUAL_CONTROL_IDS},
    **{key: INTERPRETACION for key in INTERPRETATION_CONTROL_IDS},
}


def controls_editable_by(role: str, *, signed_version_exists: bool) -> frozenset[str]:
    """Return controls editable by ``role`` for the current draft phase."""
    if role == AUXILIAR:
        return frozenset() if signed_version_exists else AUXILIAR_MANUAL_CONTROL_IDS
    if role == MEDICO:
        return frozenset(CONTROL_TYPES)
    return frozenset()
