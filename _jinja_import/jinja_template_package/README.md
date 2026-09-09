# Artefacto histórico de importación

> Este paquete corresponde a un demo anterior y no participa en el runtime de
> INO_InformeGX. Sus plantillas, rutas de ejemplo y conteos de controles no
> definen el workflow vigente. La referencia actual es
> `templates/study_draft.html`, con 93 controles definidos en
> `services/study_report.py`, persistencia propia y permisos de backend.

# Plantilla Jinja — informe de ergoespirometría

Paquete obtenido del demo aprobado. Incluye 87 controles, trazabilidad GX/MANUAL, resúmenes narrativos por sección, informe clínico consolidado, vista de impresión y actualización inmediata en el navegador.

## Archivos

- `templates/study_report_form.html`: plantilla Jinja autónoma.
- `static/study_report.css`: diseño adaptable e impresión.
- `static/study_report.js`: sincronización de campos, narrativos, informe y controles de interfaz.

## Integración en Flask

Copie `study_report_form.html` al directorio `templates` de la aplicación y los dos archivos estáticos al directorio `static`.

La plantilla acepta estos datos:

- `study`: diccionario del registro de `staging.gx_analytics`, enriquecido con los valores GX derivados.
- `form_values`: borrador previamente guardado. Sus valores tienen prioridad sobre `study`.
- `form_action`: URL que recibirá el formulario por `POST`.
- `page_title`, `app_name` y `current_user_name`: textos opcionales.

Ejemplo:

```python
from flask import render_template, request, url_for


def report_form(row, draft=None):
    study = dict(row)
    study.update(build_derived_values(study))

    return render_template(
        "study_report_form.html",
        study=study,
        form_values=draft or {},
        form_action=url_for("reports.save", visit_id=row["load_id"]),
        app_name="Ergo App",
        current_user_name="Usuario",
    )
```

## Valores GX derivados

El navegador no recalcula variables clínicas. El backend debe entregar estos identificadores dentro de `study` cuando correspondan:

| Identificador del formulario | Columnas de origen |
|---|---|
| `porc_fc_maxima` | `gx_vo2_max_hr_bpm`, `gx_predicted_hr_bpm` |
| `medicion_gases` | `gx_rest_ph`, `gx_vo2_max_ph` |
| `porc_o2_predicho` | `gx_vo2_max_vo2_ml_per_min`, `gx_predicted_vo2_ml_per_min` |
| `porc_vo2_predicho` | `gx_vo2_max_vo2_ml_per_min`, `gx_predicted_vo2_ml_per_min` |
| `carga_max_w` | `gx_vo2_max_work_watts`, `gx_predicted_work_watts` |
| `porc_pred_o2_latido_6` | `gx_vo2_max_vo2_per_hr_ml_per_beat`, `gx_predicted_vo2_per_hr_ml_per_beat` |
| `reserva_respiratoria_pico_l` | `pf_pre_mvv_l_per_min`, `gx_vo2_max_ve_btps_l_per_min` |

Los elementos repetidos en distintas secciones usan un único campo de base de datos mediante `source_id`; por ejemplo, las variantes visuales de VO₂ relativo y frecuencia respiratoria máxima.

## Guardado

Todos los controles tienen `id` y `name` coincidentes. Los campos manuales se reciben con el mismo nombre mostrado en el HTML. El checkbox `medicion_gases` se envía como `true` cuando está marcado y no se incluye en el `POST` cuando está desmarcado.

```python
manual_values = request.form.to_dict()
manual_values["medicion_gases"] = bool(request.form.get("medicion_gases"))
```

Antes de persistir, aplique en el backend las validaciones clínicas y de tipo correspondientes. Los valores introducidos por el usuario se escapan antes de incorporarlos al narrativo dinámico.

## Ajustes habituales

- Si la aplicación usa un `base.html`, conserve el contenido de `<main>` dentro de su bloque principal y mantenga las referencias a CSS y JavaScript.
- Si los archivos estáticos pertenecen a un blueprint, cambie `url_for('static', ...)` por el endpoint estático del blueprint.
- Para generar PDF, renderice la misma vista y use los estilos `@media print` incluidos.
