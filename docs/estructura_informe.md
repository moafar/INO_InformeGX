# Estructura del informe

> La interfaz vigente es el formulario aprobado de seis secciones y 87
> controles documentado en `docs/integracion_jinja_aprobada.md`. El modelo
> declarativo descrito a continuación se conserva como referencia del borrador
> anterior y para compatibilidad interna, pero ya no controla la página de
> resultados.

El informe es efímero, narrativo y editable. Se construye a partir de un estado canónico en memoria y no persiste fuera de la sesión actual.

## Convenciones

* `DIRECTO`: procede de una columna clínica sin redacción adicional.
* `CALCULADO`: se compone o formatea a partir de una o varias columnas.
* `MANUAL`: se escribe libremente en la interfaz.
* `INTERPRETACIÓN`: es una valoración clínica redactada por la persona usuaria.

## Elaboración

### Estructura visual

* Cabecera clínica superior con ficha resumida del paciente, del estudio y del progreso global.
* Contenedor amplio para edición, con ancho objetivo aproximado de 1280 a 1440 px.
* Barra lateral con navegación por secciones, conteos y resaltado de la sección activa.
* Barra de herramientas superior fija con progreso global, filtro `Todos / Pendientes` y acceso a `Siguiente pendiente`.
* Hoja clínica central compacta, organizada como una cuadrícula de paneles semánticos con spans declarativos.
* Vista narrativa sin cambios funcionales y con su ancho documental propio.
* Las filas de cada sección se presentan como una secuencia compacta, con un único contenedor por sección y controles agrupados cuando comparten significado clínico.
* Los campos largos crecen hasta el límite disponible y las unidades aparecen alineadas a la derecha de cada control cuando existen.

### Metadatos de presentación

* `compact`: campos breves como edad, RER y Borg.
* `numeric`: números con unidad.
* `medium`: ID, fecha, sexo y categorías cortas.
* `flex`: nombres y apellidos con crecimiento flexible.
* `long`: diagnóstico, interpretación y texto clínico.
* `full`: áreas multilínea y conclusiones.
* `single`: fila semántica simple.
* `grouped`: varias variables relacionadas en una sola fila.

### Agrupaciones y spans de sección

* Antecedentes clínicos y remisión: `12` columnas.
* Antecedentes: `4` columnas.
* Protocolo: `8` columnas.
* Capacidad funcional: `12` columnas.
* Respuesta cardiovascular: `4` columnas.
* Respuesta ventilatoria: `4` columnas.
* Intercambio gaseoso: `4` columnas.
* Conclusiones: `12` columnas.

### Agrupaciones declaradas

* Antecedentes clínicos y remisión: motivo de remisión, médico remitente, diagnóstico, síntomas y hábitos comparten una secuencia compacta; fecha del estudio, nombre completo, identificación, edad y sexo quedan en la banda clínica auxiliar; nombre, segundo nombre y apellidos comparten una fila amplia.
* Protocolo: duración, carga máxima y RER comparten una fila.
* Antecedentes: peso, estatura e IMC comparten una fila.
* Respuesta cardiovascular: frecuencia cardiaca, presión arterial y pulso de oxígeno se presentan como filas agrupadas por variable relacionada.
* Respuesta ventilatoria: VVM, ventilación minuto, VE/MVV, VT/CI, frecuencia respiratoria y SpO₂ usan filas agrupadas cuando hay más de un valor.
* Intercambio gaseoso: VD/VT y PETCO₂ se presentan agrupados.
* Conclusiones: ocupan una fila completa con textarea autosize.

## 1. Antecedentes clínicos y remisión

### Compositor narrativo

* Párrafo 1: remisión, médico remitente, exposición, oxigenoterapia y medicación en frases independientes cuando existan.
* Párrafo 2: diagnóstico y síntomas referidos en frases independientes cuando existan.
* Párrafo 3: hábitos clínicos en frases independientes cuando existan.

### Elementos

