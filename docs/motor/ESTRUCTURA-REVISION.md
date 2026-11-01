# Revisión estructural 0.8.74

El resultado principal se descarga como Informe de revisión; el detalle técnico es opcional. Las rutas históricas siguen disponibles. La cobertura insuficiente se presenta antes de interpretar la ausencia de casos; las asociaciones exploratorias no se cuentan como inconsistencias.

Las series Excel conservan concepto, título de ámbito explícito, unidad, período y coordenadas. Las relaciones entre padres e hijos requieren conciliación en varios períodos. Sólo se agrupan referencias equivalentes cuando los otros componentes son cero y la identidad se cumple en todos los períodos comparables. Las fichas se generan para nuevas cargas; no se reescriben ejecuciones históricas.

La materialidad necesita un total comparable de la misma unidad y cuadro. Para evitar que una caída a cero parezca irrelevante, se toma el mayor entre la participación del valor observado y la del desvío respecto al promedio de sus vecinos. Este desvío es orientativo, no un error confirmado. Los patrones inferiores al 0,1 % y los extremos unilaterales quedan en MEDIA salvo corroboración independiente. La materialidad desconocida permanece explícita.

Las tablas PDF con encabezados no fiables o columnas sin separar se excluyen antes de aplicar controles numéricos; se conservan las tablas legibles. Las correlaciones entre partes de una composición cerrada no se presentan como anomalías. PDF: 150 páginas por defecto, máximo configurable de 300; Excel conserva la lectura de todas las hojas. Otros límites de carga y cobertura siguen vigentes y se informan.

La IA usa un modelo principal y respaldo cuando el principal no ofrece un resultado completo; la comparación explícita conserva los proveedores elegidos. El procesamiento semántico usa lotes acotados y comparaciones transversales. Se conservan las hipótesis válidas de un lote mixto, sin atribuir cobertura completa a ese lote. Se mantiene el rechazo estricto de campos adicionales del proveedor.

Validación: regresiones de desplazamiento, escala, identidad estructural, falsos positivos por composición, cobertura PDF, materialidad ante caída a casi cero, descarga autenticada y conservación de hipótesis válidas. La prueba previa del modo predeterminado se actualiza porque el contrato pasa de dos consultas simultáneas a principal con respaldo; se agregan controles de respaldo y comparación explícita. No se cambian las expectativas sobre errores reales de los fixtures existentes.
