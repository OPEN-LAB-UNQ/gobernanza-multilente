# Calibración de límites — 0.8.29

60 casos con tres semillas y pares correctos/alterados. Se cubren tres, cuatro y cinco períodos, componentes ausentes, diferencias negativas, totales negativos, compensaciones y redondeos absolutos y relativos.

En 0.8.28 las tres alteraciones de series con componentes no nulos que se compensan no se detectaban: los períodos cuyo total era cero se descartaban. Ahora esos períodos contribuyen a corroborar la relación cuando algún componente supera la tolerancia absoluta. Tablas de ceros o importes insignificantes siguen sin corroborarla. Dos regresiones adicionales protegen ese límite.

Se conservan las reglas de materialidad y mínimo de períodos. De las 30 alteraciones, 24 deben detectarse; seis con sólo tres períodos comparables están fuera del alcance de inferencia actual y no se cuentan como detecciones. Las 30 versiones correctas no deben producir falsas conciliaciones. Estos ensayos no evalúan el estado comunicado en PDF para relaciones no corroboradas.

Sin llamadas a IA. Casos sintéticos, no estimación de precisión sobre cualquier Excel real.
