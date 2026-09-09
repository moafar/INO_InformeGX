# AGENTS.md

## Propósito y flujo vigente

INO_InformeGX es una aplicación Flask para redactar informes de ergoespirometría
con el flujo persistente `AUXILIAR → MÉDICO → COORDINADORA`:

1. Login.
2. Búsqueda exacta de un estudio GX.
3. AUXILIAR diligencia los controles MANUAL asignados en `PRELIMINAR`.
4. MÉDICO toma, revisa, libera o firma una versión persistente.
5. COORDINADORA genera a demanda el PDF de una versión `FIRMADO`.

Firmar cierra una versión inmutable; no genera PDF ni crea una versión nueva.
El PDF se genera en memoria y se audita por evento, sin almacenamiento permanente.

## Fuente clínica y seguridad

La fuente vigente es `Patient Query → patient_query_automate → PostgreSQL
staging.gx_analytics`. Es estrictamente de solo lectura.

- Nunca modificar `patient_query_automate`, ETL o `staging.gx_analytics`.
- Nunca consultar Breeze/SQL Server interno ni decodificar `GXTestRawData`.
- Nunca escribir datos de aplicación en la base clínica.
- No introducir fórmulas, umbrales o interpretaciones clínicas no aprobadas.
- Usar exclusivamente datos sintéticos en pruebas, ejemplos, logs y documentación.
- No versionar secretos, credenciales, certificados, tokens ni claves.

## Modelo de controles

La fuente funcional única de los 93 controles es `services/study_report.py`; la
clasificación aprobada está en `services/report_controls.py`:

- `DIRECTO`: 46 controles.
- `CALCULADO`: 8 controles.
- `MANUAL`: 16 controles.
- `INTERPRETACIÓN`: 23 controles.

`EDITADO` es una condición, no un tipo, y solo aplica a DIRECTO/CALCULADO.
Conserva valor original y vigente. No usar categorías formales AUSENTE,
PENDIENTE_DE_VALIDACIÓN o INCONSISTENTE.

`services/report_draft.py` es legado. No crear funcionalidad ni dependencias de
runtime sobre él.

## Roles y permisos

- Estados persistentes: `PRELIMINAR`, `EN_FIRMA`, `PRELIMINAR_BLOQUEADO`,
  `FIRMADO`.
- `AUXILIAR`: solo puede editar sus 14 MANUAL asignados en `PRELIMINAR`.
- `MEDICO`: toma `PRELIMINAR` o `PRELIMINAR_BLOQUEADO`; solo el propietario de
  `EN_FIRMA` puede editar, liberar o firmar. Puede crear v2+ desde la última
  versión firmada.
- `COORDINADORA`: solo busca, selecciona versiones firmadas y genera/descarga PDF.
- `EN_FIRMA` liberado o expirado pasa a `PRELIMINAR_BLOQUEADO`, nunca a
  `PRELIMINAR`.

La autorización siempre se valida en backend.

## Persistencia y bloqueo

La aplicación usa `APP_DATABASE_URL` (lectura/escritura) y
`CLINICAL_DATABASE_URL` (solo lectura), ambas PostgreSQL.

- Un único borrador activo por estudio app; las versiones firmadas son inmutables.
- Estado funcional, ownership médico e infraestructura de concurrencia son
  conceptos separados. El ownership dura 30 días desde la toma y no se renueva
  con actividad; al expirar, pasa a `PRELIMINAR_BLOQUEADO` y se audita.
- Autosave: 15 segundos; Guardar ahora persiste con revisión optimista.
- Logout solo limpia locks técnicos heredados; no cambia estado ni ownership.
- Cada versión firmada conserva snapshot completo, identidad técnica, perfil
  textual del médico firmante y auditoría del workflow. Cada generación PDF
  crea un evento con SHA-256 y tamaño, sin guardar los bytes.

La identidad técnica del estudio se mantiene separada de los campos visibles y
editables del informe. La selección GX se rechaza si el datasource devuelve más
de un estudio para el mismo selector actual.

## Arquitectura

- Entrada/configuración: `app.py`, `config.py`, `db.py`.
- Datasource GX: `services/gx_data_source.py` (`GXPostgresDataSource` actual;
  preparado para `GXApiDataSource`).
- Borradores/versiones: `services/draft_workflow.py`, `repositories/drafts.py`.
- Informe: `services/study_report.py`, `services/report_narratives.py`.
- PDF: `services/pdf_report.py` con WeasyPrint.
- Migraciones reproducibles y explícitas: `ALLOW_APP_MIGRATIONS=1 python -m migrations`.

## Despliegue y verificación

`compose.yaml` prepara `web` (Gunicorn) y `postgres` con volumen persistente;
PostgreSQL no publica el puerto 5432.

Verificar siempre:

```bash
python -m unittest discover -s tests
node tests/draft_editor_js_test.js
git diff --check
```
