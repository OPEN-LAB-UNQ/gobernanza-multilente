# Controles tabulares reproducibles — versión 1

Se ejecutan al cargar Excel y recuperan del original códigos como NA que la conversión tabular puede convertir en vacíos, pero sólo sobre las filas y columnas conservadas por el saneamiento. No dependen de nombres de archivos, hojas, indicadores del benchmark ni coordenadas conocidas.

## Reglas

- Series con al menos cuatro números y 75% de cobertura numérica: vacío interior con vecinos presentes, texto no convertible y signo negativo único rodeado de positivos. Una fórmula sin caché no se interpreta como un dato eliminado.
- Años no enteros, duplicados, fuera de orden o con discontinuidad cuando la secuencia aporta evidencia de periodicidad anual. Un encabezado inválido impide usar el tramo ambiguo; no bloquea ventanas de tres años únicos y consecutivos en otras posiciones. Las conciliaciones alinean por año inequívoco, no por posición, y excluyen ambas apariciones de un duplicado.
- Puntos interiores: razones con ambos vecinos, interpolación, mediana/MAD y residuo logarítmico para series positivas. El pico requiere apartarse de ambos vecinos, recuperación de escala y vecinos comparables. Umbral fuerte: al menos factor 3 frente a cada vecino y factor 5 respecto de la interpolación. No se modifican los umbrales de Cronista.
- Extremos: extrapolación local con dos períodos contiguos; se declara expresamente que falta confirmación bilateral. Un candidato moderado sólo se comunica si también rompe una conciliación independiente.
- Conciliaciones por jerarquía de sangría/espacios, totales y subtotales; se suman componentes inmediatos, evitando contar padres e hijos a la vez. Relaciones entre cuadros: mismo indicador y unidad en la misma hoja, o total/indicador repetido. Exigen al menos cuatro períodos concordantes y 80% de concordancia; con dos o tres períodos, la misma relación (mismos rótulos, origen y unidad) tiene que cerrar en todos sus períodos en al menos otras tres hojas o cuadros del archivo, sin otra que falle el mismo período; son relaciones inferidas que deben validarse con el área. Tolerancia: 0,05 unidades más 0,1% de la mayor magnitud comparada. No se infieren relaciones universales entre cualquier par de hojas.

## Prioridad y consolidación

Puntaje acumulativo, no porcentaje de certeza: estructura 120; ruptura aritmética material 110; picos/extremos según razón relativa; conciliación independiente aporta 20 puntos. Una discrepancia menor de conciliación obtiene 55. El importe absoluto no incrementa la prioridad. Las magnitudes monetarias sólo se utilizan dentro de su propia relación aritmética.

Las conciliaciones que corroboran una celda ya señalada se incorporan a su evidencia. No se presentan como otra alarma. La evidencia distingue declarado, reconstruido, diferencias, tolerancias, componentes y acción de revisión. Un pico interior comunica una única celda con ambos vecinos.

Las variaciones generales se agrupan por archivo y año **para la lectura**; esta agrupación no establece comparabilidad económica entre las hojas. Se conserva cada señal original con descripción y evidencia. La pantalla muestra 20 resultados y permite desplegar el resto. Ambos PDF separan controles prioritarios y detalle contextual. Se mantienen las declaraciones de alcance previas.

## Corpus y pruebas

- las planillas de regresión (no publicadas): original, variante alterada, hashes y verdad terreno con los 12 cambios. Las coordenadas están en la verdad terreno, no en las reglas ni en las aserciones de los tests.
- El mismo benchmark se ejecuta con nombres de hojas sustituidos y todos los datos desplazados tres filas y dos columnas.
- Casos sintéticos en orientaciones horizontal y vertical, códigos de ausencia, años, jerarquías, redondeos, formatos numéricos, fórmulas sin caché, exclusión de datos personales, contextos compartidos y prioridades independientes del importe absoluto.
- Flujo HTTP → cola → motor → persistencia JSONB simulada → reporte y comprobante PDF.
- Se mantienen los casos del libro por provincia y los ocho pares públicos. El libro ahora debe detectar los nuevos controles estructurales; la prueba sigue rechazando las viejas falsas alertas de fórmulas y exige conservar sus 197 variaciones originales.

Ejecutar `venv/bin/python scripts/verificar_calidad.py` antes de publicar. El empaquetador también ejecuta las nuevas regresiones y conserva ambos corpus.

## Límites medidos

El benchmark del libro de gasto recupera los 12 cambios deliberados. Esto no certifica que todos los demás hallazgos sean errores: el archivo original también contiene patrones y discrepancias que requieren revisión. En el libro por provincia una diferencia en el último período se localiza por conciliación, sin aislar inequívocamente el componente erróneo. No se bajan umbrales para atribuirle una certeza que la evidencia no permite.

Las relaciones no corroboradas, fórmulas sin resultados cacheados y estructuras que no pudieron interpretarse requieren revisión o preparación de la fuente. Los controles son ayuda para revisar, no prueba de la causa de una diferencia ni certificación de veracidad.

## Regresión del comprobante 194

El comprobante 194 fue emitido con el motor 0.7.3. En 0.8.0 ya se detectaban seis controles; aún se bloqueaba todo el cuadro por un año duplicado. En 0.8.1 se revisan ventanas locales inequívocas y las conciliaciones se alinean por año válido. No se reconstruye ni se adivina el año corrupto.

El corpus las planillas de regresión (no publicadas) conserva el archivo aportado y un original extraído, con valores cacheados y estilos, de la hoja correspondiente del libro de gasto original. La comparación celda por celda confirma los siete cambios. La verdad terreno distingue seis localizaciones directas y una ruptura de total con el componente alterado entre sus participantes; no se presenta esta última como atribución exclusiva.

Se comprueban carga, saneamiento, cola, persistencia con claves reordenadas, lentes, priorización y ambos PDF. También se repite con nombres de hojas y posiciones cambiados. El original no genera observaciones de estos controles. La suite mantiene los benchmarks completos de los dos libros por provincia y los ocho pares previos.