1.1. Motivo de la remisión
* Titulo: Motivo de la remisión
* Origen: MANUAL
* Fuente: 
* Unidad: 
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Motivo de la remisión: {remision_motivo}.
* Variantes parciales válidas:
  * `Motivo de la remisión: {remision_motivo}.`

1.2. Médico remitente
* Titulo: Médico remitente
* Origen: MANUAL
* Fuente: 
* Unidad: 
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Médico remitente: {remision_medico}.
* Variantes parciales válidas:
  * `Médico remitente: {remision_medico}.`

1.3. Diagnóstico
* Titulo: Diagnóstico
* Origen: DIRECTO
* Fuente: `diagnosis`
* Unidad: 
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Diagnóstico: {diagnosis}.
* Variantes parciales válidas:
  * `Diagnóstico: {diagnosis}.`

1.4. Disnea
* Titulo: Disnea
* Origen: DIRECTO
* Fuente: `dyspnea`
* Unidad: 
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Disnea: {dyspnea}.
* Variantes parciales válidas:
  * `Disnea: {dyspnea}.`

1.5. Tos
* Titulo: Tos
* Origen: DIRECTO
* Fuente: `cough`
* Unidad: 
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Tos: {cough}.
* Variantes parciales válidas:
  * `Tos: {cough}.`

1.6. Sibilancias
* Titulo: Sibilancias
* Origen: DIRECTO
* Fuente: `wheez`
* Unidad: 
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Sibilancias: {wheez}.
* Variantes parciales válidas:
  * `Sibilancias: {wheez}.`

1.7. Tabaquismo
* Titulo: Tabaquismo
* Origen: DIRECTO
* Fuente: `tbco_prod`
* Unidad: 
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Tabaquismo: {tbco_prod}.
* Variantes parciales válidas:
  * `Tabaquismo: {tbco_prod}.`

1.8. Índice paquetes-año
* Titulo: Índice paquetes-año
* Origen: DIRECTO
* Fuente: `pk_yrs`
* Unidad: 
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Índice paquetes-año: {pk_yrs}.
* Variantes parciales válidas:
  * `Índice paquetes-año: {pk_yrs}.`

1.9. Exposición a biomasa
* Titulo: Exposición a biomasa
* Origen: MANUAL
* Fuente: 
* Unidad: 
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Exposición a biomasa: {biomasa_exposure}.
* Variantes parciales válidas:
  * `Exposición a biomasa: {biomasa_exposure}.`

1.10. Oxigenoterapia
* Titulo: Oxigenoterapia
* Origen: MANUAL
* Fuente: 
* Unidad: 
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Oxigenoterapia: {oxygenoterapia}.
* Variantes parciales válidas:
  * `Oxigenoterapia: {oxygenoterapia}.`

1.11. Medicamentos
* Titulo: Medicamentos
* Origen: MANUAL
* Fuente: 
* Unidad: 
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Medicamentos: {medications}.
* Variantes parciales válidas:
  * `Medicamentos: {medications}.`

1.12. Fecha y hora del estudio
* Titulo: Fecha y hora del estudio
* Origen: CALCULADO
* Fuente: `visit_datetime`
* Unidad: 
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Fecha y hora del estudio: {visit_datetime}.
* Variantes parciales válidas:
  * `Fecha y hora del estudio: {visit_datetime}.`

1.13. Nombre del paciente
* Titulo: Nombre del paciente
* Origen: CALCULADO
* Fuente: `patient_first_name`, `patient_middle_name`, `patient_last_name`
* Unidad: 
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Paciente {patient_full_name}.
* Variantes parciales válidas:
  * `Paciente {patient_full_name}.`

1.14. Identificación del paciente
* Titulo: Identificación del paciente
* Origen: DIRECTO
* Fuente: `patient_id_num`
* Unidad: 
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: ID {patient_id_num}.
* Variantes parciales válidas:
  * `ID {patient_id_num}.`

1.15. Edad
* Titulo: Edad
* Origen: DIRECTO
* Fuente: `age`
* Unidad: años
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Edad {age} años.
* Variantes parciales válidas:
  * `Edad {age} años.`

