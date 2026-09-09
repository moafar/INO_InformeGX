# Generación y auditoría del PDF clínico

## Flujo

`POST /studies/versions/report.pdf` requiere sesión COORDINADORA, token CSRF y
una versión FIRMADA concreta. El servidor genera exclusivamente desde el
snapshot persistido de esa versión; no recibe contenido clínico del navegador.
Cada generación inserta un evento en `report_pdf_events`, vinculado a la versión,
con SHA-256, tamaño, usuario coordinador e instante.

Los narrativos se reconstruyen como texto plano en
`services/report_narratives.py`. El endpoint no recibe ni utiliza el
`innerHTML` generado en el navegador. `services/pdf_report.py` renderiza una
plantilla exclusiva mediante WeasyPrint y mantiene los bytes en memoria.

El orden transaccional es:

1. autenticación, CSRF y versión FIRMADA;
2. narrativos del servidor desde el snapshot;
3. bytes PDF definitivos en memoria;
4. SHA-256 y tamaño de esos bytes;
5. inserción transaccional del evento PDF;
6. respuesta de descarga con los mismos bytes.

Una excepción al insertar o confirmar el `report_pdf_event` ejecuta `rollback`; la
respuesta PDF no se construye ni se entrega.

El instante `generated_at` se determina una sola vez en UTC antes del renderizado.
El PDF muestra el perfil textual persistido del médico que firmó la versión, no
el de la coordinadora que lo genera.

## Presentación institucional

WeasyPrint selecciona dos elementos corridos independientes mediante CSS
paginado: `@page:first` usa el membrete ancho y las páginas restantes usan el
compacto con la identificación resumida. Ningún archivo se obtiene por red.

Los recursos opcionales se ubican en `static/report_assets/`:

| Uso | Archivo | Formato recomendado | Proporción | Reserva física A4 | PNG alternativo mínimo |
| --- | --- | --- | --- | --- | --- |
| Primera página | `membrete_ancho.svg` | SVG con `viewBox` | `178:22` | `178 × 22 mm` | `2103 × 260 px`, 300 ppp |
| Páginas 2+ | `membrete_compacto.svg` | SVG con `viewBox` | `178:10` | `178 × 10 mm` | `2103 × 118 px`, 300 ppp |

Las dos imágenes deben diseñarse y exportarse por separado. No se recorta ni se
reutiliza una para representar la otra. Si falta cualquiera de ellas, queda su
reserva en blanco y la generación continúa.

Al final del documento se incluye un bloque indivisible con espacio para firma
manuscrita y perfil textual. No se admite imagen de firma ni datos de firma en
el formulario clínico.

## Motor y despliegue

El motor fijado es `WeasyPrint==69.0`. Produce texto seleccionable, soporta A4,
CSS paginado y contadores de página, y funciona en Linux y WSL. No usa servicios
externos, navegador remoto ni recursos CDN.

En los destinos previstos Debian/Ubuntu y WSL se requieren Pango y HarfBuzz:

```bash
sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0
pip install -r requirements.txt
python -m weasyprint --info
```

Si se incorpora otro sistema operativo o imagen base, debe verificarse primero
contra las dependencias nativas indicadas por la versión fijada de WeasyPrint.

## Migraciones reproducibles

`migrations/004_drafts_roles_versions.sql` crea la base persistente;
`migrations/005_workflow_states_pdf_events.sql` añade estados, ownership médico,
auditoría y eventos PDF; `migrations/006_add_vdvt_persistence.sql` conserva las
alternativas VD/VT y su fuente seleccionada. Las migraciones son un paso
explícito de despliegue y se ejecutan con
`ALLOW_APP_MIGRATIONS=1 python -m migrations` contra `APP_DATABASE_URL`; nunca
tocan la conexión clínica ni `staging.gx_analytics`.

Como backfill conservador, la migración 005 marca los borradores existentes como
`PRELIMINAR_BLOQUEADO`: su historial de intervención médica anterior no puede
inferirse de forma segura, por lo que no recuperan edición auxiliar automáticamente.
