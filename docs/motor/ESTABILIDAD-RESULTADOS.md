# Estabilidad y lectura de resultados — motor 0.8.18

## Detección preservada

El corpus las planillas de regresión (no publicadas) guarda el Excel aportado, SHA-256 y verdad terreno. La prueba exige seis hallazgos con hoja, celda y regla exactas y prioridad de revisión alta: una jurisdicción H36, una jurisdicción F33, una jurisdicción C35, una jurisdicción D17, una jurisdicción U5 y una jurisdicción K23. Los módulos de detección tabular no cambian en esta versión.

## Casos y señales

`services/casos_revision.py` agrupa sin eliminar ni mutar observaciones. Cada caso lleva `root_cause_id`, `primary_finding`, `related_findings`, criterio y prioridad. El ID usa identidades técnicas, no IDs de base ni orden de llegada. Una agrupación es una relación técnica inferida, no causalidad demostrada.

Se asocian encabezado duplicado y discontinuidad inmediata compatible; también conciliaciones del mismo período y hoja que comparten explícitamente un total y la magnitud de diferencia. Compartir solamente una celda o un año no basta. Se mantienen las señales originales y su severidad histórica.

El contador principal muestra casos. Se distinguen señales de control y variaciones de contexto expandidas: un registro persistido puede contener muchas variaciones. No se presenta la cantidad de registros agrupados como cantidad de errores.

## Prioridad de revisión

ALTA requiere ruptura estructural, tipo incompatible, signo aislado, conciliación de al menos 5%, corroboración independiente o factor de escala de al menos ocho. Picos que no cumplen esas condiciones quedan en MEDIA. El contexto temporal no compite con controles mecánicos. Es una prioridad para revisar, no una probabilidad de error. En reglas fuera de esta recalibración se conserva la clasificación existente.

## Contexto y PDF

El contexto se organiza por archivo, año, hoja y cuadro. La pantalla ofrece cinco referencias por grupo; el ejecutivo muestra cinco grupos iniciales y remite al anexo. La evidencia original permanece disponible.

En informes extensos o con casos agrupados, el PDF abre con una síntesis de doce casos prioritarios como máximo, cobertura, controles no aplicables, delta y próximos pasos. El anexo comienza en una página nueva. Las corridas pequeñas mantienen el comprobante compacto. La severidad histórica del detalle se distingue de la prioridad de revisión actual.

## Comparaciones

Las ejecuciones nuevas guardan una instantánea de señales y prioridad en su manifiesto. La base automática es la última ejecución compatible de la misma persona, área, dominio y nombres de origen (búsqueda acotada a cien ejecuciones); el mismo informe también puede servir como base. Sin base se informa expresamente, sin inventar continuidad.

La pantalla permite elegir un informe base por número. El endpoint exige permiso sobre ambos informes. El delta informa persistentes, nuevos, desaparecidos, cambios de prioridad y cambios de evidencia, junto con hashes y versiones de ambas corridas. Una fuente única renombrada conserva las identidades de sus señales; para múltiples fuentes no se presume correspondencia por orden.

En históricos sin instantánea se reconstruye sólo desde los hallazgos de la ejecución vigente y se conserva su severidad histórica. Si faltan hashes se informa como desconocido. Si cambiaron fuente y motor, el delta no atribuye causalidad por sí solo.

## Aplicabilidad

Radiólogo continúa fuera del dominio presupuestario calibrado cuando corresponde. Rizoma no aplica a cuadros anchos donde las columnas son años y las filas rubros heterogéneos: correlacionar columnas anuales sobre esos rubros no es la pregunta calibrada de esa lente. Los motivos se conservan al agregar cuadros y los controles no aplicables/no evaluables se muestran separados de los ejecutados.

## Modelos

Se exigen exactamente cuatro campos JSON: prioritarios (enteros no negativos y dentro del conjunto), lectura (texto), explicaciones_alternativas (textos) y confianza (baja/media/alta). Un error de estructura permite un único reintento, con instrucción explícita de reparación. Los errores de disponibilidad no provocan este reintento. Se registran intentos y errores de formato en el manifiesto.

Cada proveedor recibe copias independientes del contexto y de las señales. Su respuesta no puede modificar los controles determinísticos. Claude permanece suspendido. Validar y reintentar no garantiza que un proveedor externo responda correctamente.

## Correcciones del diagnóstico del 23/09/2026

La lectura de períodos acepta fechas serializadas y meses abreviados con notas al pie. Las etiquetas textuales de la fila total se preservan como dimensión. El corpus de deuda mensual verifica 92 conciliaciones y 91 variaciones: el máximo es 5,23194 % entre abril y mayo de 2024. Un objetivo no evaluado conserva ese estado aunque existan resultados de controles generales.

Benford excluye columnas genéricas e identificadores de usuarios; no sustituye la clasificación semántica de una columna ambigua.

La entrada a los modelos tiene un presupuesto explícito de evidencia y conserva los índices originales. Renderix utiliza JSON Schema y un presupuesto menor; Llama recibe también una entrada acotada. El manifiesto y la pantalla informan el alcance enviado. Los resultados completos de los controles permanecen disponibles.