1.16. Sexo
* Titulo: Sexo
* Origen: DIRECTO
* Fuente: `sex`
* Unidad: 
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Sexo {sex}.
* Variantes parciales válidas:
  * `Sexo {sex}.`

## 2. Antecedentes

### Compositor narrativo

* Párrafo 1: medidas antropométricas con peso, estatura e IMC.
* Párrafo 2: hemoglobina y hematocrito.

### Elementos

2.1. Medidas antropométricas
* Titulo: Medidas antropométricas
* Origen: CALCULADO
* Fuente: `weight`, `height`, `bmi`
* Unidad: kg / cm / kg/m²
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Medidas antropométricas: peso {weight} kg, estatura {height_cm} cm e IMC {bmi} kg/m².
* Variantes parciales válidas:
  * `peso {weight} kg`
  * `estatura {height_cm} cm`
  * `e IMC {bmi} kg/m²`

2.2. Hemoglobina
* Titulo: Hemoglobina
* Origen: MANUAL
* Fuente: 
* Unidad: g/dL
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Hemoglobina: {hemoglobin} g/dL.
* Variantes parciales válidas:
  * `Hemoglobina: {hemoglobin} g/dL.`

2.3. Hematocrito
* Titulo: Hematocrito
* Origen: MANUAL
* Fuente: 
* Unidad: %
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Hematocrito: {hematocrit} %.
* Variantes parciales válidas:
  * `Hematocrito: {hematocrit} %.`

## 3. Protocolo

### Compositor narrativo

* Párrafo 1: duración, carga máxima y RER del esfuerzo.
* Párrafo 2: etapas y Borg.

### Elementos

3.1. Protocolo
* Titulo: Protocolo
* Origen: CALCULADO
* Fuente: `gx_vo2_max_time_min`, `gx_vo2_max_work_watts`, `gx_vo2_max_rer`
* Unidad: min / W
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Protocolo: duración {gx_vo2_max_time_min} min, carga máxima {gx_vo2_max_work_watts} W y RER {gx_vo2_max_rer}.
* Variantes parciales válidas:
  * `Protocolo: duración {gx_vo2_max_time_min} min`
  * `carga máxima {gx_vo2_max_work_watts} W`
  * `RER {gx_vo2_max_rer}`

3.2. Etapas
* Titulo: Etapas
* Origen: MANUAL
* Fuente: 
* Unidad: 
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Etapas: {protocol_stages}.
* Variantes parciales válidas:
  * `Etapas: {protocol_stages}.`

3.3. Borg disnea
* Titulo: Borg disnea
* Origen: MANUAL
* Fuente: 
* Unidad: 
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Borg disnea: {protocol_borg_disnea}.
* Variantes parciales válidas:
  * `Borg disnea: {protocol_borg_disnea}.`

3.4. Borg fatiga
* Titulo: Borg fatiga
* Origen: MANUAL
* Fuente: 
* Unidad: 
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Borg fatiga: {protocol_borg_fatiga}.
* Variantes parciales válidas:
  * `Borg fatiga: {protocol_borg_fatiga}.`

## 4. Capacidad funcional

### Compositor narrativo

* Párrafo 1: VO₂ en reposo.
* Párrafo 2: VO₂ pico.
* Párrafo 3: carga pico y pendiente VO₂/carga.
* Párrafo 4: valores predichos.

### Elementos

4.1. VO₂ en reposo
* Titulo: VO₂ en reposo
* Origen: CALCULADO
* Fuente: `gx_rest_vo2_ml_per_min`, `gx_rest_vo2_ml_per_kg_per_min`
* Unidad: ml/min / ml/kg/min
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: VO₂ en reposo {gx_rest_vo2_ml_per_min} ml/min ({gx_rest_vo2_ml_per_kg_per_min} ml/kg/min).
* Variantes parciales válidas:
  * `VO₂ en reposo {gx_rest_vo2_ml_per_min} ml/min ({gx_rest_vo2_ml_per_kg_per_min} ml/kg/min)`
  * `VO₂ en reposo {gx_rest_vo2_ml_per_min} ml/min`
  * `VO₂ en reposo {gx_rest_vo2_ml_per_kg_per_min} ml/kg/min`

