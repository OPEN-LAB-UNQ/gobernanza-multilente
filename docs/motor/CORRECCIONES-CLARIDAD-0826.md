# Correcciones de claridad y recuperación — motor 0.8.26

- El porcentaje de series por período se identifica como cobertura temporal, sin
  equipararlo a la lectura total del archivo. Sin series aparentes se informa
  cobertura no calculable, tanto en pantalla como en el texto del reporte.
- La prueba de propuesta firme guarda el borrador y solicita revisar los diez
  criterios. La tutoría recibe el borrador completo guardado como material del
  usuario, sin depender del límite de 12000 caracteres de un mensaje de chat.
- La prueba informa avance, fallo o revisión recibida, incluyendo contador sin
  cambios. El contador continúa siendo orientativo; no certifica cumplimiento.
- Los mensajes y consultas conservan el texto hasta confirmar recepción. Si se
  escribió otro borrador durante la espera, la respuesta no lo borra.
- La entrega tiene confirmación persistente y el botón evita repetir la misma
  acción. Los borradores pueden seguir guardándose; se conserva el estado real.
- R-1 y Monitoreo aparecen plegados. Monitoreo conserva la restricción al ganador.
- El plan semántico divide anclas extensas en fragmentos sin descartarlas e incluye
  comparaciones entre los fragmentos de un bloque y entre bloques relacionados.
- Ante salida truncada se intenta subdividir el corpus de esa tarea, con hasta
  dos niveles de subdivisión y los mismos límites globales de llamadas y tiempo.
  No se repite a ciegas el mismo lote truncado. Los fallos quedan registrados.
- Una recuperación sólo cuenta como evaluada al completar todos los lotes nuevos
  y sus comparaciones transversales. Un elemento indivisible o un proveedor que
  siga fallando conserva el resultado incompleto; no se relajan las referencias.

Pruebas nuevas: mensajes fallidos y borradores concurrentes, envío de propuesta
larga íntegra a la tutoría, falta de denominador temporal, partición sin pérdida
comparativa y recuperación/budget de truncamiento. Proveedores simulados en pruebas;
no garantizan disponibilidad ni calidad de respuesta de todos los servicios reales.
