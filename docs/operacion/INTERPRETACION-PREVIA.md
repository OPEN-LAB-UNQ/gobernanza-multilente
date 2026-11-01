# Interpretación previa y confirmación del informe

Versión candidata de aplicación y motor: 0.10.3. Contrato HTTP: 0.4.1. La publicación exige la barrera completa sobre el commit exacto y la repetición de los 93 casos públicos fijados el 22/10.

La 0.10.3 separa también cuadros breves apilados sin períodos, como las cuatro tablas de carreras de posgrado en una hoja de una universidad. La 0.10.2 agrega una traza por cuadro que separa controles seleccionados, lentes efectivamente ejecutadas, módulos invocados y selecciones cuya ejecución todavía carece de traza propia. Cuenta relaciones acordadas y realmente controladas por separado. La interfaz muestra la traza y, por cada control seleccionado, antecedentes públicos de estructura y roles coincidentes incorporados con revisión humana al registro administrativo. Un cero es explícito; el número de antecedentes no es una probabilidad de acierto. No se incorporan automáticamente las respuestas a señales ni los 93 archivos de desarrollo como verdad de terreno.

El registro de calibración exige un grupo de fuente para casos revisados o reservados como validación externa ciega. Así, variantes del mismo informe no pueden cruzar entre desarrollo y evaluación aunque cambie su SHA-256. Esta barrera técnica no convierte por sí sola una campaña en ciega o representativa: hacen falta revisión independiente y nuevos informes. El banco todavía no contiene suficientes casos adjudicados para calibrar una tasa de acierto.

La versión 0.10.0 se midió durante la madrugada: 93 intentos, 77 análisis terminados, 5 pendientes de confirmación humana y 11 rechazos de carga. La auditoría de esos rechazos encontró ocho cuadros cuantitativos con encabezados apilados y tres archivos sin tabla numérica. Esa medición queda conservada como línea de base; las cifras de 0.10.1 sólo se registran al terminar su propia repetición.

En 0.10.1, la interpretación confirmada se ata a cada bloque y columna Excel. Las sumas inferidas excluyen roles de porcentaje e índice; las fórmulas extrapoladas exigen el mismo rol en origen y destino; y los controles de período respetan si el tiempo está en filas o columnas. Los cuadros que combinan años y meses se separan por frecuencia. El redondeo de totales sin rótulo usa los decimales publicados en el formato del libro, incluso en `.xls`. Los archivos sin tabla cuantitativa se informan como sin análisis numérico aplicable. Las respuestas inválidas de un proveedor reciben un reintento de esquema y, si persisten, se muestra el motivo sin convertirlas en votos.

## Requisito confirmado con el usuario

1. La IA interpreta primero el informe: institución, propósito y significado de cada cuadro.
2. Se muestra la interpretación antes de ejecutar controles: «Interpretamos que subiste un informe de presupuesto de una universidad. ¿Es correcto?».
3. La persona dispone de «Sí, analizar», «No, modificar» y «Reanalizar con más detalle».
4. Confirmar habilita los controles que correspondan. Modificar permite corregir institución, tipo y cuadros por separado. Reanalizar solicita una lectura más exhaustiva, y vuelve a pedir confirmación; no ejecuta controles.
5. Cada control dependiente del significado usa la interpretación confirmada de su cuadro. Sus condiciones matemáticas siguen siendo obligatorias.
6. Pantalla, resultados y PDF muestran la interpretación usada, su origen, los controles ejecutados y los pendientes.

No se confunde «universidad» con un régimen jurídico ni con un tipo de dato. Una universidad puede ser pública o privada y presentar presupuesto, matrícula, personal o varios temas en el mismo archivo.

## Hallazgos que motivan el cambio

La aplicación publicada ejecutaba controles durante la carga y después las lentes; el lector con IA agregaba relaciones más tarde. El dominio de la carga rápida se infería por palabras en encabezados. La lectura de la IA no dirigía esos controles anteriores.

