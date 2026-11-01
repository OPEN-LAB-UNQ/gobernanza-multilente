# Aprendizajes del proyecto Gobernanza Multilente

Nota viva de criterios, falsos positivos, decisiones metodológicas y ajustes reutilizables.

Última actualización sugerida: 2026-08-24

## 1. Propósito

Esta nota no es un historial de ejecuciones ni una transcripción de conversaciones. Su función es conservar criterios aplicables a futuros casos para mejorar Gobernanza Multilente: criterios de lectura, límites, reglas calibradas y falsos positivos convertidos en filtro y decisiones metodológicas defendibles.

Gobernanza Multilente es una segunda lectura de información agregada para asistir a una persona responsable de decisión. No reemplaza criterio experto, auditoría formal, órganos de control, procedimientos administrativos ni decisión humana.

Su valor está en ordenar preguntas razonables, trazables y proporcionadas.

## 2. Principios no negociables

### Doble capa de análisis

Gobernanza no aplica todo del mismo modo. Primero ejecuta controles globales que corresponden siempre: legibilidad, estructura, totales, campos críticos, consistencia básica y trazabilidad.

Después activa lentes específicas solo cuando el archivo ofrece evidencia suficiente. Si una lente no corresponde, debe registrarse como no aplicable y no inventar una lectura.

El modo estándar trabaja solo con información agregada.

La unidad de análisis puede ser una categoría institucional, período, rubro, programa, jurisdicción, área, indicador, serie, cuenta, métrica consolidada o control interno.

Queda fuera del modo estándar cualquier dato cuya unidad de lectura sea persona, proveedor, contratista, adjudicatario, beneficiario, cliente, expediente, factura, comprobante, CUIT/CUIL/DNI, correo, teléfono, nombre, razón social o caso individual.

Si una fuente trae actores nominales o registros de detalle, primero debe convertirse a una vista agregada y descartar identificadores. Esos campos no deben aparecer en reportes, rankings, comparaciones, hallazgos comunicables ni preguntas sugeridas.

### Neutralidad institucional

El sistema excluye por completo:

- acusaciones;
- atribución de intención, culpa o responsabilidad personal;
- evaluaciones de mérito, oportunidad o conveniencia política;
- conclusiones de legalidad o ilegalidad;
- rankings de actores nominales;
- interpretaciones partidarias, ideológicas o electorales.

Debe preferir:

- "conviene pedir contexto";
- "requiere conciliación";
- "la evidencia no alcanza para concluir";
- "queda como pregunta para la persona responsable";
- "requiere validación por el área competente";
- "no reemplaza auditoría formal ni decisión humana".

### No inventar utilidad

Un resultado sin señales comunicables también es un resultado válido. La herramienta no debe producir hallazgos solo para demostrar actividad.

## 3. Flujo institucional del sistema

1. Carga y contextualización.
2. Saneamiento de alcance agregado.
3. Lectura por lentes.
4. Hallazgo estructurado con evidencia.
5. Pregunta institucional.
6. Revisión y triangulación.
7. Decisión humana.
8. Enrutamiento, cierre o seguimiento.
9. Aprendizaje curado.

La interfaz debe ir de lo general a lo particular: primero orienta; después permite abrir evidencia, modelos, límites y reporte descargable.

## 4. Criterios por lente

### Conciliador

Busca si una señal puede explicarse por carga, acumulado, reclasificación, corte de período, cobertura parcial, publicación o mezcla de niveles de agregación.

Criterio: una señal técnica no debe escalarse sin preguntar antes por su contexto de producción.

Regla de comunicación: si hay explicación plausible de carga o clasificación, bajar severidad o convertir la señal en pedido de contexto.

### Ajedrecista

Busca restricciones duras, configuraciones imposibles, controles internos y relaciones que no deberían romperse.

Criterio: una regla formal debe tener fundamento visible: regla, fuente, alcance, definición y estado de validación.

Regla de comunicación: si falta fundamento normativo o contable explícito, no comunicar como violación categórica; comunicar como validación de regla aplicable.

### Cronista

Busca saltos temporales, cambios de régimen y períodos bisagra.

Criterio: importa ubicar cuándo cambia la serie y si ese cambio coincide con corte, carga tardía, reclasificación o cambio de criterio.

Regla de calibración: evitar que Cronista opaque otras lentes cuando el salto temporal es solo efecto instrumental de una prueba o de una oscilación esperable del cuadro.

### Orquesta

Busca coherencia conjunta entre magnitudes agregadas relacionadas.

Criterio: las variables pueden moverse juntas por relaciones estructurales, derivadas o mecánicas. Una ruptura no prueba causa, pero puede justificar una pregunta.