4.2. VO₂ pico
* Titulo: VO₂ pico
* Origen: CALCULADO
* Fuente: `gx_vo2_max_vo2_ml_per_min`, `gx_vo2_max_vo2_ml_per_kg_per_min`
* Unidad: ml/min / ml/kg/min
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: VO₂ pico absoluto {gx_vo2_max_vo2_ml_per_min} ml/min y relativo {gx_vo2_max_vo2_ml_per_kg_per_min} ml/kg/min.
* Variantes parciales válidas:
  * `absoluto {gx_vo2_max_vo2_ml_per_min} ml/min`
  * `relativo {gx_vo2_max_vo2_ml_per_kg_per_min} ml/kg/min`

4.3. Carga y pendiente
* Titulo: Carga y pendiente
* Origen: CALCULADO
* Fuente: `gx_vo2_max_work_watts`, `gx_vo2_max_vo2workslope_ml_per_min_per_watt`
* Unidad: W / ml/min/W
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Carga pico {gx_vo2_max_work_watts} W y pendiente VO₂/carga {gx_vo2_max_vo2workslope_ml_per_min_per_watt} ml/min/W.
* Variantes parciales válidas:
  * `Carga pico {gx_vo2_max_work_watts} W`
  * `pendiente VO₂/carga {gx_vo2_max_vo2workslope_ml_per_min_per_watt} ml/min/W`

4.4. Predichos
* Titulo: Predichos
* Origen: CALCULADO
* Fuente: `gx_predicted_vo2_ml_per_min`, `gx_predicted_vo2_ml_per_kg_per_min`, `gx_predicted_work_watts`, `gx_predicted_vo2workslope_ml_per_min_per_watt`
* Unidad: ml/min / ml/kg/min / W / ml/min/W
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Predichos: VO₂ {gx_predicted_vo2_ml_per_min} ml/min; {gx_predicted_vo2_ml_per_kg_per_min} ml/kg/min; carga {gx_predicted_work_watts} W; pendiente {gx_predicted_vo2workslope_ml_per_min_per_watt} ml/min/W.
* Variantes parciales válidas:
  * `VO₂ {gx_predicted_vo2_ml_per_min} ml/min`
  * `{gx_predicted_vo2_ml_per_kg_per_min} ml/kg/min`
  * `carga {gx_predicted_work_watts} W`
  * `pendiente {gx_predicted_vo2workslope_ml_per_min_per_watt} ml/min/W`

## 5. Respuesta cardiovascular

### Compositor narrativo

* Párrafo 1: frecuencia cardiaca y presión arterial.
* Párrafo 2: pulso de oxígeno y parámetros manuales o interpretativos.

### Elementos

5.1. Frecuencia cardiaca
* Titulo: Frecuencia cardiaca
* Origen: CALCULADO
* Fuente: `gx_rest_hr_bpm`, `gx_vo2_max_hr_bpm`
* Unidad: lpm / lpm
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: FC en reposo {gx_rest_hr_bpm} lpm y máxima {gx_vo2_max_hr_bpm} lpm.
* Variantes parciales válidas:
  * `en reposo {gx_rest_hr_bpm} lpm`
  * `máxima {gx_vo2_max_hr_bpm} lpm`

5.2. Presión arterial
* Titulo: Presión arterial
* Origen: CALCULADO
* Fuente: `gx_rest_sysbp_mmhg`, `gx_rest_diabp_mmhg`, `gx_vo2_max_sysbp_mmhg`, `gx_vo2_max_diabp_mmhg`
* Unidad: mmHg / mmHg / mmHg / mmHg
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Presión arterial en reposo {gx_rest_sysbp_mmhg}/{gx_rest_diabp_mmhg} mmHg y máxima {gx_vo2_max_sysbp_mmhg}/{gx_vo2_max_diabp_mmhg} mmHg.
* Variantes parciales válidas:
  * `en reposo {gx_rest_sysbp_mmhg}/{gx_rest_diabp_mmhg} mmHg`
  * `máxima {gx_vo2_max_sysbp_mmhg}/{gx_vo2_max_diabp_mmhg} mmHg`