Los lugares de integración son `routers/carga_rapida.py`, `services/analisis.py`, `services/lentes`, `services/controles_excel`, los controles de fórmulas y PDF, la cola, la interfaz y los reportes. Cambiar solamente el orden de una llamada no satisface el requisito.

## Contrato y límites

- Se prepara una representación saneada del documento y un inventario estable de cuadros. Preparar y contar cobertura es distinto de emitir hallazgos sustantivos.
- Los modelos reciben rótulos, títulos, notas y estructura, con cifras de datos enmascaradas. Los números como texto también se enmascaran. Las coordenadas y los conteos estructurales se distinguen de los valores del informe.
- Las respuestas tienen un esquema cerrado, referencias a fuentes existentes y validación determinística. El catálogo de controles lo define el programa; el texto de una IA nunca se ejecuta.
- La clasificación distingue institución, régimen, propósito y tipo de cada cuadro. Los roles de columnas y el eje temporal son locales: una fecha de pago no convierte un libro de pagos en una serie estadística.
- El consenso se calcula entre proveedores distintos. Una omisión, desacuerdo o respuesta inválida se declara y no se interpreta como aprobación.
- La confirmación humana queda vinculada al archivo exacto, su interpretación y la persona que confirma. Una modificación de datos o interpretación invalida la aprobación anterior.
- Las decisiones y las modificaciones conservan historial. No se sustituye en silencio lo que la IA propuso por lo que corrigió la persona.
- Sin confirmación no hay análisis determinístico sustantivo, tampoco por rutas alternativas, reintentos ni tareas en cola.
- «Reanalizar con más detalle» cambia realmente el alcance de lectura; no se limita a renombrar el mismo pedido ni reutiliza una respuesta anterior como si fuera nueva. Cada omisión por límite se declara.
- El modo detallado vuelve a la confirmación. Nunca confirma automáticamente una interpretación modificada.
- Los originales no se conservan como archivos permanentes. La integración de carga y confirmación debe preservar esta garantía, y no introducir almacenamiento bruto por comodidad.
- Una interpretación desconocida no se presenta como informe correcto. Los controles no ejecutados llevan su motivo.
- Completar el flujo no equivale a garantizar detección universal ni interpretación infalible.

## Barrera de aceptación

- Prueba de orden: no se llama a controles sustantivos antes de interpretar y confirmar.
- Prueba de aislamiento: dos cuadros del mismo archivo reciben políticas diferentes cuando sus contenidos difieren; un cuadro no desactiva controles de otro.
- Prueba causal: cambiar de forma válida la interpretación cambia la selección de controles, manteniendo los mismos datos.
- Prueba de confirmación: editar, reanalizar, cambiar de archivo, repetir una petición o usar un usuario diferente no permite reutilizar una aprobación inválida.
- Prueba de falla: proveedor caído, desacuerdo, respuesta inválida, lectura parcial y texto hostil no producen aprobación ni hallazgos inventados.
- Prueba de independencia: columnas con fechas operativas y columnas de importes se tratan según sus roles, no como una abstención temporal global.
- Prueba de regresión: siguen detectándose alteraciones aritméticas reales en cuadros confirmados, con controles correctos sin alarmas nuevas injustificadas.
- Prueba integral con archivo público: carga, interpretación real, confirmación, selección, ejecución, persistencia, pantalla y PDF sobre la misma versión.
- Suite completa del proyecto sobre el commit exacto antes de publicar; respaldo y comprobación posterior.
- No reprogramar la campaña como si validara este flujo hasta que el arnés ejercite también interpretación y confirmación, y no solamente el lector antiguo.

## Trazabilidad operativa

Base de trabajo: publicación 0.9.25.2. El desarrollo y los ensayos operativos usan código y base aislados. Los temporizadores de la campaña anterior fueron desactivados y su marca de pausa se conserva; no se reutilizan sus resultados como si evaluaran este flujo.

## API y recuperación

`POST /api/analisis-rapido` ahora devuelve `interpretando` y un trabajo de lectura. Se consulta `GET /api/interpretacion-previa/{id}` hasta `pendiente_confirmacion`. No se ejecutan controles durante esa espera.

