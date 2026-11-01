# Cobertura y diagnóstico de IA — 0.8.22

## Diagnóstico del #220

En 0.8.21, el inventario tenía 1052 elementos, 173 bloques y 1917 relaciones.
El empaquetado sólo enviaba 81 elementos y 15 bloques a GPT, Gemini y DeepSeek.
El contexto repetía etiquetas, nombres de archivos, hojas y aristas del grafo.

Los errores conservados eran validaciones de evidencia (citas idénticas o sin
celda), esquema incompleto y JSON no reconocible. El registro histórico carecía
de tiempos, estados HTTP, salida y tokens, por lo que no permitía distinguir
truncamientos de salida y otros errores del proveedor. No se reconstruyen esos
campos por suposición: se explicita que no fueron registrados.

## Cambios

- Diccionarios sin pérdida de textos, hojas, roles, coordenadas y referencias.
  Adyacencia compacta de todas las relaciones. El inventario real del #220 cabe
  íntegro en 55783 bytes, frente a más de 500 KB de representación original.
- Interpretación numérica y exploración semántica son peticiones independientes:
  cada una conserva su presupuesto y su resultado. Un fallo exploratorio no
  borra la interpretación determinística ni viceversa.
- Estrategia global hasta 60000 bytes para GPT/Gemini/DeepSeek, y límites menores
  por proveedor. Si no cabe, todos los bloques se recorren en lotes con anclas;
  luego una segunda pasada compara todas las relaciones entre hojas. Las parejas
  de fragmentos cruzan también las fronteras de los lotes.
- Se considera evaluada cuando al menos una estrategia completa TODOS sus lotes
  y su comparación transversal con salida válida. Sólo enviar el corpus o
  terminar la etapa local no basta. Los hallazgos siguen siendo exploratorios.
- Recursos acotados por estrategia: 24 intentos y 240 segundos comprobados entre
  lotes. El lote en curso puede exceder ese tiempo hasta agotar sus dos intentos
  y los respectivos timeouts.
  Alcanzar un límite deja tareas pendientes y estado no completado, nunca éxito.
- En los corpus globales grandes, el presupuesto de salida de los proveedores
  que lo configuran sube a 8192 tokens para evitar truncamientos conocidos.

## Registro por modelo e intento

El manifiesto conserva `status`, `error_type`, `http_status`, `latency`,
`input_tokens`, `input_elements`, `output_received`, `parse_status`,
`discard_reason` y todos los intentos en `llamadas`. Cada intento añade fase,
lote, tokens de salida, motivo de finalización, longitud y SHA256 de la salida,
fragmento redactado de hasta 2000 caracteres y señal de truncamiento del registro.
Los tokens desconocidos se guardan nulos; no se confunden con cero ni se estiman.
Las claves y cabeceras de autenticación no se conservan.

Tipos separados: timeout, HTTP, autenticación, límite de tasa, red, configuración,
JSON inválido, esquema inválido, referencias inválidas, salida vacía y límite de
tokens. Un truncamiento informado por el proveedor prevalece sobre el error de
JSON que pueda ocasionar. Los límites del plan son fallos de cobertura.

Se distinguen elementos enviados de elementos con salida válida. La pantalla y
los PDF dicen «Exploración no completada» y muestran causas. En los históricos
esa presentación se calcula sin alterar el registro original. No se inventa
telemetría que no existía.

## Alcance del corpus

Se cubre el inventario saneado almacenado, no contenido ausente de él. Omisiones
de extracción, formatos no soportados y límites de relaciones permanecen en
`exclusiones_corpus`. Cubrir ese corpus no garantiza que la IA encuentre todos
los problemas ni que sus hallazgos sean correctos. Requiere revisión humana.