5.3. Pulso de oxígeno
* Titulo: Pulso de oxígeno
* Origen: CALCULADO
* Fuente: `gx_rest_vo2_per_hr_ml_per_beat`, `gx_vo2_max_vo2_per_hr_ml_per_beat`, `gx_predicted_vo2_per_hr_ml_per_beat`
* Unidad: ml/latido / ml/latido / ml/latido
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Pulso de oxígeno en reposo {gx_rest_vo2_per_hr_ml_per_beat} ml/latido; máximo {gx_vo2_max_vo2_per_hr_ml_per_beat} ml/latido; predicho {gx_predicted_vo2_per_hr_ml_per_beat} ml/latido.
* Variantes parciales válidas:
  * `en reposo {gx_rest_vo2_per_hr_ml_per_beat} ml/latido`
  * `máximo {gx_vo2_max_vo2_per_hr_ml_per_beat} ml/latido`
  * `predicho {gx_predicted_vo2_per_hr_ml_per_beat} ml/latido`

5.4. Recuperación
* Titulo: Recuperación
* Origen: MANUAL
* Fuente: 
* Unidad: 
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Recuperación: {cardio_recovery}.
* Variantes parciales válidas:
  * `Recuperación: {cardio_recovery}.`

5.5. ECG
* Titulo: ECG
* Origen: INTERPRETACIÓN
* Fuente: 
* Unidad: 
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: ECG: {cardio_ecg}.
* Variantes parciales válidas:
  * `ECG: {cardio_ecg}.`

5.6. Valoración clínica
* Titulo: Valoración clínica
* Origen: INTERPRETACIÓN
* Fuente: 
* Unidad: 
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Valoración clínica: {cardio_valuation}.
* Variantes parciales válidas:
  * `Valoración clínica: {cardio_valuation}.`

## 6. Respuesta ventilatoria

### Compositor narrativo

* Párrafo 1: VVM y ventilación minuto.
* Párrafo 2: VE/MVV y VT/CI.
* Párrafo 3: frecuencia respiratoria y SpO₂.

### Elementos

6.1. VVM
* Titulo: VVM
* Origen: CALCULADO
* Fuente: `pf_pre_mvv_l_per_min`
* Unidad: L/min
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: VVM pretest {pf_pre_mvv_l_per_min} L/min.
* Variantes parciales válidas:
  * `VVM pretest {pf_pre_mvv_l_per_min} L/min.`

6.2. Ventilación minuto
* Titulo: Ventilación minuto
* Origen: CALCULADO
* Fuente: `gx_rest_ve_btps_l_per_min`, `gx_vo2_max_ve_btps_l_per_min`
* Unidad: BTPS L/min / BTPS L/min
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: VE en reposo {gx_rest_ve_btps_l_per_min} BTPS L/min y máxima {gx_vo2_max_ve_btps_l_per_min} BTPS L/min.
* Variantes parciales válidas:
  * `en reposo {gx_rest_ve_btps_l_per_min} BTPS L/min`
  * `máxima {gx_vo2_max_ve_btps_l_per_min} BTPS L/min`

6.3. VE/MVV
* Titulo: VE/MVV
* Origen: CALCULADO
* Fuente: `gx_vo2_max_ve_per_mvv_pct`
* Unidad: %
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: VE/MVV máxima {gx_vo2_max_ve_per_mvv_pct} %.
* Variantes parciales válidas:
  * `VE/MVV máxima {gx_vo2_max_ve_per_mvv_pct} %.`

