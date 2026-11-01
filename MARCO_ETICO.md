# Marco ético

Gobernanza Multilente asiste a quien decide; no decide. Este marco establece cómo se diseña y cómo
debe usarse.

## La salida de la IA nunca se entrega cruda

Todo lo que produce pasa por cuatro verbos humanos antes de salir: **se revisa, se corrige, se contrasta
y se asume**.

- **La IA es insumo, nunca producto.** Entrega un borrador, una señal de dónde mirar y qué preguntarse;
  nunca un resultado terminado. No existe «lo hizo la IA»: siempre hay una persona que analiza, decide
  y firma.
- **La IA correlaciona; la persona comprende.** Gobernar es intervenir sobre causas. Lo que sólo
  correlaciona puede optimizar; no puede gobernar.
- **El sistema no aprende: se calibra.** Las personas ajustan sus reglas a partir de casos revisados. Eso
  es calibración, no aprendizaje de la máquina; el criterio sigue siendo humano.
- **Se usa cuando se justifica.** Frente a cada problema se evalúa si conviene resolverlo con IA o por
  otra vía, y se trata como un recurso, no como un juguete.

## Principios de diseño

| Principio | Cómo se lleva a la práctica |
|---|---|
| Trazabilidad | Cada revisión registra qué se analizó, bajo qué criterios, con qué versión y qué se encontró. |
| Supervisión humana | El sistema señala y pregunta; la interpretación y la decisión quedan en manos de personas, y se registran. |
| Transparencia | Cada observación muestra la evidencia que la sostiene. |
| Gestión de riesgos | Si faltan datos, contexto o evidencia, el sistema lo declara en lugar de forzar una conclusión. |
| Responsabilidad | Se automatizan verificaciones y controles, no decisiones. |

Estos principios aparecen, entre otros marcos, en la Carta Iberoamericana de Inteligencia Artificial en
la Administración Pública (CLAD) y en las recomendaciones de la OCDE y la UNESCO sobre IA. Gobernanza
Multilente no se presenta como certificación ni cumplimiento de ellos: propone mecanismos concretos para
llevarlos a la práctica y poder contrastar cómo se aplicaron.

## Prohibiciones y límites de uso

- **No cargar datos personales ni información sensible.** La herramienta trabaja con datos agregados
  (presupuestos y su ejecución, estados contables, tableros de indicadores y metas), no con expedientes
  ni personas identificables.
- **No usarla para buscar culpables.** No es una herramienta antifraude ni de auditoría forense y no
  atribuye responsabilidades. Cada señal llega como pregunta, no como acusación.
- **No usarla como certificación.** No reemplaza auditorías, controles internos ni asesoramiento
  jurídico, y no certifica que un informe sea verdadero o esté libre de errores. Lo no evaluado no
  equivale a un control superado, y que no aparezcan señales no significa que el informe esté bien.
- **No delegar la decisión.** Una decisión de la que nadie se hace responsable no es gobierno.

## Datos y proveedores

- Las comprobaciones las hacen reglas programadas que dan el mismo resultado con las mismas entradas.
- Cuando se usa un modelo de lenguaje, no recibe el archivo original: recibe las señales y su evidencia,
  que pueden incluir valores del informe. Sin claves de proveedores, los controles y el comprobante
  funcionan igual.
- La lectura de PDF e imágenes se hace en el propio servidor; esos datos no se envían a proveedores de IA.

## Honestidad sobre sus límites

La herramienta publica sus criterios para considerarse usable y se mide contra ellos con archivos nuevos.
Los resultados se publican también cuando son desfavorables ([`evaluacion/`](evaluacion/)). Una
herramienta que promete encontrarlo todo invita a dejar de mirar: preferimos una que encuentre una parte
de los problemas y diga hasta dónde llegó.
