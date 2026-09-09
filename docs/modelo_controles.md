# Modelo vigente de controles

La clasificación es definitiva y está implementada en
`services/report_controls.py`. Los 93 controles se reparten en 46 DIRECTO, 8
CALCULADO, 16 MANUAL y 23 INTERPRETACIÓN.

## DIRECTO

`patient_first_name`, `patient_middle_name`, `patient_last_name`, `age`, `sex`,
`visit_date`, `patient_id_num`, `diagnosis`, `weight`, `height`, `bmi`,
`tbco_prod`, `pk_yrs`, `gx_vo2_max_time_min`, `gx_vo2_max_work_watts`,
`gx_vo2_max_rer`, `gx_rest_vo2_ml_per_min`,
`gx_rest_vo2_ml_per_kg_per_min`, `gx_vo2_max_vo2_ml_per_min`,
`gx_vo2_max_vo2_ml_per_kg_per_min_1`, `relacion_consumo_trabajo`,
`gx_rest_hr_bpm`, `gx_vo2_max_hr_bpm`, `gx_rest_sysbp_mmhg`,
`gx_rest_diabp_mmhg`, `gx_vo2_max_sysbp_mmhg`,
`gx_vo2_max_diabp_mmhg`, `gx_vo2_max_vo2_per_hr_ml_per_beat`,
`gx_at_ex_time_min`, `pf_pre_mvv_l_per_min`, `gx_rest_ve_btps_l_per_min`,
`gx_vo2_max_ve_btps_l_per_min`, `gx_vo2_max_ve_per_mvv_pct`,
`gx_vo2_max_vt_per_ic_pct`, `gx_rest_rr_br_per_min`,
`gx_vo2_max_rr_br_per_min_1`, `gx_rest_spo2_pct`, `gx_vo2_max_spo2_pct`,
`gx_rest_vd_per_vt_meas`, `gx_vo2_max_vd_per_vt_meas`, `gx_at_ve_per_vco2`,
`gx_at_ve_per_vo2`, `gx_rest_petco2_mmhg`,
`gx_vo2_max_vo2_ml_per_kg_per_min_2`,
`gx_vo2_max_vo2workslope_ml_per_min_per_watt`, `gx_vo2_max_rr_br_per_min_2`.

## CALCULADO

`porc_fc_maxima`, `medicion_gases`, `porc_o2_predicho`,
`porc_vo2_predicho`, `carga_max_w`, `porc_pred_o2_latido_6`,
`porc_vo2_at_predicho`, `reserva_respiratoria_pico_l`.

## MANUAL

### AUXILIAR en PRELIMINAR

`motivo_remision`, `hb`, `hc`, `disnea_mrc`, `biomasa`, `oxigeno`,
`medicamentos`, `reposo_inicial_min`, `tiempo_sin_carga_min`,
`disnea_borg_inicial`, `disnea_borg_final`, `fatiga_borg_inicial`,
`fatiga_borg_final`, `cambio_watts_por_etapa`.

### MÉDICO en EN_FIRMA propio

`latidos_recuperados_minuto`, `vo2_minuto`.

## INTERPRETACIÓN — MÉDICO

`sugerencia_rer`, `interpretacion_consumo_vo2`,
`interpretacion_prueba_cp`, `clase_funcional`,
`interpretacion_relacion_consumo_trabajo`, `ritmo_cardio_inicial`, `calif_fc`,
`ritmo_ekg`, `interpretacion_o2_latido_6`, `umbral_anaerobio_alcanzado`,
`interpretacion_curva_flujo_volumen`, `comportamiento_vvm`,
`interpretacion_reserva_pico_vvm`, `observaciones_asa_volumen_corriente`,
`observaciones_volumen_minuto`, `interpretacion_fr_maxima`,
`relacion_vdvt_reposo`, `comportamiento_relacion_vdvt`,
`comportamiento_petco2_rest_ejercicio_total`,
`comportamiento_petco2_rest_ejercicio_maximo`,
`interpretacion_petco2_pico_reposo`, `comentario_petco2`,
`conclusiones_definitivas`.

`EDITADO` no es tipo. Solo DIRECTO/CALCULADO editados conservan original y
vigente en borrador y snapshot firmado. La editabilidad depende adicionalmente
del workflow: AUXILIAR solo edita sus 14 MANUAL en PRELIMINAR; MÉDICO solo los
93 controles de una versión EN_FIRMA de su propiedad. COORDINADORA no edita.

## Procedencia VD/VT persistida

Los dos controles VD/VT conservan de forma específica ambos valores clínicos
(medido y estimado) y la fuente seleccionada en el borrador. Al firmar, esa
metadata se incluye en el snapshot inmutable y se copia a una nueva versión.
Esto permite reconstruir el valor visible y su columna fuente sin volver a
consultar `staging`.

Los borradores y versiones creados antes de la migración 006 pueden carecer de
esta metadata. En esos casos se conserva el valor persistido existente, pero no
se inventan la alternativa ni la procedencia técnica ausente.
