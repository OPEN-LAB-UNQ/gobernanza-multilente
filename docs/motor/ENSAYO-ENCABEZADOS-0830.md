# Calibración 0.8.30

30 casos de Excel (cinco familias, tres semillas, versiones correctas/alteradas) y cuatro pruebas específicas de encabezados. Se cubren unidades homogéneas, porcentajes y escalas distintas, períodos inversos y totales repetidos en bloques con períodos en orden distinto.

La comparación entre bloques ya encontraba la diferencia: el evaluador inicial exigía que la celda alterada fuera la referencia principal, cuando correctamente figuraba entre ambas celdas participantes. El evaluador ahora exige las dos ubicaciones, período e importe exactos.

Se reprodujo una falsa alarma real: los encabezados estrictamente decrecientes provocaban avisos anios_no_crecientes. Ahora se admite el orden decreciente y se infiere paso anual -1. Se mantienen los avisos por duplicación, salto anual y orden mezclado. No se cambian las ventanas de cálculo temporal ni sus fórmulas.

Estas pruebas sintéticas verifican conciliación y encabezados; no garantizan toda la interpretación semántica de unidades ni toda serie temporal posible. No llaman proveedores IA.
