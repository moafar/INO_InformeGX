# AGENTS.md

## Propósito del repositorio

- Aplicación web Flask para autenticación, búsqueda exacta de estudios y elaboración de borradores clínicos editables.
- Estado actual del desarrollo:
  - `auth` con persistencia de cuentas.
  - Búsqueda exacta por `patient_id_num`.
  - Selección de un estudio por fecha y hora.
  - Borrador efímero en memoria, editable desde la interfaz.
  - Sin persistencia de borradores, informes clínicos ni PDF.

## Principios de trabajo

- Mantener el alcance de la V1: autenticación -> búsqueda exacta -> selección -> borrador completamente editable y efímero.
- No introducir persistencia de datos clínicos, borradores, informes o PDF salvo que una tarea lo pida explícitamente.
- No considerar definitivas fórmulas, puntuaciones o interpretaciones clínicas pendientes de validación.
- Distinguir siempre entre `DIRECTO`, `CALCULADO`, `MANUAL`, `INTERPRETACIÓN`, `AUSENTE`, `PENDIENTE_DE_VALIDACIÓN` e `INCONSISTENTE`.
- Si un dato no existe o no es fiable, dejarlo como ausente o pendiente de validación en lugar de inferirlo.
- No usar tablas internas de Breeze o SQL Server ni decodificar `GXTestRawData`.
- Tratar la fuente clínica como de solo lectura; no crear, restaurar, poblar ni modificar `staging.gx_analytics`.
- Usar datos sintéticos en pruebas, ejemplos y logs. No versionar volcados, datos clínicos reales, identificadores, secretos ni credenciales.

## Configuración y entorno

- La configuración se resuelve por variables de entorno.
- Variables relevantes:
  - `APP_ENV`
  - `SECRET_KEY`
  - `AUTH_DATABASE_URL`
  - `CLINICAL_DATABASE_URL`
  - `SESSION_COOKIE_SECURE`
- En desarrollo y pruebas pueden existir valores por defecto locales; en producción deben llegar por entorno.
- La base clínica debe tratarse como lectura solamente.

## Arquitectura actual

- Entrada principal: `app.py`.
- Configuración: `config.py`.
- Conexiones de base de datos: `db.py`.
- Rutas:
  - `routes/auth.py`
  - `routes/home.py`
  - `routes/studies.py`
  - `routes/errors.py`
- Servicios:
  - `services/auth.py`
  - `services/search.py`
  - `services/draft.py`
  - `services/report_draft.py`
  - `services/csrf.py`
  - `services/passwords.py`
  - `services/names.py`
- Repositorios:
  - `repositories/users.py`
  - `repositories/studies.py`
- Interfaz:
  - `templates/`
  - `static/`
- Especificación de estructura del informe: `docs/estructura_informe.md`.

## Flujo funcional vigente

1. Inicio de sesión.
2. Búsqueda exacta por `patient_id_num`.
3. Selección del estudio identificado por fecha y hora.
4. Apertura del borrador editable.

## Reglas de implementación

- No asumir campos, secciones o métricas que no estén ya representados en el modelo o en la vista.
- Al ampliar el informe, mantener la separación entre dato fuente, transformación y redacción narrativa.
- Si una regla clínica requiere validación, documentarla como tal y no codificarla como verdad definitiva.
- Cualquier cambio en búsqueda, mapeo clínico o narrativa debe ir acompañado de pruebas.
- Si se toca el editor frontend, validar también el comportamiento del script en `tests/draft_editor_js_test.js`.

## Verificación

- Pruebas Python:
  - `python -m unittest discover -s tests`
- Si se modifica lógica de cliente:
  - `node tests/draft_editor_js_test.js`

## Comunicación

- Responder de forma concisa con:
  - resultado,
  - archivos modificados,
  - verificaciones ejecutadas,
  - bloqueadores si los hubiera.
