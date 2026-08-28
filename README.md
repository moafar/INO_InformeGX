# Ergo App

Aplicación Flask para autenticación, búsqueda exacta de estudios y borrador clínico efímero.

## Estado actual

- Backend conservado: autenticación, búsqueda exacta por `patient_id_num`, selección por fecha y hora, y borrador editable sin persistencia.
- Formulario clínico integrado: diseño Jinja aprobado con 87 controles, trazabilidad GX/MANUAL, seis secciones, narrativos inmediatos y vista de informe imprimible.
- Descarga PDF en memoria con auditoría transaccional en la base de autenticación; el PDF no se persiste.

## Puesta en marcha

1. Exporta `APP_ENV`, `SECRET_KEY`, `AUTH_DATABASE_URL` y `CLINICAL_DATABASE_URL`.
2. En Debian/Ubuntu (también dentro de WSL), instala las bibliotecas nativas de WeasyPrint:

   ```bash
   sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0
   ```

3. Instala dependencias con `pip install -r requirements.txt` y comprueba el motor con `python -m weasyprint --info`.
4. Aplica manualmente `migrations/001_create_ergo_app_users.sql`, `migrations/002_create_report_pdf_audits.sql` y `migrations/003_create_user_signature_profiles.sql` en la base de autenticación. La aplicación no ejecuta migraciones.

## Ejecución

```bash
export APP_ENV=development
python -m flask --app app:create_app run
```

## Flujo V1

1. Iniciar sesión.
2. Buscar por `patient_id_num` exacto.
3. Seleccionar un estudio.
4. Editar el borrador efímero.
5. Confirmar `Generar PDF` para descargar y auditar el informe visible.

La selección clínica usa la clave única `(patient_id_num, visit_datetime)`. Los
campos GX se preparan en `services/study_report.py`; los campos manuales y las
correcciones explícitas de GX solo sobreviven al envío actual del formulario y
no se persisten.

La generación usa `POST /studies/report.pdf`, vuelve a validar la identidad
exacta del estudio y reconstruye los seis narrativos en el servidor. El PDF se
entrega solo después de confirmar su fila de auditoría. Consulta
`docs/generacion_pdf.md` para el detalle operativo.

## Verificación

Para incluir la inspección de contenido y geometría PDF instala las dependencias
de desarrollo con `pip install -r requirements-dev.txt`.

```bash
python -m unittest discover -s tests
node tests/draft_editor_js_test.js
```
