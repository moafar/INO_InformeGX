# Membretes del informe PDF

Este directorio admite dos recursos independientes y opcionales. La ausencia de
cualquiera de ellos conserva su espacio en blanco y no impide generar el PDF.

* `membrete_ancho.svg`: exclusivo de la primera página, proporción `178:22`.
* `membrete_compacto.svg`: exclusivo de las páginas posteriores, proporción `178:10`.

El formato recomendado es SVG con `viewBox` proporcional y sin dimensiones
dependientes de recursos externos. No se reutiliza ni recorta un membrete para
reemplazar al otro. Para una alternativa raster PNG con transparencia, prepara
archivos distintos a 300 ppp como mínimo: `2103 × 260 px` para el ancho y
`2103 × 118 px` para el compacto.