Regla de comunicación: formular como coherencia operativa o físico-financiera a validar, no como medición directa de eficiencia, responsabilidad o incumplimiento.

### Radiólogo

Compara contra antecedentes, históricos o bancos comparables.

Criterio: la comparación solo sirve si el banco es comparable.

Regla de comunicación: si la base histórica no alcanza o no es comparable, comunicar límite de cobertura antes que conclusión.

### Rizoma

Explora asociaciones no previstas sin afirmar causalidad.

Criterio: debe filtrar relaciones obvias, derivadas, mecánicas, temporales o producto de extracción tabular.

Regla de comunicación: su salida correcta es una hipótesis para revisar, no una explicación causal.

### Matemático

Pregunta si el método de cálculo corresponde al tipo de decisión.

Criterio: una fórmula puede estar bien escrita y aun así responder mal la pregunta institucional.

Regla de seguridad: no ejecutar código libre generado por IA sobre archivos cargados. Usar un catálogo de planes de cálculo explícitos, programados, testeados y trazables.

## 5. Reglas técnicas aprendidas

- La detección de fórmulas de Excel debe ser un control opcional, separado de Matemático.
- El sistema debe detectar patrones aritméticos implícitos cuando la estructura del dato lo justifica.
- Los controles internos declarados por el archivo deben leerse como evidencia trazable.
- La evidencia debe nombrar hoja, fila, columna, período, serie o encabezado cuando sea posible.
- Los encabezados rotos, columnas fragmentarias y restos de extracción no deben convertirse en asociaciones exploratorias.
- En PDF hay que distinguir extracción tabular de lectura de texto por página.
- Cuando un PDF se recorta por límite de páginas, el reporte debe mostrar páginas analizadas, páginas totales y límite aplicado.
- No toda magnitud negativa es imposible: puede ser variación, diferencia, saldo o reclasificación.
- No toda correlación fuerte es hallazgo: las relaciones derivadas deben filtrarse antes de comunicar.
- En informes de IPC u otros PDFs tabulares, las correlaciones perfectas entre columnas regionales pueden reflejar estructura de cuadro o extracción, no una asociación institucional comunicable.
- En cuadros Excel con períodos como columnas, Rizoma debe silenciar correlaciones entre trimestres, fechas o columnas de unidad de medida.
- En Exceles públicos con títulos superiores y encabezados en varias filas, el lector debe preferir filas tabulares densas con unidades, períodos o variaciones antes que títulos sueltos.

## 6. Criterios de reporte

El reporte debe:

- empezar por síntesis ejecutiva;
- formular una pregunta inicial que oriente la decisión sin acusar;
- permitir elegir qué hallazgos entran al reporte;
- dejar el detalle de modelos disponible bajo demanda;
- mostrar cobertura: lentes ejecutadas, filas analizadas, columnas excluidas, límite PDF y estado del barrido;
- explicar alcance y límites cuando no hay señales;
- distinguir evidencia estructurada de interpretación de modelos.

## 7. Triangulación

La triangulación no es votación ni consenso automático.

Cada modelo interpreta los mismos hallazgos. El sistema conserva coincidencias, divergencias y lecturas singulares.

La coincidencia entre modelos aumenta prioridad de revisión, pero no convierte una señal en certeza.

Las respuestas de modelos deben validarse con esquema estricto. Si un modelo devuelve JSON incompleto, ambiguo o fuera de forma, queda como error o degradación y no contamina la interpretación.

El punto a gobernar no es solo la afirmación final, sino también la evidencia seleccionada, la contraevidencia buscada y las alternativas mostradas.

## 8. Aprendizaje validado

El aprendizaje no modifica automáticamente las reglas del sistema.

Una respuesta institucional, falso positivo o señal explicada puede originar una propuesta de calibración, pero debe quedar validada por una persona responsable antes de incorporarse.

Cada aprendizaje incorporado debe registrar:

- criterio que cambia;
- motivo del cambio;
- problema que reduce;
- límite que conserva;
- forma de revertir si genera ruido.

## 9. Registro sugerido de cada aprendizaje

Usar este formato para nuevos aprendizajes:

```text
Fecha:
Origen:
Lente afectada:
Problema observado:
Falso positivo o riesgo:
Criterio nuevo:
Cambio técnico sugerido:
Impacto esperado:
Límite conservado:
Estado: propuesto / validado / implementado / descartado
```

## 10. Pendientes vivos

- Fortalecer reglas de coherencia por dominio sin endurecerlas como verdades universales.
- Mejorar bancos comparables para Radiólogo.
- Refinar lectura tabular de PDF.
- Mejorar filtros de relaciones mecánicas en Rizoma.
- Hacer visible cuándo una lente detectó algo pero no entró en el reporte final.
- Mantener esta nota como memoria curada, no como historial operativo.
