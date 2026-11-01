# OCR local — piloto 0.8.31

Acceso autenticado /api/ocr para administradores y analistas. Entrada JPG/PNG/PDF de hasta 15 MB; un PDF con texto entra hasta 60 páginas (índice de páginas, de a 10 por lectura, que la persona elige) y se leen con OCR hasta cinco páginas sin texto o imágenes por lectura, una lectura concurrente por proceso, Tesseract con límite de 25 segundos por página y presupuesto de 100 segundos entre páginas. Imágenes de hasta 24 millones de píxeles. Se corrige orientación EXIF y se limita la resolución de trabajo. Se utilizan español e inglés.

Dependencias: Tesseract y paquetes de idiomas spa/eng; en AlmaLinux `dnf install tesseract tesseract-langpack-spa tesseract-langpack-eng`. Pillow y pypdfium2 están fijados en requirements. No se invoca IA paga. Los archivos temporales se eliminan al terminar.

Texto digital del PDF (40 caracteres o más) se conserva. Las páginas sin texto suficiente pasan por OCR. Páginas fallidas y fuera del límite quedan explícitas. Un PDF que mezcla texto digital e imágenes con texto dentro de la misma página requiere revisión manual: no se fusionan ambas lecturas en este piloto.

La interfaz muestra imagen, coordenadas y palabras con confianza menor a 80; esto no garantiza exactitud del resto. El espacio visual sólo sugiere columnas; la persona corrige texto y tabulaciones, previsualiza, confirma y descarga un CSV por página. Se exige encabezado y filas rectangulares. Cualquier edición revoca la confirmación. No se recalculan ni se analizan automáticamente números OCR.

El JSON descargable conserva imagen, palabras, coordenadas, texto original/revisado, confirmaciones, cobertura y SHA256 del archivo. No es una certificación ni un registro firmado: la confirmación procede de la interfaz. La sesión no se guarda en base de datos. Conservar original y JSON junto al CSV; este último se carga luego en Multilente. El enlace visual al original aún no aparece en el PDF de hallazgos.

Límites pendientes de validar con documentos reales: tablas densas, celdas combinadas, fotos inclinadas, manuscritos y deterioro visual. No se infieren automáticamente relaciones entre tablas ni se convierten automáticamente comas/signos. Ante lectura deficiente corresponde corregir/repetir la captura.

## Revisión de lectura (0.9.7)

Desde 0.9.7 Multilente analiza directo sólo Excel y CSV: `/api/analisis-rapido` responde 422 con `detail = {"codigo": "requiere_revision_lectura", "archivos", "otros_archivos", "mensaje", "url": "/api/ocr"}` ante un PDF o una imagen (por extensión o por contenido), aunque venga junto con Excel/CSV; en ese caso no analiza nada. Esta herramienta es el paso previo:

- PDF con texto: la tabla sale del texto (grilla por coordenadas de palabras o líneas dibujadas, la que deja más celdas con un único número). OCR sólo para páginas sin texto e imágenes. Cada página dice cómo se leyó: «texto del PDF» u «OCR: revisá números y signos».
- Tabla editable al lado del original, con celdas dudosas resaltadas: períodos vacíos (celdas combinadas), números ambiguos («31,821», «1.054») si la tabla no decide el formato, columnas sin rótulo o repetidas, celdas con dos números y filas o columnas Total que no suman (sin contar dos veces los subtotales). Acciones: «Completar hacia abajo» (reparte un año centrado en su grupo de filas), formato numérico de la tabla, agregar o quitar filas y sumar filas de otra tabla con las mismas columnas.
- «Analizar esta tabla» envía «<documento> (revisado).csv» (UTF-8, `;`, coma decimal, sin punto de miles) con `origen_lectura=revision_pdf|revision_ocr` y `archivo_original`; el informe dice arriba «Tabla leída de <archivo> y revisada por una persona antes de analizar». Ningún dato se envía a proveedores de IA durante la lectura.
