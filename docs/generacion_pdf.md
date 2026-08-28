# Generación y auditoría del PDF clínico

## Flujo

`POST /studies/report.pdf` requiere sesión y el token CSRF del formulario. El
servidor valida los controles, vuelve a recuperar un único estudio mediante
`(patient_id_num, visit_datetime)` y aplica la precedencia ya usada por el
borrador: el valor enviado prevalece en esta petición, tanto para campos
manuales como para correcciones explícitas GX; si un GX no se envía, se usa el
valor directo o derivado del registro exacto de `staging.gx_analytics`.

Los narrativos se reconstruyen como texto plano en
`services/report_narratives.py`. El endpoint no recibe ni utiliza el
`innerHTML` generado en el navegador. `services/pdf_report.py` renderiza una
plantilla exclusiva mediante WeasyPrint y mantiene los bytes en memoria.

El orden transaccional es:

1. autenticación, CSRF, formulario e identidad exacta;
2. narrativos del servidor;
3. bytes PDF definitivos;
4. SHA-256 y tamaño de esos bytes;
5. inserción y `commit` de la auditoría;
6. respuesta de descarga con los mismos bytes.

Una excepción al insertar o confirmar la auditoría ejecuta `rollback`; la
respuesta PDF no se construye ni se entrega.

El instante `generated_at` se determina una sola vez en UTC antes del
renderizado. Ese mismo objeto se usa para el pie del PDF, convertido mediante
`America/Bogota`, y para la fila de auditoría; el hash se sigue calculando sobre
los bytes definitivos ya renderizados.

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

## Migración manual

`migrations/002_create_report_pdf_audits.sql` se aplica únicamente a la base de
autenticación. Crea `ergo_app.report_pdf_audits` con el estudio, el identificador
y nombre del usuario autenticado, instante de generación, nombre, hash y tamaño.
Incluye índices por estudio, usuario y hash; el hash no es único.

La migración no toca la conexión clínica ni `staging.gx_analytics`, y nunca se
ejecuta al arrancar la aplicación.

`migrations/003_create_user_signature_profiles.sql` crea en la misma base
`ergo_app.user_signature_profiles`, una fila opcional por usuario con nombre de
firma, profesión o especialidad, registro profesional y línea institucional.
El repositorio la carga con el usuario autenticado y la sesión firmada conserva
una copia acotada para el PDF. Sin fila se usa `users.full_name` como único dato
de respaldo.