6.4. VT/CI
* Titulo: VT/CI
* Origen: CALCULADO
* Fuente: `gx_vo2_max_vt_per_ic_pct`
* Unidad: %
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: VT/CI máxima {gx_vo2_max_vt_per_ic_pct} %.
* Variantes parciales válidas:
  * `VT/CI máxima {gx_vo2_max_vt_per_ic_pct} %.`

6.5. Frecuencia respiratoria
* Titulo: Frecuencia respiratoria
* Origen: CALCULADO
* Fuente: `gx_rest_rr_br_per_min`, `gx_vo2_max_rr_br_per_min`
* Unidad: br/min / br/min
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Frecuencia respiratoria en reposo {gx_rest_rr_br_per_min} br/min y máxima {gx_vo2_max_rr_br_per_min} br/min.
* Variantes parciales válidas:
  * `en reposo {gx_rest_rr_br_per_min} br/min`
  * `máxima {gx_vo2_max_rr_br_per_min} br/min`

6.6. SpO₂
* Titulo: SpO₂
* Origen: CALCULADO
* Fuente: `gx_rest_spo2_pct`, `gx_vo2_max_spo2_pct`
* Unidad: % / %
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: SpO₂ en reposo {gx_rest_spo2_pct} % y máxima {gx_vo2_max_spo2_pct} %.
* Variantes parciales válidas:
  * `en reposo {gx_rest_spo2_pct} %`
  * `máxima {gx_vo2_max_spo2_pct} %`

## 7. Intercambio gaseoso

### Compositor narrativo

* Párrafo 1: VD/VT y PETCO₂.
* Párrafo 2: gases arteriales y umbral anaeróbico.

### Elementos

7.1. VD/VT
* Titulo: VD/VT
* Origen: CALCULADO
* Fuente: `gx_rest_vd_per_vt_meas`, `gx_vo2_max_vd_per_vt_meas`
* Unidad: 
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: VD/VT en reposo {gx_rest_vd_per_vt_meas} y máxima {gx_vo2_max_vd_per_vt_meas}.
* Variantes parciales válidas:
  * `en reposo {gx_rest_vd_per_vt_meas}`
  * `máxima {gx_vo2_max_vd_per_vt_meas}`

7.2. PETCO₂
* Titulo: PETCO₂
* Origen: CALCULADO
* Fuente: `gx_rest_petco2_mmhg`, `gx_vo2_max_petco2_mmhg`
* Unidad: mmHg / mmHg
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: PETCO₂ en reposo {gx_rest_petco2_mmhg} mmHg y máxima {gx_vo2_max_petco2_mmhg} mmHg.
* Variantes parciales válidas:
  * `en reposo {gx_rest_petco2_mmhg} mmHg`
  * `máxima {gx_vo2_max_petco2_mmhg} mmHg`

7.3. Gases arteriales
* Titulo: Gases arteriales
* Origen: MANUAL
* Fuente: 
* Unidad: 
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Gases arteriales: {arterial_gases}.
* Variantes parciales válidas:
  * `Gases arteriales: {arterial_gases}.`

7.4. Valoración clínica del umbral anaeróbico
* Titulo: Valoración clínica del umbral anaeróbico
* Origen: INTERPRETACIÓN
* Fuente: 
* Unidad: 
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: Valoración clínica del umbral anaeróbico: {anaerobic_threshold}.
* Variantes parciales válidas:
  * `Valoración clínica del umbral anaeróbico: {anaerobic_threshold}.`

## 8. Conclusiones

### Compositor narrativo

* Párrafo único de texto libre con los saltos de línea del usuario.

### Elementos

8.1. Conclusiones
* Titulo: Conclusiones
* Origen: MANUAL
* Fuente: 
* Unidad: 
* Requisitos mínimos: al menos una cláusula narrativa válida.
* Plantilla narrativa: 

## Elementos declarados como `PENDIENTE_DE_VALIDACIÓN` que no se muestran actualmente

> Nota histórica: esta terminología pertenece al diseño anterior. El modelo
> funcional vigente está definido en `docs/modelo_controles.md`.

* Ninguno declarado en la implementación inspeccionada.
