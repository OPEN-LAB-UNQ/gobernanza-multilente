> README técnico del proyecto, conservado tal cual. Sus rutas son relativas a la raíz del repositorio.

# Gobernanza Multilente

Aplicación **v0.10.62**; documento principal **v9.3**, publicado en Zenodo el 25/10/2026
(DOI de la versión [10.5281/zenodo.23649172](https://doi.org/10.5281/zenodo.23649172);
DOI de la serie [10.5281/zenodo.22063241](https://doi.org/10.5281/zenodo.22063241)); motor
**multilente-0.10.61**; API **0.4.3**; protocolos **B-1 v1.2** y **R-1 v1.1**.

Gobernanza Multilente lleva los principios de gobernanza a algo que se puede
comprobar: una segunda lectura de informes con datos agregados antes de decidir.
Sirve a organismos públicos y a organizaciones (empresas, cooperativas, ONG,
universidades): al cargar se elige el ámbito, que define qué reglas se aplican
(`services/ambito.py`; por defecto, organismo público). La franja «Uso registrado»
de la presentación se calcula en vivo (`services/uso_publico.py`). Los cambios de
cada versión del motor están en `HISTORIA.md`. El documento v7
describe la aplicación 0.9.6 con el motor multilente-0.9.4 y anticipa la etiqueta de cohorte de
Conexiones, que llega en la 0.9.7; los cambios posteriores (hasta la versión vigente, en `versiones.py`) están en
`HISTORIA.md` y se incorporarán en la próxima edición. El documento v7 es la edición
depositada en Zenodo (DOI 10.5281/zenodo.23329097); las versiones anteriores se consultan allí y los
informes de revisión fechados quedan en `docs/documento/` y `docs/revision-070/`. El Word no se
distribuye desde la aplicación.
Las correcciones de evidencia, reportes y pares de ejemplos se detallan en
`docs/historico-07x/revision_ocho_casos.md`.
La descarga conjunta incorporada en 0.7.1 sigue documentada en
`docs/historico-07x/ejemplos_zip.md`. Los protocolos institucionales mantienen sus versiones;
las correcciones no reescriben informes históricos ni equivalen a validación empírica.

Corte histórico de referencia: **v0.7.0**, código
`ad9e4f00874ed3e2a2930a214b77f7b8b5153bf1` (17/09/2026).
Revisión de consistencia documental: 18/09/2026. Protocolos institucionales
vigentes: **B-1 v1.2** y **R-1 v1.1**. Las versiones anteriores se conservan
solo para interpretar evaluaciones históricas.

La publicación posterior, autorizada por el usuario, está documentada en
`docs/revision-070/PUBLICACION.md`. El informe de auditoría y su Word conservan
el alcance de la revisión previa, que no había modificado producción.

Lectura multilente para la gobernanza de información agregada en la conducción
institucional, asistida por IA. Implementa seis lentes y una capa conciliadora
sobre información agregada, triangulación configurable entre los proveedores de IA
habilitados (cinco en el selector de la interfaz), devolución en lenguaje llano y un comprobante automático que registra
los controles efectivamente aplicados. El comprobante no exige una validación
manual de las operaciones del motor y no equivale a aprobación, auditoría ni
certificación del contenido del informe.

El Conciliador corre al final por su función contextual, pero no ocupa una
jerarquía superior ni inferior a las otras seis lentes. Revisa el conjunto de
hallazgos y, cuando puede explicar una señal
por un artefacto técnico que encuentra en el archivo (crédito vigente cero con
ejecución, reversas mensuales, retrocesos acumulados, ratios ejecución/crédito
extremos o notas de cobertura), le baja la severidad y le adjunta contexto en
`limites.contexto_tecnico` en vez de duplicarla como advertencia aparte. De una
nota de cobertura en una columna de notas, observaciones o personas no copia el
texto a la evidencia (que puede llegar al prompt de los modelos), sólo dónde está
(«nota de cobertura en la fila N»); de otras columnas la copia saneada. Sin
ese artefacto no modula nada: una imposibilidad presupuestaria conserva su
severidad aunque mencione devengado o crédito, y en el ámbito «organización»
no usa el vocabulario del presupuesto público para emparejar señales. Ver
`services/lentes/__init__.py` y `services/lentes/conciliador.py`.

No es una herramienta de auditoría, forense ni de atribución de
responsabilidades. La autoridad conserva la decisión institucional sobre qué
hacer con la información; esa decisión queda fuera del comprobante de
controles automáticos.

## Protocolos

- **Comprobante de controles automáticos aplicados — Gobernanza Multilente:**
  se genera a partir de la revisión ya ejecutada, identifica la versión del
  motor, la huella del objeto, los controles aplicados, las observaciones
  mecánicas y las señales exploratorias. No incorpora aprobación humana. El
  protocolo B-1 v1.2 es una revisión institucional opcional separada y fuera
  del recorrido habitual. La institución puede abrirla por acceso directo cuando
  su normativa exige esa instancia. Conserva once controles, evidencia, revisión
  humana explícita y separación entre evaluación y emisión. Abrirla no
  equivale a revisar sus controles ni transforma el comprobante en un sello.
- **R-1 v1.1:** protocolo de quince controles que evalúa si un problema
  institucional está suficientemente definido, si corresponde utilizar IA y
  qué condiciones de supervisión, datos, riesgo y trazabilidad necesita. No
  ejecuta las siete lentes de B-1 ni autoriza por sí mismo una puesta en
  producción. Se aplica dentro de **Gobernanza Incubadora**, el módulo
  formativo de acompañamiento de proyectos de IA -- el módulo y el protocolo
  no son lo mismo: la Incubadora es el espacio de trabajo, R-1 es el
  protocolo de control que corre dentro de ella.

## Capa exploratoria (experimental)

Módulo separado de la lectura multilente y de los protocolos B-1/R-1:
`services/exploratorio.py`, `routers/exploratorio.py`, pantalla propia en
`/exploratorio.html`. Produce **hipótesis no validadas**, nunca hallazgos --
su salida no se incorpora automáticamente a controles, anexos ni evidencia
institucional. Se bloquean las referencias tipadas a hipótesis al aportar
evidencia y al evaluar la emisión (ver `tests/test_pared_exploratoria.py`).
Esto no valida semánticamente textos libres ni referencias genéricas aportadas
manualmente: una asociación no es evidencia suficiente de conformidad y debe
descartarse como fundamento autónomo durante la revisión institucional.
B-1 v1.2 también excluye Rizoma y las salidas marcadas como exploratorias del
análisis Multilente al construir estados y evidencia iniciales.

## Implementación vigente

El recorrido habitual es carga → lectura Multilente → controles automáticos →
comprobante automático. B-1 no aparece como continuación sugerida: es una capa
institucional separada, disponible por acceso directo cuando la normativa exige
revisión humana documentada. La ausencia de inconsistencias solo describe los
controles, condiciones y cobertura de esa ejecución.

`versiones.py` centraliza aplicación, motor y documento metodológico. La API
mantiene **0.3.0** como versión independiente de su contrato HTTP. Las versiones
B-1 y R-1 se obtienen de `VersionProtocolo` en la base; no se duplican en constantes
de aplicación. B-1 1.2 conserva once controles y excluye la exploración de su
conformidad/evidencia; las evaluaciones históricas conservan su protocolo y no
se reinterpretan retrospectivamente. El Word vigente de esta entrega es un
artefacto externo destinado a su publicación en Zenodo: la aplicación no
distribuye archivos DOCX desde `static/`. Las versiones anteriores se conservan
solo como antecedentes históricos fuera de las rutas públicas.

Cada archivo nuevo conserva nombre, bytes recibidos (su SHA-256 y tamaño, no su
contenido), MIME, responsable y fecha. `Informe.saneamiento.proveniencia` vincula
esa huella con la del objeto saneado y sus transformaciones. La carga JSON usa
una representación canónica del payload identificada explícitamente como tal.
Los reingresos se enlazan con `informe_anterior_id`; conservan su versión y
controlan compatibilidad de esquema. No se inventan hashes de archivos históricos.

`contexto_validacion` admite `condiciones_criticas`, `campos_requeridos` y
`esquema_esperado` (columnas y tipos). En carga rápida se envía como campo JSON.
Las condiciones que no pueden verificarse quedan declaradas; una crítica ausente
o fallida impide concluir. Los cambios de significado no deducibles del archivo
requieren una nueva definición del contrato por la institución. Para cotejar
preinformes se exige comparabilidad explícita; para conciliar varios archivos,
contexto compatible de período, entidad, moneda, unidad y escala.

El manifiesto registra sanitización, condiciones, naturaleza de los resultados,
guardrails aplicados, convergencias, huellas de código y controles y modelos
realmente utilizados. `GET /api/informes/{id}/manifiesto` requiere permiso sobre
el informe. `EjecucionAnalisis` conserva la corrida y permite señalar posibles
reevaluaciones sin alterar decisiones ni revocar sellos automáticamente.

El panel `/tecnico.html` permite a administradores/docentes con rol administrador
configurar actividades de votación y registrar calibraciones. La votación expresa
exclusivamente una preferencia pedagógica entre proyectos de una cohorte: no es
ranking de calidad, evaluación académica, certificación, aprobación técnica ni
autorización para implementar. Sus justificaciones y resultados no cambian R-1,
la devolución docente, las constancias ni Monitoreo. Los votos históricos
permanecen en su cohorte cerrada. Conexiones agrupa proyectos visibles; su consulta
general no aplica el filtro de cohorte específico de la votación.

La calibración compara resultados aportados por el responsable con los esperados,
según una tolerancia explícita. No ejecuta una batería nueva al registrar esos
datos. Distingue cambios de motor, entorno de datos y condiciones insatisfechas.
La búsqueda retrospectiva delimita ejecuciones por fechas, dominio, código,
protocolo y control. No puede descartar afectación sobre ejecuciones históricas
sin versiones. La validación externa ciega sigue pendiente: su infraestructura
permite registrar casos separados y rechaza reutilizar un caso calibrado como ciego.

Monitoreo tiene interfaz y API implementadas: cinco tipos (avance, riesgo,
decisión, indicador y aprendizaje), cuatro estados (abierto, en curso, resuelto
y descartado), responsable, fecha, valor numérico opcional para indicadores e
historial completo de cambios de estado. El titular del proyecto y los
administradores pueden registrar y consultar su seguimiento. El resumen cuenta
registros por tipo y estado; no calcula cumplimiento de metas, impacto ni eficacia.
La API no comprueba que el proyecto esté en producción ni lo limita al ganador
de una votación. Su uso sostenido y utilidad requieren validación empírica.

### Pruebas e instalación

Instalar `requirements-dev.txt` en un entorno virtual y ejecutar `pytest` desde
la raíz. La suite configura credenciales ficticias y SQLite para sus fixtures;
no necesita datos reales ni claves de IA. La suite Python
(`python -m pytest -q`) y las pruebas JavaScript
(`node --test tests/ejemplos_zip_ui.cjs`) deben quedar aprobadas en cada corte;
el número de pruebas crece con cada versión y se informa en `HISTORIA.md`. Estos tests verifican comportamientos
programados y no constituyen validación empírica de eficacia institucional,
concordancia entre evaluadores, tasas de falsos positivos o negativos, utilidad
decisoria ni validación externa. El corte público se regenera con
`scripts/actualizar_evidencia_publica.py`, que guarda en
`static/public-evidence.json` la fecha, los conteos, la huella Python del código
ensayado y los datos agregados de uso. Los cortes anteriores (286, 323, 326, 329
y 334) quedan como evidencia histórica fechada en `HISTORIA.md` y `docs/`.
La revisión integral está en `docs/documento/revision-073/`. Los registros de la suite del
corte 0.7.0 se conservan en `docs/revision-070/`. El conteo se puede reproducir
con `pytest --collect-only -q`; no se presenta como un conteo de futuras versiones.
Estas pruebas verifican comportamientos programados, no eficacia institucional.
Siguen pendientes concordancia entre evaluadores, falsos positivos y negativos
en casos reales, tiempos de aplicación, utilidad para quien decide y prueba ciega
externa. No se identificó en esta entrega un corpus independiente y reproducible
de los «35 casos sintéticos» mencionados anteriormente; esa cifra queda por revisar.

Para actualizar una base PostgreSQL existente: respaldo → `alembic upgrade head`
→ reinicio del servicio. Las migraciones 20260917 agregan ejecuciones,
calibraciones y actividades sin sustituir evaluaciones existentes. Ver
`docs/historico-07x/actualizacion_070.md` para alcance, compatibilidad y formato de calibración.

No es una octava lente: no está en `enums.Lente` (que sigue en siete
miembros, ver `tests/test_enums.py`), no usa `Severidad` ni los estados
`conforme`/`observado`. Su único estado posible es `HIPOTESIS_NO_VALIDADA` --
sin escala de confianza numérica ni ranking, porque un número invita a leer
una conjetura como medición.

Dos pistas, ambas con lenguaje neutral de `services/guardrails.py` aplicado a
su salida:

- **Preguntas no formuladas:** un modelo lee el informe y propone
  interrogantes que las siete lentes no anticiparon (se le pasan las
  preguntas canónicas de `services/lens_matrix.py` con la consigna explícita
  de no repetirlas).
- **Correlaciones no declaradas:** el cálculo es determinístico en Python
  (`services/exploratorio.calcular_correlaciones`), igual que el resto de los
  cálculos del sistema; el modelo de lenguaje solo redacta la comunicación
  del resultado, siempre como coincidencia observada y nunca como causa.

Deliberadamente fuera de alcance: comparar un informe con antecedentes que
terminaron en corrección. Señalar por semejanza se acerca a atribuir
responsabilidad por parecido, que es precisamente lo que este sistema no
hace.

La tabla `hipotesis_exploratorias` no tiene relación alguna con
`EvaluacionCertificacion` ni con `Hallazgo` -- ni clave foránea, ni relación
ORM, ni campo de referencia cruzada, ni campo de "promoción a hallazgo".
Cuelga del informe y de nada más. Acceso restringido a usuarios habilitados,
igual que el resto de la carga; nada de esto es visible en la página pública
de verificación de sellos.

## Alcance agregado — no negociable

La lectura Multilente está destinada a información agregada por dimensión
(unidad, rubro, programa, período, tipo de señal), no al análisis de personas ni
documentos individuales. `services/sanitizacion.py` aplica filtros sobre los
informes al cargarlos: una columna
cuyo nombre matchee un patrón de identificador (`proveedor`, `contratista`,
`adjudicatario`, `cliente`, `beneficiario`, `cuit`, `dni`, `email`, `teléfono`, `factura`, `expediente`,
`nombre`, `apellido`, etc.) se excluye antes de guardar el informe. Las columnas
que nombran personas (`agente`, `empleado`, `titular`, `paciente`, `docente`,
`socio`, `afiliado`, `alumno`, `destinatario`, `contacto`, en singular o plural)
se conservan sólo si sus valores son cifras («Agentes» = 120 es un conteo); con
texto adentro se excluyen, y nunca se usan como rótulo de fila. Una columna se
conserva por sus valores, nunca por su rótulo. En texto libre se enmascaran el
DNI con etiqueta («DNI 12.345.678», «Documento: 30.123.456», «dni nro
12345678»), el CUIT con guiones, el CUIT con puntos, espacios o sin separador
sólo si su dígito verificador es válido, los correos, los teléfonos («+54 9 11
4555 1234», «011 4555-1234», «4555-1234», con o sin etiqueta) y las
referencias a comprobantes. Un número sin esa forma no se toca: códigos
presupuestarios, años, rangos («2019-2020») y montos quedan intactos. Los
expedientes con formato sistema de expedientes («EX-2024-…-APN-…») son identificadores
administrativos y se conservan salvo que vengan rotulados como expediente. La exclusión no es silenciosa: queda en
`Informe.saneamiento` y se muestra tanto en la respuesta de la API como en la
interfaz. Los filtros no garantizan anonimización absoluta ni detección de todo
identificador indirecto. Los archivos deben revisarse antes de cargarlos.
Incubadora y Monitoreo sí conservan autoría y usuarios para gestionar accesos;
esto no equivale a analizar su desempeño.

## Flujo

1. `POST /api/areas` — dar de alta las unidades.
2. `POST /api/informes` — cargar información agregada de una unidad para un
   período (`datos` es una lista de registros agregados por dimensión;
   columnas numéricas se detectan solas; columnas identificatorias se
   descartan automáticamente).
   La carga rápida (`/api/analisis-rapido`) analiza sólo Excel (.xlsx, .xls) y
   CSV. Un PDF (con texto o escaneado) o una imagen recibe un 422 con
   `detail.codigo = "requiere_revision_lectura"`: primero pasa por la revisión
   de lectura (`/api/ocr`), donde la persona ve el original al lado de la tabla
   leída (del texto del PDF, u OCR local para páginas sin texto e imágenes),
   corrige y confirma; la tabla confirmada se analiza como CSV con
   `origen_lectura` y `archivo_original` (ver `docs/motor/OCR-LOCAL.md`).
3. `POST /api/informes/{id}/analizar` — corre las lentes disponibles, triangula
   entre los modelos de IA configurados (GPT, Gemini, Renderix, Claude,
   DeepSeek, Llama) y genera la devolución comprensible. No dispara nada hacia
   otras unidades.
4. `GET /api/informes/{id}/comprobante-controles.pdf` — descarga el comprobante
   de los controles automáticos aplicados y registra la descarga en la bitácora.

Interfaz web en `/` (estáticos servidos por FastAPI desde `static/`), API bajo
`/api`.

## Alcance

Las lentes usan heurísticas simples (sumas, z-scores, correlaciones)
en vez de modelos entrenados — son un esqueleto funcional, no el estado
final del sistema. El radiólogo solo opera sobre `dominio="presupuestario"`,
tal como plantea el documento. La triangulación sí llama a los modelos
configurados si están disponibles; si no lo están, esa
ausencia queda registrada explícitamente en vez de simularse.

## APIs de modelos

La triangulación puede usar seis servicios de IA cuando las credenciales están cargadas en `/home/gobernanza/.env`:

- `OPENAI_API_KEY` con `OPENAI_MODEL=gpt-4.1-mini`
- `ANTHROPIC_API_KEY` con `ANTHROPIC_MODEL=claude-sonnet-4-6`
- `GEMINI_API_KEY` con `GEMINI_MODEL=gemini-2.5-flash`
- `DEEPSEEK_API_KEY` con `DEEPSEEK_MODEL=deepseek-chat`
- `RENDERIX_API_KEY` con `RENDERIX_BASE_URL=https://ia.plataformaialocal.com/local/v1` y `RENDERIX_MODEL=renderix-es:latest`
- `OLLAMA_BASE_URL` / `OLLAMA_API_KEY` con `OLLAMA_MODEL=llama3.1`

Las claves no se guardan en el código ni se muestran por API. El endpoint protegido `/api/modelos/status` indica solamente si cada servicio de IA está configurado y qué modelo se usará. Si una clave falta o falla, la app sigue funcionando con las lentes heurísticas y registra explícitamente que esa interpretación de modelo no se ejecutó.

Luego de modificar `.env`, reiniciar con `systemctl restart gobernanza.service`.

### Datos enviados y alcance de las estimaciones

Cada llamada de interpretación NO recibe el archivo cargado (el Excel/CSV/PDF
completo), sino el `SYSTEM_PROMPT` y un JSON con los hallazgos que recibe
`_prompt_usuario` en `services/triangulacion.py`, incluida su evidencia,
contexto y orientación declarada. No existe un límite fijo de 2–3 hallazgos
en esa función. El costo depende del proveedor, modelo y contenido enviado;
no se garantiza un costo fijo por corrida. Sin hallazgos se omiten las llamadas
de triangulación, no necesariamente las de otros módulos ni los costos operativos.

La capa exploratoria usa OpenAI por separado. Para proponer preguntas puede
enviar hasta cinco filas saneadas, además del período, dominio y columnas;
para redactar asociaciones envía variables, coeficiente y observaciones.
No hereda la configuración local Ollama de triangulación. Tutoría y demás
funciones de IA también requieren revisar su circuito específico antes de
prometer procesamiento íntegramente local.

Los valores de `COSTO_ESTIMADO_MODELO` en `static/app.js` son una
referencia de tarifa pública por modelo medida a **enero 2026**, no un
cálculo en vivo a partir del uso real de tokens de cada respuesta (la app no
trackea `usage` de las APIs). Sirven para comparar qué modelo sale más caro
entre sí, no como presupuesto exacto de una corrida puntual — y hay que
revisarlos a mano si cambian las tarifas de los proveedores o los modelos en
`.env`.

## Tests

Suite única con pytest (`tests/`, configurado en `pyproject.toml`):

```
venv/bin/python3 -m pytest
```

Correr la suite después de tocar umbrales, reglas o el orden de las lentes.

## Accesibilidad de las exportaciones

Los reportes se ofrecen también en Markdown y HTML, formatos recomendados
cuando se necesita adaptar tipografía, contraste o tecnología de asistencia.
El PDF conserva texto Unicode, orden de lectura y metadatos documentales, pero
la versión actual no es un PDF etiquetado ni declara conformidad PDF/UA. Por
eso no debe presentarse como plenamente accesible hasta completar una
validación específica con lectores de pantalla.

## Desarrollo local

```
python3 -m venv venv
venv/bin/pip install -r requirements-dev.txt
cp .env.example .env  # completar credenciales
venv/bin/python scripts/inicializar_base.py  # base vacía o existente
venv/bin/uvicorn main:app --reload --port 6163
```

La aplicación requiere una base PostgreSQL. `scripts/inicializar_base.py` prepara
tanto una base vacía como una existente; la guía completa, probada desde cero,
está en `docs/operacion/INSTALACION.md`. Para tests
no se necesita `.env`. `GOBERNANZA_PASSWORD` sigue siendo un campo requerido de
configuración; el acceso real es por usuario (ver `core/auth.py`). Si se mueve el
proyecto, crear un entorno virtual nuevo: sus ejecutables contienen rutas absolutas.

## Despliegue en este servidor

Servicio systemd `gobernanza.service`, usuario de sistema `gobernanzaapp`,
puerto interno 6163, detrás de nginx (con TLS) en
`gobernanza.entornodepruebas.com.ar`. Base Postgres `gobernanza` con rol
`gobernanza`. `nginx.service` corre en foreground en este VPS — recargar con
`nginx -s reload`, nunca `systemctl restart nginx`.

Variables de operación opcionales en `.env`: `MODELOS_SUSPENDIDOS` (proveedores de
triangulación suspendidos sin borrar credenciales, separados por coma),
`MONITOREO_PROYECTO_ID` (único proyecto con Monitoreo habilitado) y
`USUARIOS_EXCLUIDOS_METRICAS` (correos de cuentas de prueba que no cuentan en las
métricas, separados por coma), y `ALERTAS_EMAIL` (destinatario fijo de
`scripts/alerta_errores.py`, que avisa por errores 500, análisis fallidos en segundo plano y
caída del servicio). `DOCENTE_AVISO_EMAIL` (correos del docente, separados por coma, que reciben un aviso por cada consulta nueva al espacio docente de la Incubadora —sólo proyecto, fecha y enlace, sin el texto ni datos del participante— y el recordatorio diario de `scripts/recordatorio_consultas_docente.py`; vacío, no se avisa). La prueba de restauración del backup está en `docs/operacion/RESTAURACION-BACKUP.md`.

Uso de IA y cuentas: `LIMITE_ANALISIS_IA_DIA` (análisis y exploraciones con IA por usuario en 24
horas, 20 por defecto; 0 = sin tope) y `LIMITE_MENSAJES_INCUBADORA_DIA` (150 por defecto); la
administración queda exenta. `INCUBADORA_AMBITO=organizacion` adapta la tutora de la Incubadora a
empresas, cooperativas y ONG (por defecto, administración pública). Cada usuario puede cambiar su
contraseña y cerrar sesión en todos sus dispositivos desde «Mi cuenta»; la administración puede
desactivar usuarios y cerrar sus sesiones desde Actividad → «Usuarios y accesos».

### Modelos de triangulación

La capa de triangulación puede consultar OpenAI, Gemini, Renderix, Anthropic, DeepSeek y Llama/Ollama. Cada servicio interpreta los mismos hallazgos y el sistema conserva coincidencias, divergencias y lecturas singulares; no se fuerza votación ni consenso.

Variables relevantes: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `DEEPSEEK_API_KEY`, `RENDERIX_API_KEY`, `OLLAMA_API_KEY`, `OPENAI_MODEL`, `ANTHROPIC_MODEL`, `GEMINI_MODEL`, `DEEPSEEK_MODEL`, `DEEPSEEK_BASE_URL`, `RENDERIX_MODEL`, `RENDERIX_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_BASE_URL`.
