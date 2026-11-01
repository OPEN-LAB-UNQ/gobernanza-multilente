# Ficha para «Código para el Desarrollo» (BID)

Borrador con los mismos campos que la ficha publicada del
[Asistente IA para Consultas Académicas](https://knowledge.iadb.org/es/conocimiento-abierto/codigo-para-el-desarrollo/solucion-de-codigo-abierto/asistente-ia-para-consultas-academicas).

## Título

Gobernanza Multilente

## Datos

| Campo | Valor |
|---|---|
| Idioma | Python |
| Tipo de herramienta | Aplicación web |
| Licencia | The MIT License |
| Versión | 0.10.65 |
| Responsable | OPEN LAB · Universidad Nacional de Quilmes |
| Repositorio | https://github.com/OPEN-LAB-UNQ/gobernanza-multilente *(a confirmar al crearlo)* |

## ¿Qué es?

Gobernanza Multilente es una aplicación web desarrollada en Python (FastAPI y PostgreSQL) que hace una
segunda lectura de informes con datos agregados —presupuestos y su ejecución, estados contables,
tableros de indicadores y metas— antes de decidir con ellos. Lee planillas Excel, CSV y PDF, y aplica
a cada cuadro los mismos controles reproducibles, organizados en seis lentes analíticas (ajedrecista,
matemático, cronista, orquesta, radiólogo y rizoma) y una capa conciliadora que revisa si una señal
tiene una explicación técnica antes de escalarla. No da veredictos: devuelve preguntas con su evidencia,
en lenguaje llano, para que quien decide se las haga al área que armó el informe. Cada informe empieza
por lo que no pudo leer o revisar y queda un comprobante de qué se controló. La inteligencia artificial
propone cómo leer cada cuadro y lee las señales, pero no calcula ni decide: «la IA propone, las reglas
comprueban, la persona decide». La revisión rápida, que es la que se usa por defecto, no usa IA. Incluye
Gobernanza Incubadora, un entorno en el que cada persona formula un proyecto de aplicación responsable
de IA para un problema de su área, acompañada por una IA que hace preguntas en lugar de dar respuestas
cerradas. Se desarrolló en OPEN LAB, proyecto de extensión de la Universidad Nacional de Quilmes, y se
usó en una capacitación para agentes de la Administración Pública Nacional (Argentina): al 31/10/2026,
52 participantes cargaron 151 informes y formularon 74 proyectos.

## ¿Qué problemas resuelve?

Quien decide casi nunca tiene tiempo de revisar a fondo los informes que recibe, y controlarlos hacia
atrás, insumo por insumo, es inviable. Un total que no cierra, un valor cargado en otra escala, una
fórmula que cambió de criterio sin aviso o una serie con un quiebre pueden pasar inadvertidos y llegar a
una decisión. Gobernanza Multilente sistematiza esa segunda lectura: aplica los mismos controles a todos
los cuadros, sin depender del cansancio ni del apuro de quien revisa, y convierte cada hallazgo en una
pregunta concreta para el área responsable. Así prepara mejor la conversación con la auditoría o el área
técnica, sin reemplazarlas.

## ¿Cómo funciona la herramienta?

**Carga y lectura.** Se carga el informe (Excel o CSV) y se elige el ámbito (organismo público u
organización) y la revisión: rápida, sólo con las cuentas y sin IA, o profunda, en la que modelos de IA
proponen cómo interpretar cada cuadro sin ver las cifras y una persona lo confirma. Los PDF y las imágenes pasan antes por una revisión de lectura: se ve el original al lado
de la tabla leída, se corrige lo necesario y se confirma. La lectura se hace en el propio servidor, y
una salvaguarda compara las cifras del original con las que efectivamente se analizan, declarando
cualquier pérdida.

**Controles por lentes.** Reglas programadas y reproducibles revisan totales y componentes, escalas,
signos, períodos, unidades, fórmulas y relaciones entre magnitudes, cada una desde una lente: lo que no
puede pasar (ajedrecista), lo que cambió en el tiempo (cronista), lo que debería acompañarse
(orquesta), cómo se calculó (matemático), qué dicen los antecedentes (radiólogo) y qué conexiones
explorar (rizoma). La capa conciliadora ajusta la prioridad cuando una señal se explica por cómo se
publicó o armó el dato.

**Informe y decisión humana.** El informe empieza por lo que no se pudo leer o controlar y sigue con las
consultas para el área, cada una con qué pasó, qué preguntar, la evidencia y dónde está. En la revisión
profunda, la IA lee las señales y ayuda a formularlas, contrastada con la evidencia. La decisión y la firma
quedan siempre en manos de una persona, y queda registrado qué se controló y con qué versión.

## Estándares abiertos

- HTTP/HTTPS (IETF RFC 9110 / RFC 2818) → comunicación cliente-servidor
- REST → diseño de la API
- JSON (ECMA-404 / RFC 8259) → intercambio de datos
- SQL (ISO/IEC 9075) → base de datos PostgreSQL
- Office Open XML (ECMA-376 / ISO/IEC 29500) → lectura de planillas Excel (.xlsx)
- CSV (RFC 4180) → lectura de datos tabulares
- PDF (ISO 32000) → lectura de documentos con texto
- UTF-8 (RFC 3629) → codificación de caracteres
- TLS (IETF RFC 8446) → cifrado de las comunicaciones

## Sector

Gobierno y gestión pública / Finanzas públicas / Ciencia y Tecnología

## Características

Análisis y visualización de recopilación de datos / Inteligencia artificial / Transparencia y rendición de cuentas

## Objetivos de desarrollo sostenible

Paz, justicia e instituciones sólidas (ODS 16) / Industria, innovación e infraestructura (ODS 9)

## Recursos

| Recurso | Descripción | Enlace |
|---|---|---|
| Ejemplos sin clave | Ocho pares de informes de ejemplo (uno sin señal y otro con señal) que cualquiera puede abrir. | https://gobernanza.entornodepruebas.com.ar/probar.html |
| Presentación | Qué es, cómo funciona, criterio de uso y preguntas frecuentes. | https://gobernanza.entornodepruebas.com.ar/presentacion |
| Ficha técnica | Arquitectura, criterios de uso y resultados de cada medición independiente. | https://gobernanza.entornodepruebas.com.ar/detalle |
| Charla | Charla relámpago en el Encuentro Nacional de Tecnología Cívica (Guadalajara, 15/10/2026). | https://gobernanza.entornodepruebas.com.ar/multilente |

## Capturas

Archivos en [`docs/capturas/`](capturas/):

1. `portada.png` — «Una segunda lectura antes de decidir».
2. `ejemplos.png` — informes de ejemplo que se pueden probar sin clave.
3. `informe.png` — «El 7 es el mismo. La fórmula, no.»: lo que devolvió la herramienta sobre una
   planilla en la que una celda pasó de promedio ponderado a simple sin cambiar el resultado.
4. `ficha.png` — criterios de uso y resultados de cada medición.
