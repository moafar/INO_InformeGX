# Integración de la plantilla Jinja aprobada

La página de resultados hereda de `templates/base.html` y conserva el flujo de
autenticación, cierre de sesión, CSRF, búsqueda exacta y borrador efímero. El
formulario contiene 87 controles con `id` y `name` coincidentes, distribuidos en
seis secciones.

## Selección del estudio

`routes/studies.py:select` delega en `services.search.build_study_draft`, que
recupera un único registro mediante
`repositories.studies.get_study_by_identity`. La identidad usada es
`(patient_id_num, visit_datetime)`, respaldada en la fuente por la restricción
única `ux_gx_analytics_patient_visit`.

## Procedencia y precedencia

`services/study_report.py` declara la procedencia de cada control:

* `GX` directo: una columna de `staging.gx_analytics`.
* `GX` derivado: exclusivamente columnas de ese mismo registro.
* `MANUAL`: sin columna clínica fuente.

En la primera carga, los GX proceden del registro seleccionado y los MANUAL
están vacíos. Al reenviar el formulario, los MANUAL recuperan el valor enviado.
Se mantiene la corrección efímera de un GX que ya ofrecía el editor anterior:
la interfaz muestra `GX · Editado`, conserva `data-original-value` y sigue
mostrando las columnas fuente. Nada se persiste en sesión ni en base de datos.

## Derivados implementados

Los porcentajes se presentan con un máximo de dos decimales, usando `Decimal` y
redondeo `ROUND_HALF_UP`. Un dato ausente, no numérico o un denominador cero
produce un campo vacío.

| Control | Fórmula |
|---|---|
| `porc_fc_maxima` | `gx_vo2_max_hr_bpm / gx_predicted_hr_bpm * 100` |
| `medicion_gases` | verdadero solo si existen `gx_rest_ph` y `gx_vo2_max_ph` |
| `porc_o2_predicho` | `gx_vo2_max_vo2_ml_per_min / gx_predicted_vo2_ml_per_min * 100` |
| `porc_vo2_predicho` | `gx_vo2_max_vo2_ml_per_min / gx_predicted_vo2_ml_per_min * 100` |
| `carga_max_w` | `gx_vo2_max_work_watts / gx_predicted_work_watts * 100` |
| `porc_pred_o2_latido_6` | `gx_vo2_max_vo2_per_hr_ml_per_beat / gx_predicted_vo2_per_hr_ml_per_beat * 100` |
| `reserva_respiratoria_pico_l` | `pf_pre_mvv_l_per_min - gx_vo2_max_ve_btps_l_per_min` |

Las operaciones se apoyan además de en las columnas indicadas por el paquete,
en los rótulos, unidades y frases narrativas aprobadas: “% del predicho” define
la relación medido/predicho, y “reserva respiratoria ... L/min” define la
diferencia entre VVM y VE pico.

## Diferencias frente al demo autónomo

* Se eliminan el documento HTML y encabezado de aplicación duplicados; la vista
  usa la herencia existente.
* Se conservan el logout y los tokens CSRF de la aplicación.
* Se añaden campos ocultos separados para la identidad estable del estudio y un
  botón `Actualizar borrador` para conservar el ciclo efímero existente.
* CSS y JavaScript viven en archivos específicos y los estilos se limitan a
  `.study-report-page`/`.study-report-body`.
* El JavaScript no calcula ni convierte variables clínicas. Solo lee controles,
  escapa texto dinámico y sincroniza narrativos e informe.
* La ruta de vista previa conserva datos sintéticos solo fuera de producción;
  la ruta normal nunca utiliza valores del demo.
