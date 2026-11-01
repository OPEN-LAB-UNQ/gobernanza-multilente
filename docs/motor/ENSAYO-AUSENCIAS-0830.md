# Calibración de ausencias y fórmulas — 0.8.30

42 casos, siete familias y tres semillas, con versiones base/alterada. Se verifican reglas y celdas exactas, además de prohibiciones explícitas de falsas alarmas:

- Vacío interior: aviso en la celda correspondiente.
- Vacío extremo: no fingir vecinos a ambos lados ni convertirlo en cero al conciliar.
- Cero: mantiene su valor numérico y permite detectar la diferencia aritmética.
- Texto s/d: cambio de tipo comunicado, sin convertirlo en cero.
- Fórmulas coherentes sin caché: no se consideran datos borrados.
- Fórmula desplazada: se identifica la celda fuera del patrón.
- Año duplicado: se identifica el encabezado y se excluyen ambas columnas ambiguas de conciliación.

Los 42 casos pasan sin modificar el motor. Las versiones base no generan hallazgos. Se incorporan a la batería completa y al control obligatorio Excel. El ensayo comprueba controles y evidencia, no la redacción del PDF ni la evaluación de resultados de fórmulas sin caché. No llama IA ni recalcula fórmulas con Excel.