Para confirmar se envían otra vez los mismos archivos y opciones, con `interpretacion_accion=confirmar`, `interpretacion_id`, `interpretacion_revision` e `interpretacion_correcciones` (JSON opcional por cuadro). La respuesta contiene el trabajo de análisis. `interpretacion_accion=detallada` crea una nueva revisión pendiente de confirmación. Un archivo, usuario, dato, opción o revisión diferentes invalidan la aprobación. Las huellas se calculan sobre los originales antes de convertir un Excel estricto.

La carga de datos estructurados utiliza `POST /api/informes/{id}/interpretacion` con `preparar`, `detallada` o `confirmar`. Las entradas de análisis y el worker exigen la misma confirmación. Una comparación atómica impide confirmar dos veces o que una relectura concurrente reemplace una decisión.

La lectura está en la cola persistente y se recupera tras reiniciar el servicio. Cerrar el navegador no detiene ese trabajo. Para confirmar archivos se requieren los originales: no se guardan sus bytes en el servidor.

## Evidencia y límites del ensayo operativo

Se recorrió HTTP, cola real, proveedores configurados, confirmación, análisis y PDF sobre una base PostgreSQL aislada. Archivo público: canasta de crianza de un instituto de estadística, SHA-256 `822a0d40aa5bcf81d41910c571b99097a971ac47a40d7a7843d6e213694aaa35`, 81 meses. La propuesta identificó una serie estadística con columnas de importes; no inventó una institución ni un régimen ausentes del material.

El original produjo dos señales temporales de prioridad media. Una copia con E20 aumentado en 100.000 produjo una diferencia localizada en E20, incluida una relación leída que no cierra. Los PDF ejecutivo, completo y comprobante se generaron. Es un ensayo acotado, no una medición de eficacia general. Las pruebas automatizadas usan proveedores simulados; la disponibilidad real se comprobó por separado.

La prueba real reveló dos defectos del contrato de evidencia: una referencia al título presente entre las notas se rechazaba, y citar más de ocho fuentes válidas invalidaba toda la respuesta. Se añadieron regresiones: las notas de la hoja son fuentes admitidas; todas las referencias se validan antes de conservar hasta ocho, registrando cuántas se recortaron. Una fuente inventada sigue invalidando la lectura, aunque aparezca después de la octava.

La lectura inicial presenta hasta 24 filas y cuatro finales; la detallada, hasta 300 y cuatro finales, con más notas. Los límites de texto pueden reducir el alcance. Se muestran los conteos efectivos en confirmación, resultados y PDF. Las cuentas recorren los datos disponibles, pero la lectura semántica no se declara exhaustiva ni se garantiza cubrir todos los formatos.

## Medición posterior

`scripts/medir_flujo_confirmado.py` ejecuta el mismo flujo HTTP y worker. Requiere una base con prefijo `gobernanza_medicion_`, una huella de código fijada y una carpeta de salida nueva. El lanzador operativo debe cotejar esa huella, el commit y los modelos con producción antes del inicio.

La confirmación del banco es **simulada**, sólo para propuestas conocidas con al menos dos lecturas válidas; si existe una etiqueta independiente de tipo, también debe coincidir. No valida la intervención humana ni responde las preguntas posteriores sobre relaciones. Los casos desconocidos quedan pendientes, no se cuentan como aprobados. Cada archivo conserva su huella y los resultados incluyen cobertura, hallazgos y PDF completo y anexo.

El límite es de 1.500 invocaciones a proveedores (lectura y comentarios) y siete horas de trabajo, con un corte operativo externo. La caché se limita a pedidos ciegos idénticos bajo el mismo código, proveedor y modelo, dentro de una corrida nueva. Los archivos no terminados se declaran. Las señales en archivos oficiales se informan como señales que requieren revisión; no se las llama falsas alarmas sin contrastarlas.

El arnés se ensayó con el original y la copia alterada: ambos recorridos terminaron, la celda alterada quedó localizada y no hubo fallos del proveedor en esas invocaciones. La medición amplia queda pendiente de su ejecución. Sus resultados no se mezclan con las campañas del lector anterior.
