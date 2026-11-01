# Orden temporal — 0.8.35

La validación de encabezados ya aceptaba años descendentes, pero las ventanas de anomalías locales exigían paso +1. Esto ocultaba picos y escalas extremas al invertir un cuadro. Se reproduce en 12 casos de tres semillas, ambas orientaciones y anomalías interiores/extremas.

Se admite paso -1 uniforme además de +1, conservando exclusión de duplicados, períodos no enteros, saltos y cambios de dirección. No se reordenan datos ni se cambian coordenadas. Las fórmulas de comparación local y sus umbrales permanecen.

48 casos pareados verifican datos correctos y alterados (×10), orden ascendente/descendente, años en filas/columnas. Se exigen regla, período y celda exactos. Cuatro controles adicionales rechazan ventanas ambiguas o discontinuas. Integrados en la batería obligatoria de Excel. Casos sintéticos, no garantía universal de detección.
