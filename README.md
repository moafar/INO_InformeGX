# INO_InformeGX

Aplicación Flask para informes de ergoespirometría con workflow persistente,
versiones firmadas y PDF bajo demanda.

## Flujo

El flujo es `AUXILIAR → MÉDICO → COORDINADORA`. Los estados son
`PRELIMINAR`, `EN_FIRMA`, `PRELIMINAR_BLOQUEADO` y `FIRMADO`. AUXILIAR puede
editar sus 14 campos MANUAL solo en PRELIMINAR. Un MÉDICO toma una versión para
pasarla a EN_FIRMA; solo su propietario puede editarla, liberarla o firmarla.
Una liberación o expiración funcional de 30 días deja la versión en
PRELIMINAR_BLOQUEADO, disponible para que otro médico la tome, nunca para AUXILIAR.

Firmar guarda una versión inmutable y no genera PDF ni crea automáticamente v2.
Un MÉDICO puede crear v2+ desde la última FIRMADA; nace EN_FIRMA con una copia
completa de valores y ownership del creador. COORDINADORA genera el PDF en
memoria desde una versión FIRMADA, usando el perfil persistido del médico firmante.
Cada descarga se registra con SHA-256 y tamaño, sin almacenar el archivo.

La fuente clínica `staging.gx_analytics` es solo lectura. La aplicación no copia
la tabla clínica: conserva una identidad técnica propia y un selector GX validado.

## Configuración

Variables necesarias:

```text
APP_ENV=development|testing|production
SECRET_KEY=...
APP_DATABASE_URL=postgresql://...
CLINICAL_DATABASE_URL=postgresql://...
SESSION_COOKIE_SECURE=true|false
```

`APP_DATABASE_URL` es lectura/escritura para usuarios, borradores, bloqueos y
versiones. `CLINICAL_DATABASE_URL` se abre con transacciones de solo lectura.

## Migraciones

Las migraciones son reproducibles, se ejecutan explícitamente antes de arrancar
una versión nueva y requieren confirmación contra la base de aplicación:

```bash
ALLOW_APP_MIGRATIONS=1 python -m migrations
```

No ejecutar migraciones contra la base clínica.

## Desarrollo

```bash
pip install -r requirements.txt
python -m flask --app app:create_app run
```

## Docker

`compose.yaml` crea los servicios `web` y `postgres`. Web ejecuta Gunicorn;
PostgreSQL usa el volumen `app_postgres_data` y no expone 5432. Ejecute el paso
de migración explícito antes de iniciar una versión nueva. El puerto web queda
en `127.0.0.1:8000` para un reverse proxy del VPS.

No incluya secretos en el repositorio; suminístrelos mediante entorno del host.

## Verificación

```bash
python -m unittest discover -s tests
node tests/draft_editor_js_test.js
```

La clasificación exacta de los 93 controles, roles y permisos se documenta en
`docs/modelo_controles.md`.
