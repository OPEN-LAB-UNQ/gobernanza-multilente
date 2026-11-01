## 0.10.65 · 01/11/2026

Documento metodológico v9.4 y presentación sin el nombre del ministerio. Motor sin cambios (multilente-0.10.61).

- **Ficha técnica.** Cita el documento metodológico v9.4, publicado en Zenodo el 1/11/2026 (10.5281/zenodo.23851688): actualiza la v9.3 con los cortes 0.10.41.4 a 0.10.64 (adenda K) y deja de nombrar organismos, jurisdicciones y publicaciones oficiales asociados a posibles errores reales o a las validaciones, sin cambiar sus resultados.
- **Presentación.** La actividad formativa se describe sin nombrar el ministerio al que pertenece la mayoría de los participantes, con el mismo criterio que la copia pública del código y la v9.4; la aclaración final dice que no implica adopción ni aval de ningún organismo.
- Las pruebas que fijaban los textos anteriores se actualizaron: ahora exigen que la presentación no nombre al ministerio y que la ficha cite la v9.4.

## 0.10.64 · 31/10/2026

Python 3.12 y dependencias actualizadas. Motor sin cambios (multilente-0.10.61). La aplicación corría con Python 3.9, que dejó de tener soporte en octubre de 2025, y declaraba versiones con avisos de seguridad conocidos en la base OSV: Starlette 0.41 (por FastAPI 0.115), python-multipart 0.0.20, pypdf 6.16, Pillow 11.3, python-dotenv 1.0 y pdfminer.six 20251107 (por pdfplumber 0.11.8); en desarrollo, pytest 8.4. Las correcciones de varias exigen Python 3.11 o posterior.

- Entorno nuevo con Python 3.12 (`venv312`); el anterior, con Python 3.9, queda guardado para volver atrás.
- FastAPI 0.115.6 → 0.162.0 (Starlette 0.41.3 → 1.10.0), python-multipart 0.0.20 → 0.0.33, pypdf 6.16.1 → 6.21.4, Pillow 11.3.0 → 13.0.0, python-dotenv 1.0.1 → 1.2.4 y pdfplumber 0.11.8 → 0.11.10 (pdfminer.six 20260107); en desarrollo, pytest 8.4.2 → 9.2.0. El resto, igual.
- Los 66 paquetes instalados, sin avisos conocidos en OSV al 31/10/2026.
- Requisito de instalación: Python 3.11 o posterior.

Pruebas: sin cambios en el código; suite completa con Python 3.12: 2642 pruebas de Python y 122 de pantalla.

## 0.10.63 · 30/10/2026

Tutora de la Incubadora. Caso real del 30/10: un participante de una comisión del grupo original se quejó de que la herramienta le preguntaba una y otra vez lo mismo. Su conversación mostró tres problemas, corregidos sin cambiar el motor (multilente-0.10.61).

- **Preguntas cortadas.** El filtro que limita y saca preguntas repetidas (`_limitar_preguntas`) dejaba restos: «2. Por ejemplo,» sin pregunta, «2. ****» cuando la pregunta estaba en negrita, «**Usuarios:** Por ejemplo, …» con la etiqueta suelta y ejemplos en líneas con sangría pegados al ítem anterior. Ahora la etiqueta, el énfasis, el ejemplo de la misma oración y las líneas de continuación se van con la pregunta descartada.
- **Pendientes repetidos.** Después de que el participante respondió punto por punto, la tutora le volvía a listar los mismos faltantes con las mismas palabras. El prompt pide ahora reconocer qué aportó de cada pendiente y explicar qué precisión falta y por qué; los pedidos de borrador, pendientes y siguiente paso lo recuerdan, y una respuesta en varios puntos numerados se incorpora punto por punto (`_responde_varios_puntos`).
- **Siglas.** La tutora tomó una sigla por el nombre de un fenómeno climático. El prompt pide preguntar qué es una sigla o un nombre propio que no conoce antes de suponerlo.
- **Revisión con citas.** Para el problema citaba la frase más antigua del participante aunque después la había ampliado. Cada aporte llega ahora con su orden («aporte 2 de 9, del más antiguo al más reciente») y la instrucción pide citar el más reciente y completo.
- Una prueba de 0.8.x esperaba que quedara suelto el ejemplo de una pregunta descartada («Por ejemplo, discrepancias.»): se actualizó a la nueva regla.

Pruebas: tests/test_tutora_0163.py (10). Suite completa: 2642 pruebas de Python y 122 de pantalla.

## 0.10.62 · 29/10/2026

Grupos de cursada. Pedido del 29/10: dar de alta a un grupo nuevo sin que vea los trabajos de las comisiones 1 y 2 del grupo original, y al revés. Motor sin cambios (multilente-0.10.61).

- **Grupo de cada cuenta** (`usuarios.grupo`). Sin grupo es el grupo por defecto, el de las comisiones originales; la cuenta administradora ve todos (`services/grupos.py`).
- **Lo que ve cada participante.** La galería de casos, «Ver trabajo completo», Conexiones y los conteos de temas de la tutora muestran sólo proyectos del propio grupo (`_proyectos_visibles(..., usuario)`). También las métricas de «Calibración del sistema» y las de la tutora cuentan sólo el propio grupo. La página principal ya no entrega a otro grupo los tramos escritos a mano sobre proyectos del grupo original (las tres síntesis y el piloto de Monitoreo): `main.index_para` los quita y muestra un aviso. Los informes ya eran de cada persona.
- **Votación por grupo** (`actividades_votacion.grupo`). Hay una votación activa por grupo (índice único sobre el grupo cuando está activa, en lugar de una sola en total), activar una apaga sólo la de su grupo y no admite proyectos de otro grupo. Si una cuenta cambia de grupo después de armada la votación, su proyecto deja de mostrarse y de poder votarse en ella. La administración ve la votación activa más reciente. La página técnica suma el campo «Grupo» y lo muestra en el selector.
- **Altas.** La API de administración crea cuentas con grupo (hasta 60 caracteres) y la tabla de usuarios lo muestra.
- **Migración** `20261029_grupos`: dos columnas que admiten NULL y el índice de la votación activa por grupo. Nada se borra; las cuentas y la votación existentes quedan en el grupo por defecto. Probada contra una copia de la estructura de la base.

Revisión independiente: encontró cuatro fugas (las síntesis de la página principal, las dos métricas y la votación tras un cambio de grupo), corregidas con sus pruebas.

Pruebas: tests/test_grupos_0162.py (13). Suite completa: 2632 pruebas de Python y 122 de pantalla.

## 0.10.61 · 28/10/2026

Ajustes de una auditoría externa de sólo lectura (28/10/2026). Cada hallazgo se verificó contra el código, la base y los registros antes de tocar nada. Controles sin cambios.

- **Contador público.** «Uso registrado» contaba como revisado todo informe cargado, y como «sin señales» también a los que no tenían devolución (había uno). Ahora separa cargados, con devolución y, entre estos, sin señales; las observaciones son las de informes con devolución (`uso_publico.CON_DEVOLUCION`).
- **Alertas por origen.** `scripts/alerta_errores.py` tomaba cualquier traceback como análisis fallido. El 27/10 el proveedor reinició el servidor, la migración del arranque encontró la base levantándose, el servicio volvió solo a los 12 segundos y el correo dijo «fallaron análisis en segundo plano». Ahora cada traceback se avisa por su origen (arranque, base, proveedor de IA u otro) con la línea de la excepción y, en el arranque, si volvió después del último intento. Los de un análisis fallido y de un 500 no se repiten: ya tienen su aviso, el del análisis ahora con el número de trabajo. Un traceback cortado no se traga al siguiente, y uno en un formato que no se reconoce se avisa igual.
- **/api/health.** Respondía siempre «ok». Ahora consulta la base (503 si no responde) y la cola con los umbrales de `scripts/vigilar_cola.py` («degradado» si está trabada). Sigue público y sin datos.
- **Errores de análisis.** La pantalla y el correo mostraban el texto de la excepción; en septiembre llegó a usuarios un error de programación tal cual. Ahora muestran un mensaje fijo con el número de trabajo y el detalle queda sólo en el registro (`jobs.error_interno`).
- **Tope de carga.** El límite de 30 MB se comprobaba después de cargar el archivo entero en memoria. Ahora se rechaza por su tamaño, que se conoce al recibirlo, o leyendo como mucho un byte más que el tope.
- **Sondeo.** El motivo decía «es la forma del cuadro que se repite, no un error». Ahora dice que puede ser la forma del cuadro o un error de plantilla copiado en cada hoja, y que no se puede distinguir sin mirarlo (`sondeo.REPETIDO_EN_HOJAS`). La ficha lo dice igual.
- **Textos públicos.** Qué datos se cargan (agregados, nunca de personas; el filtro de datos personales no los encuentra todos); «informes reservados» en lugar de «sensibles»; la devolución automática como borrador previo a la revisión humana; las cifras de la medición vigente. Son 119 de 123 errores insertados y 88 de 132 planillas publicadas sin señal alta, con la aclaración de que no es una tasa de acierto, y 169 señales altas, medidas el 28/10/2026 con multilente-0.10.59 (la 0.10.60 y esta no cambian los controles). Los 8 posibles errores reales se volvieron a comprobar con el motor vigente: 7 en alta y 1 en media.
- **Fuera de esta versión.** El destinatario fijo de alertas (ALERTAS_EMAIL) es configuración del servidor y espera el OK. Separar el procesamiento de la web, congelar reglas y armar un conjunto de evaluación reservado son decisiones de fondo. «¿Qué resultó ser esta señal?» no tiene ninguna respuesta en 168 informes: queda por revisar por qué.

Pruebas: tests/test_auditoria_0161.py (19). Suite completa: 2619 pruebas de Python y 122 de pantalla.

## 0.10.60 · 28/10/2026

- Lector del cuadro e interpretación previa sin DeepSeek por defecto: leen GPT (OpenAI) y Gemini, y una relación se comprueba si la proponen las dos. DeepSeek trata los datos en China, que no tiene decisión de adecuación de la Comisión Europea. Se vuelve a sumar sólo a mano (LECTOR_LECTORAS=gpt,gemini,deepseek; entonces hay que volver a declararlo en /privacidad), y con él vale lo que acuerden dos de tres. La triangulación no cambia: DeepSeek sólo si se elige expresamente. Las lecturas ya guardadas en informes anteriores se conservan (nada se borra) y no obligan a reanalizar.
- Pedido de la interpretación previa: dice que las relaciones son parte de la respuesta y pide proponer todas las que los rótulos sostengan. Antes, con «[] si no hay evidencia semántica suficiente», GPT no proponía ninguna y el lector funcionaba sólo con Gemini y DeepSeek.
- Medición del lector (28/10/2026, en el servidor, con llamadas reales a los proveedores): tres planillas oficiales correctas y seis copias con un error insertado (un total y un dígito por libro). Producción 0.10.59 (las relaciones salen de Gemini y DeepSeek, porque GPT no proponía ninguna): 34 relaciones acordadas en las correctas (33 confirmadas), 2 señales, 4 de 6 errores detectados. GPT + Gemini con el pedido nuevo, en dos pruebas: 30 acordadas las dos veces (todas confirmadas), 2 señales, 2 y 0 de 6 detectados. En la primera, entre 1 y 7 lecturas de GPT por planilla se descartaban enteras por citar una celda inexistente («referencias inexistentes»), y en las dos copias del libro de diez cuadros GPT y Gemini acordaron 3 y 18 relaciones (antes 28 y 31). En la segunda, con las citas inexistentes descartadas una por una, GPT perdió su lectura sólo en el libro de 18 cuadros (de 3 a 6 cuadros, sin ninguna cita real), donde quedaron 4 o 5 cuadros sin clasificar; la detección no mejoró. Los controles de la revisión (motor multilente-0.10.59, sin lector) detectan los seis errores de esas copias: lo que se pierde es la segunda ruta, no esos hallazgos. Se saca DeepSeek igual, por decisión del responsable, con el límite declarado en la ficha técnica.
- Revisión independiente (28/10/2026): no quedan caminos que manden cuadros a DeepSeek por defecto. Arreglos: una cita inexistente se descarta sola y se cuenta (fuentes_descartadas); si no queda ninguna real, la lectura no vale, como antes. Una lectora pedida pero suspendida (MODELOS_SUSPENDIDOS) figura en cada cuadro como «No se consultó: está suspendida en este despliegue», porque con dos lectoras la que falta deja a los cuadros sin acuerdo. LECTOR_LECTORAS acepta openai y google; un nombre desconocido se avisa en el registro y una lista sin ninguna lectora conocida vuelve a GPT y Gemini. /privacidad dice «desde la versión 0.10.60» y «en este despliegue». Una interpretación preparada antes con DeepSeek y confirmada después conserva sus lecturas y su acuerdo.
- Páginas públicas: la ficha técnica, la charla, la presentación, la aplicación y /privacidad dicen dos proveedores (OpenAI y Gemini) y que el lector ya no envía los cuadros a DeepSeek.
- Pruebas: tests/test_lector_sin_deepseek.py (17). Suite completa: 2600 pruebas de Python y 122 de pantalla.

## 0.10.59 · 28/10/2026

- Motor multilente-0.10.59: ruido de totales y valores repetidos en libros oficiales grandes. Los dos libros que quedaban traían, siendo correctos, 86 «columna total que no cierra» y 50 «valor idéntico en otra fila» de prioridad alta. Cuatro cambios: (1) una fila con el total y las partes en cero (años todavía sin datos al pie de una serie) ya no cuenta como fila en que el total cierra: ahí cierra cualquier relación, y «Oferta Global Total» quedaba confirmada como la suma de los consumos; (2) tres o más filas seguidas en que un total falla con el mismo signo y por una diferencia pareja (hasta 15 %, la mayor como mucho tres veces la menor) son una sola señal de prioridad alta, con la diferencia de cada fila, anclada en la que más se aparta y con un rango que las cubre a todas: puede ser un tramo en que la fuente suma otra cosa o un mismo error repetido; (3) un valor con más de cuatro decimales que es el promedio de 2, 3, 4, 6 o 12 valores escritos con pocos decimales (tasas anuales de trimestres, promedios de meses) toma la resolución de sus sumandos sólo para decidir si un total cierra y para contar las cifras de un valor repetido; un promedio de enteros no; (4) en una serie empalmada (un índice viejo por un coeficiente), si el valor repetido es múltiplo de la misma unidad que buena parte de su columna, las coincidencias casuales esperadas se cuentan con esa unidad y entre esos valores: sólo si no son raras la igualdad no se señala.
- Revisión independiente (28/10/2026), en dos vueltas. La primera encontró diez puntos en la primera versión; los más graves, de los que esconden un error de verdad: un error repetido en bloque (×1000 en tres meses) quedaba en una sola señal media, un promedio de enteros admitía ±2 y una copia en una serie empalmada corta se callaba. La segunda, dos casos más de series empalmadas (índice viejo mayor que 200,00 y tramo corto dentro de una columna continua). Todos corregidos, cada escenario como prueba. Pérdida aceptada: un total que sólo se confirmaba gracias a las filas en cero ya no se confirma. Límite anotado: un promedio de 6 o de 12 enteros se lee con uno o dos decimales (mirarlo con todos los divisores confundiría promedios de tasas con promedios de enteros).
- Medición (28/10/2026, en el servidor con topes de CPU y memoria, contra producción 0.10.57; el motor no cambió en 0.10.58): errores insertados, 119 de 123, igual (ninguno perdido ni ganado); planillas publicadas sin alterar, 172 → 169 señales altas, ninguna nueva (las tres que se van son porcentajes con un decimal que suman 100,1 con el total guardado como 100,00000000000001). Libros grandes: 229 → 114 y 81 → 74 casos altos («columna total que no cierra» 86 → 12 y 21 → 14; «valor idéntico en otra fila» 50 → 9).
- /privacidad: el aviso legal ya no dice «Uso educativo y de investigación», frase retirada de las páginas públicas.
- Pruebas: tests/test_ruido_totales_repetidos.py (27). Suite completa: 2583 pruebas de Python y 122 de pantalla.

## 0.10.58 · 28/10/2026

- Aplicación 0.10.58, motor sin cambios (multilente-0.10.57): prolija para la Unión Europea (RGPD y directiva de privacidad electrónica). Página pública nueva, /privacidad («Privacidad, cookies y aviso legal»), enlazada desde el pie de la presentación, la ficha técnica y la charla, desde la prueba pública, la pantalla de ingreso y la aplicación: responsable (Maximiliano Pérez, proyecto de OPEN LAB · UNQ) y contacto; qué datos se tratan si visitás las páginas públicas (registros del servidor web, 10 días), si tenés una cuenta (cuenta, informes ya saneados sin el archivo original, resultados, respuestas a señales, Incubadora y registro de actividad; mientras la cuenta esté activa, baja a pedido dentro de un mes, respaldos diarios por 14 días y mensuales por 24 meses) o si escribís; bases legales (art. 6.1.b y 6.1.f del RGPD); la única cookie (gobernanza_auth, estrictamente necesaria, sólo con sesión, 12 horas) y las cuatro preferencias que quedan en el navegador; proveedores (alojamiento en la Argentina con adecuación 2003/490/CE, respaldos, correo, y qué rutas envían contenido a OpenAI, Gemini y DeepSeek, con la transferencia a China dicha tal cual); derechos y autoridades (autoridad de protección de datos, autoridad del país de residencia en la UE); seguridad y menores; aviso legal y licencias.
- El video de la presentación queda detrás de un botón «Reproducir el video»: el reproductor de YouTube (youtube-nocookie.com) se crea recién al apretarlo (static/presentacion-video.js, porque la CSP no admite scripts en línea). Al abrir cualquier página pública el navegador no baja nada de otro dominio.
- Pruebas: tests/test_privacidad_ue.py (6): la página y sus apartados, ningún recurso de terceros al abrir las páginas públicas, el video detrás del botón, el enlace en cada página pública, y que toda cookie del servidor y toda clave que el código guarda en el navegador figuren en /privacidad (si se agrega una, la prueba obliga a declararla).

## 0.10.57 · 28/10/2026

- Motor multilente-0.10.57: ruido en libros oficiales grandes con bloques apilados. Los dos libros que entran desde 0.10.56 traían 749 y 1.675 señales altas siendo correctos. Casi todas salían de una misma estructura: cada hoja apila un bloque anual, uno trimestral y uno mensual, con una fila de códigos de serie («45.2_IT_0_T_13») antes de cada bloque. Ahora una fila de códigos de serie dentro del cuadro es metadato y separa los bloques (también con guiones bajos dobles, sin el prefijo numérico o con puntos en un tramo, si la mayoría de la fila son códigos completos); el lector de períodos entiende el trimestre con punto («I.16») y la fecha guardada como texto («2020-08-01 00:00:00»); una columna con bloques seguidos de distinta frecuencia es un formato oficial: cada bloque es su propia serie, con sus controles de valores y la interpretación confirmada de su cuadro, y sus períodos se validan por bloque (un año repetido al comienzo del bloque trimestral es un duplicado); una columna de una sola frecuencia no anual se valida por su ordinal; «n,d,», «s,d,», «s.d» y «n.d» son marcas de dato no disponible; las unidades físicas («GWh», «MW», «°C», «Miles Tns.», «dam3») forman filas de unidades; y un período sin número en ninguna de las series del cuadro que lo abarcan (al menos otras dos, con tres o más series) no tiene datos, como un año sin encuesta: un vacío ahí no se señala en cada serie, y el faltante de una serie que empezó antes que las demás se sigue señalando.
- Revisión independiente (28/10/2026): encontró cuatro errores en las primeras versiones de este cambio, todos de los que esconden un error de verdad: un cuadro apilado que se descartaba con sus faltantes y sus valores mal escritos, un período mal escrito en el borde de un bloque que no se validaba, el faltante de una serie que empezó antes tomado como año sin datos, y los bloques que por la ruta real de carga quedaban fuera de los controles porque la interpretación no los encontraba. Todos corregidos, cada uno con su prueba.
- Medición (28/10/2026, en el servidor con topes de CPU y memoria, contra producción 0.10.56): planillas publicadas sin alterar, 172 señales altas en 132 planillas, igual (ninguna nueva, ninguna que se va); errores insertados, 119 de 123, igual (ninguno perdido ni ganado). En los dos libros oficiales grandes los casos de prioridad alta bajan de 749 a 229 y de 1.675 a 81 («año no entero» 935 → 1, «cambio de tipo» 1.005 → 23, «vacío interior» 210 → 29). Aparecen 30 casos altos nuevos en series que antes no se leían como tales, algunos con aspecto de anomalías de escala. Quedan como próxima mejora 86 «columna total que no cierra» en dos hojas con encabezados de varios niveles y 50 «valor idéntico en otra fila» en índices.
- Pruebas: tests/test_ruido_libros_grandes.py (18, una por la ruta de la revisión rápida con la interpretación declarada). Suite completa: 2550 pruebas de Python y 122 de pantalla.

## 0.10.56 · 27/10/2026

- Motor multilente-0.10.56: total de columna en una fila que es una suma. El control de la fila «Total» descartaba toda diferencia mayor que el 15 %, por si la fila no era una suma. Ahora una diferencia de hasta el 50 % también se señala si el total declarado supera la suma de sus partes, todas presentes y no negativas, y en la misma fila cierran al menos tres columnas distintas con valores (no cuentan las de ceros ni las repetidas) que son al menos la mitad de las comparadas. Un promedio, un saldo, un máximo o un conteo de personas únicas declaran menos que la suma y no entran; una parte reservada («s») o vacía tampoco, porque el total publicado la incluye. La señal lo dice y su evidencia lleva `fila_suma_por_otras_columnas`. Caso: un cuadro mensual de recaudación con «TOTAL» anual en el que un dígito corrido en diciembre dejaba el total un 16 % arriba de la suma de los meses mientras las otras doce columnas cerraban.
- Libros rechazados sólo por el rango usado: si un .xlsx superaría el tope de 3 millones de celdas de rango por filas o columnas con formato y sin datos, por la dimensión declarada o por unas pocas celdas sueltas lejos del cuadro, las hojas se recortan al bloque con datos antes de leerlas. Primero sólo el formato; si no alcanza, quedan fuera hasta 20 celdas sueltas con datos por hoja, de a una hoja (la que más baja primero) y sólo hasta entrar. Se recortan las combinaciones y la dimensión y se quitan los vínculos que salen del bloque; una hoja con un comentario fuera del bloque o con celdas sin referencia no se recorta, y un libro con más de 1,5 millones de celdas escritas o que se rechazaría por sus datos no se recorre. Se hace una sola vez, a la entrada de la carga (como la conversión de un libro Open XML estricto) y fuera del bucle del servidor, y la lectura lo declara: hasta qué celda se leyó y qué celdas con datos quedaron fuera. Un libro que entra no se toca y el control de tamaño de 0.9.21 sigue valiendo sobre el libro recortado; antes se rechazaba entero. Reescribir una hoja de 1,48 millones de celdas usa 141 MB y 9 segundos.
- La prueba de pantalla de la revisión rápida espera el texto de ayuda vigente del botón (cambiado el 26/10); seguía esperando el anterior.
- Revisión independiente (27/10/2026): encontró siete errores en la primera versión de estos dos cambios (comentarios y vínculos fuera del bloque que la lectura volvía a crear, un recorte que guardaba cada celda en memoria, hojas con celdas sin referencia que perdían sus filas, partes reservadas, personas únicas y columnas de ceros tomadas como sumas, y celdas sueltas descartadas en hojas que no hacía falta recortar); todos corregidos, cada uno con su prueba.
- Medición (27/10/2026, en el servidor con topes de CPU y memoria, contra producción 0.10.54 / multilente-0.10.47 y la rama 0.10.55, con el código final): planillas publicadas sin alterar, 172 señales altas en 132 planillas, igual (ninguna nueva, ninguna que se va). Errores insertados: 115 → 119 de 123 sin perder ninguno: el dígito corrido del cuadro mensual, por el total de columna, y tres de los cuatro errores insertados en un libro oficial de 64 hojas que antes se rechazaba por el rango (dos picos aislados y un signo aislado, cada uno en su celda; la copia sin error no tiene señales en esa celda, y el total alterado sigue sin señal). Rechazos por tamaño en el banco de insertados: 9 → 4 (quedan los de un libro con más de 600.000 celdas con datos). Límite conocido: los dos libros oficiales grandes que ahora entran traen muchas señales altas siendo correctos (749 y 1.675, sobre todo «año no entero» y «cambio de tipo» en sus hojas de series): es un ruido del motor con ese formato que antes no se veía porque se rechazaban, y queda como próxima mejora. El mayor se analiza en unos 135 segundos con 1,1 GB.
- Pruebas: tests/test_total_columna_fila_suma.py (11) y tests/test_rango_inflado_recorte.py (16, una por la ruta de carga real). Se adaptaron dos pruebas de la salvaguarda de memoria de 0.9.21: un libro inflado sólo por formato o por la dimensión ahora entra recortado; los datos de verdad lejos del cuadro siguen contando y se rechazan rápido. Suite completa: 2532 pruebas de Python y 122 de pantalla.

## 0.10.55 · 27/10/2026

- Motor multilente-0.10.55: totales de series cortas. La relación «Total = suma de componentes» se corroboraba sólo con 4 períodos comparables o más; en un libro con una hoja por jurisdicción y tres años no se comprobaba ningún total, y un total alterado en una copia pasaba sin señal. Ahora, con 2 o 3 períodos comparables, la relación queda corroborada si la misma relación (mismos rótulos, mismo origen y misma unidad) cierra en todos sus períodos en al menos otras 3 hojas o cuadros del mismo archivo. No se corrobora si otra repetición falla el mismo período (indica un criterio distinto, no un error aislado) ni si menos del 80 % de las repeticiones están completas; las repeticiones que no cierran nunca (otro cuadro con los mismos rótulos, como uno de tasas) y las de valores insignificantes no cuentan, y una diferencia dentro del redondeo de los sumandos no se señala. La señal agrega «La misma relación cierra en todos sus períodos en otras N hojas o cuadros del archivo» y su evidencia lleva `corroboracion = repeticion_en_otras_hojas` y `repeticiones_que_cierran`; los cierres verificados y la materialidad (base «relación corroborada en otras hojas o cuadros») se cuentan como en las series largas, una vez por relación. Si no alcanza, el motivo dice que los totales tienen menos de 4 períodos comparables y no se repiten cerrando en otras 3 hojas o cuadros del archivo.
- Medición (26-27/10/2026, en el servidor con topes de CPU y memoria, contra el motor de producción multilente-0.10.47): planillas publicadas sin alterar, 172 señales altas en 132 planillas, igual (ninguna nueva, ninguna que se va); tampoco cambian el total de señales (1.921), las conciliaciones (2) ni los cierres verificados (7.301 en 19 planillas): ninguna de esas planillas tiene series cortas repetidas. Errores insertados: 115 de 123, igual (ninguno perdido ni ganado); las 9 planillas que superan el tope de 600.000 celdas se rechazan como antes. En un libro oficial con una hoja por jurisdicción (24 hojas, 2016-2018), los cierres verificados pasan de 0 a 216 sin señales nuevas en el original, y en cuatro copias con un error insertado (un total ×1,10, un componente +500, un total ×0,90 y un componente ×1,05) el error se señala en su celda en las cuatro; antes, en ninguna.
- Pruebas: tests/test_cierres_series_cortas.py, 14 casos con libros sintéticos (total alterado, dos períodos comparables por un «s/d», pocas repeticiones, el mismo desvío en varias hojas, dos errores en años distintos, redondeo en una jurisdicción chica, rótulos distintos, cuadro de tasas debajo, cuadros en cero, total arriba con sangría y la regla aislada). Suite completa: 2505 pruebas.

## 0.10.54 · 26/10/2026

- Incubadora, galería de casos: el trabajo completo de un caso se recorre y se busca sin salir de la tarjeta. Botones «Ir a la situación» e «Ir a la propuesta»; «Buscar en este trabajo» resalta las coincidencias en las dos secciones sin alterar el texto, dice «N de M coincidencias» y se recorre con «Anterior coincidencia» y «Siguiente coincidencia» o con Enter y Mayús + Enter (la consulta se toma como texto literal y distingue tildes); «Cerrar trabajo y volver a la tarjeta» devuelve el foco. Sin cambios en el motor (multilente-0.10.47).

## 0.10.53 · 26/10/2026

- Incubadora, galería de casos: «Ver trabajo completo» muestra la situación planteada y la propuesta guardada completas, con sus párrafos, y aclara que es texto guardado por el participante, que puede estar en elaboración y que no es una validación de la IA ni una aprobación docente. Se pide al abrirlo, una sola vez, y si falla se puede reintentar. El servidor devuelve una lista explícita de campos (nunca la conversación, las devoluciones privadas ni los contactos), aplica los mismos límites que la galería, exige sesión y no completa una propuesta ausente con el chat. La ficha orientativa queda plegada en «Ver ficha orientativa para comparar».

## 0.10.52 · 26/10/2026

- Incubadora: la detección por coincidencias de texto queda separada de las decisiones del participante. El avance dice «Hay N de M temas marcados por texto o por tu decisión; esto no confirma que estén resueltos» y distingue tema detectado por texto, cerrado por el participante y pospuesto; cada criterio se puede cerrar, reabrir o dejar en «Lo definiré después», y lo pospuesto prevalece aunque haya coincidencias de texto. La tutora recibe la detección como orientativa y los cierres del participante aparte, sin que una coincidencia de texto se le presente como cierre humano ni vuelva como aporte nuevo; en el pedido de avance trabaja sólo el primer pendiente y no repite preguntas ya respondidas. Si el modelo cierra con punto una cita que sigue en la fuente, se muestra la oración original completa, con sus restricciones y negaciones, sin admitir cambios de palabras; una afirmación de disponibilidad o permiso sin período histórico describe el estado actual.

## 0.10.51.1 · 26/10/2026

- Incubadora: la cronología de las rectificaciones la calcula el programa, no el modelo. Cada cita va con su propia rúbrica y sólo con las aclaraciones posteriores a ella; si no hay ninguna, no puede marcarse rectificada, y la última aclaración no se invalida a sí misma. La verificación de citas usa un modelo propio, configurable aparte del chat (OPENAI_MODEL_VERIFICADOR_INCUBADORA, por defecto gpt-5.4-mini; ver docs/operacion/CONTROL-CALIDAD.md), sin enviar parámetros incompatibles con modelos razonadores. La suite sin credenciales no mide la calidad semántica de ese modelo.

## 0.10.51 · 26/10/2026

- Incubadora: además de la pertinencia, cada cita se compara con las aclaraciones posteriores del participante. Si la persona retiró, contradijo o limitó esa misma afirmación para el mismo período y alcance, la cita no se usa («no sustenta el criterio con el contexto actual»); una mejora posterior no borra una observación histórica y una aclaración sobre otra variable no invalida la cita. Las rectificaciones tienen prioridad en la memoria, una aclaración archivada no llega al verificador y un veredicto sin vigencia explícita no se publica. En un pedido como «Resumí esto: tenemos fechas» se quita sólo el pedido y se conserva el aporte, con sus negaciones. Todo en la misma llamada de verificación, sin una tercera llamada al proveedor.

## 0.10.50 · 26/10/2026

- Incubadora: segunda lectura de pertinencia de las citas. Un modelo recibe sólo las citas y una rúbrica por criterio (problema, usuarios, evidencia, datos, flujo actual, rol de la IA, supervisión, riesgos, indicador y próximo paso), sin las conclusiones de la primera lectura, y decide si cada texto aporta contenido a su criterio, no si es verdadero ni si el criterio está completo. Una cita literal pero no pertinente se omite con aviso; una verificación truncada, incompleta o fallida no publica la revisión, y sin citas literales no se vuelve a llamar al proveedor. Se muestra siempre la redacción original (una mayúscula editorial no cambia palabras, cifras ni negaciones) y la cita no toma evidencia de la oración siguiente. Un pedido de síntesis se responde sólo con lo comprendido del caso y las aclaraciones, sin preguntas ni pasos nuevos; el texto real del botón de revisión no suma criterios ni fuentes.

## 0.10.49.1 · 26/10/2026

- Incubadora: pedir una revisión no cuenta como evidencia ni suma criterios; si el mismo mensaje trae el pedido y un aporte, el aporte se conserva. La revisión se arma en texto plano, como la muestran el chat y el panel, que escapan el HTML (antes salía con marcas de Markdown).

## 0.10.49 · 26/10/2026

- Incubadora, memoria y fuentes de la tutora (services/memoria_incubadora.py). La memoria toma sólo material humano activo, con cupos separados para que un mensaje reciente largo no desplace una corrección antigua, y declara su alcance parcial: la tutora no afirma haber revisado toda la conversación ni que un dato ausente nunca se aportó. Las fuentes del participante entran como material para revisar, nunca como instrucciones, y una respuesta anterior de la tutora no acredita confirmación del participante. La «Revisión con fuentes del participante» recorre los diez criterios con citas literales de lo aportado: las citas inventadas o tomadas de la IA se descartan con aviso, una revisión incompleta no se publica y se aclara que la cita acredita qué se aportó, no que el dato sea verdadero, esté disponible o que el criterio esté completo. El borrador separa «Lo aportado por vos» de «Propuestas por confirmar».

## 0.10.48 · 26/10/2026

- La pregunta de unidad del motor 0.10.47 se explica en pantalla y en el PDF como «unidad a confirmar»: «¿Estas columnas contienen cantidades o porcentajes?», con la celda, el cierre aritmético y la acción (confirmar la unidad y corregir el encabezado o la interpretación; no cambiar las cifras sin contrastar la fuente). Sin cambios en el motor.

## 0.10.47 · 26/10/2026

- Motor multilente-0.10.47 (el número salta de 0.10.39 al de la aplicación): unidades confirmadas contrastadas con el original. En un cuadro sin eje temporal, si dos o más columnas confirmadas como porcentaje (no variaciones, crecimientos ni ejecuciones) suman la única columna «Total» de cantidades en al menos 4 filas y en el 80 % de las comprobadas, y traen valores mayores que 100, se hace una sola pregunta de unidad por cuadro en lugar de un error por celda: la aritmética cierra; la unidad declarada requiere revisión. No impone un techo de 100 a cualquier tasa. Prueba con una planilla provincial publicada sin alterar: la pregunta sale en su celda y el cierre se conserva; porcentajes correctos, cantidades y variaciones no reciben alerta.
- No hay medición de los bancos con los motores 0.10.38 a 0.10.47: las cifras publicadas (115 de 123 errores insertados; 172 señales altas en 132 planillas publicadas) siguen siendo las de multilente-0.10.37.

## 0.10.46 · 26/10/2026

- Exploración con IA (informe 759): una conformidad («se mantienen coherentes», «sin cambio o conflicto», «sin indicación de que se contradigan») ya no se publica como hipótesis de discordancia.

## 0.10.45 · 26/10/2026

- Exploración con IA (informes 755 y 756). (1) Una cita con identificador y celda («e8, B17» o «B17 (e8)») se rechaza si la celda no es la de ese elemento, aunque el texto exista en otra celda. (2) Las etiquetas de cabeceras combinadas llevan su extensión a cada fragmento (leída del XML en flujo, sin cargar el libro entero): una celda de anclaje en otra fila no implica otra jerarquía, y no se señalan diferencias de estilo. (3) «12 veces mayor que el movimiento típico» es una razón de atipicidad, no un importe multiplicado por 12: se rechaza la frase que los confunde. (4) Una salida parcial dice cuántas hipótesis conservó y que no acredita cobertura completa. (5) La devolución dice «no aplicable» o «no evaluable», con el motivo, para las lentes que no corrieron, en lugar de «sin señales comunicables».

## 0.10.44 · 26/10/2026

- Exploración con IA (informes 752, 753 y 754). Cada fragmento conserva el año de sus meses y las columnas de contexto, con la aclaración de que los lotes son recortes de transmisión y no ciclos ni cuadros distintos. Se rechazan una «discontinuidad» que contradice un eje mensual completo y consecutivo, un mes «posterior al título» que está dentro del rango declarado (noviembre de 2022 no es fin de 2026) y un mes atribuido a una celda distinta aunque esa etiqueta exista en otra fila. El progreso ya no inventa una lectura de señales cuando no las había («No había señales para leer»); «salto anual» pasa a «salto entre períodos»; la salida de la exploración admite al menos 8.192 tokens.

## 0.10.43 · 26/10/2026

- Motor multilente-0.10.39: las diferencias entre períodos no saltan un mes sin datos (un dato ausente no vuelve vecinos a dos períodos separados); lo que el lector no leyó o quedó pendiente se nombra con su cuadro, además del archivo y la hoja, sin inventar un número; el eje se describe como «períodos en filas» o «en columnas», sin afirmar que sean años.

## 0.10.42 · 26/10/2026

- Motor multilente-0.10.38: la interpretación confirmada gobierna también las lentes, el conciliador y la lectura con IA. (1) Asociaciones (Rizoma) sobre observaciones independientes: las filas «Total», «Subtotal» o «Suma» quedan fuera y se informa cuántas; las diferencias entre períodos se calculan sólo con un eje temporal verificado (períodos únicos, completos, consecutivos y de una frecuencia; la confirmación prevalece sobre el nombre de la columna); entre categorías se habla de asociación positiva o inversa y se sugiere revisar muestra, composición y cobertura, no el período. (2) En un cuadro confirmado como estadística un importe puede ser un flujo neto: un «Total» negativo no se afirma imposible, el conciliador no lo reintroduce como reversa y con eje «ninguno» u «operaciones» no se buscan reversas. (3) Un cuadro confirmado sin eje temporal no activa el Cronista por un rol de período residual. (4) Pagos es un registro de operaciones de pago, no cualquier cuadro que mencione pagos o intereses. (5) La lectura de señales con IA recibe la interpretación confirmada de cada cuadro y respeta el eje de cada señal en un libro mixto.
- Historial y detalle: el historial recibe la cantidad de casos, los archivos de origen y el estado de la interpretación sin cargar los JSON completos; el detalle toma el estado de cada modelo del manifiesto sin inventar fallas; una lectura parcial no se presenta como no ejecutada; la fecha del reporte ejecutivo aclara «(UTC)».

## 0.10.41.8 · 25/10/2026

- Páginas públicas: los errores reales de publicaciones oficiales (validaciones de la ficha y el caso de gasto social de la presentación) se describen sin nombrar al organismo, la jurisdicción ni las cifras que lo identifican, para no exponer a nadie a un error público. El instituto de estadística sólo se nombra donde los errores se insertaron a propósito en copias de sus planillas públicas.

## 0.10.41.7 · 25/10/2026

- Presentación: el video de Gobernanza Multilente (5:25, canal de Open Lab en YouTube) se ve en la página, después del encabezado, con el reproductor sin cookies (youtube-nocookie.com) y un botón «Ver el video»; la política de seguridad de nginx admite sólo ese origen en frame-src.

## 0.10.41.6 · 25/10/2026

- Charla (/multilente): la filmina del recorrido en cinco pasos («La IA propone, las reglas comprueban, la persona decide.») tiene título y lista más compactos y entra completa en la pantalla también en notebooks; antes se cortaba entre 4 y 76 px de 1536×864 a 1280×720.

## 0.10.41.5 · 25/10/2026

- Lema «La IA propone, las reglas comprueban, la persona decide.» en la presentación, la charla, la ficha, la pantalla de confirmación, el lector del cuadro y el informe, en lugar de «La IA propone; la cuenta comprueba»; «Cómo funciona» pasa a cinco pasos alternados (la IA interpreta, la persona confirma, las reglas comprueban —con el conciliador, también por reglas—, la IA lee las señales ya calculadas conservando coincidencias y divergencias, la persona decide y queda registrado), y la revisión rápida usa sólo reglas y persona.

## 0.10.41.4 · 25/10/2026

- Documento metodológico v9.3, publicado en Zenodo el 25/10/2026 (10.5281/zenodo.23649172; la 9.2 era 10.5281/zenodo.23623905; serie 10.5281/zenodo.22063241): la ficha enlaza esta versión y las páginas citan la v9.3.

## 0.10.41.3 · 25/10/2026

- Gobernanza Multilente es un proyecto de OPEN LAB (Universidad Nacional de Quilmes): el pie de las páginas públicas lo dice («Proyecto de OPEN LAB (Universidad Nacional de Quilmes) en etapa piloto · Responsable: Maximiliano Pérez»), el código queda bajo licencia MIT (LICENSE en la raíz) y la metodología y la documentación bajo CC BY 4.0; la trayectoria y la ficha ya no lo llaman «independiente» al distinguirlo de la iniciativa premiada por el BID.

## 0.10.41.2 · 25/10/2026

- Pruebas: la batería corrida en la carpeta de producción, con su .env (SMTP y DOCENTE_AVISO_EMAIL), mandaba dos avisos reales «Nueva consulta en Caso» por corrida desde 0.10.40; ahora tests/conftest.py vacía el SMTP y los destinatarios, reemplaza el envío por uno que falla sin conectar y bloquea cualquier conexión a un puerto de correo, y una prueba lo fija con un SMTP «real» configurado. Sin cambios en el motor.

## 0.10.41.1 · 25/10/2026

- Páginas públicas: la presentación se reordena en seis secciones (no da veredictos; una segunda mirada, como una radiografía; revisión rápida y revisión profunda; echa luz donde no se miraba; probalo) y la ficha suma el recuadro «Qué cambia en el recorrido». Sin cambios en el motor (multilente-0.10.37): no se volvieron a medir los bancos.

## 0.10.41 · 24/10/2026

- «¿Qué resultó ser?», a la vista: en 832 señales hubo 0 respuestas, porque el botón estaba sólo en el anexo plegado y en ~1,2 minutos la gente bajaba el PDF y no volvía. Ahora cada uno de los cinco casos principales pregunta «¿Qué resultó ser? Error real · Dato correcto · Todavía no sé», con la misma respuesta de siempre (nada se borra, vale la última) y la aclaración de que sirve para medir la herramienta, no a la persona. El PDF cierra cada caso con «Respondé en la aplicación: ¿qué resultó ser esta señal?». Cada respuesta guarda la prioridad del caso y la versión del motor del momento. Al final del informe hay una pregunta de cierre («¿Corregiste algo del informe antes de entregarlo?» y «¿Encontraste errores que la herramienta no señaló?»), registrada en la bitácora; el historial la marca pendiente. Al cargar se puede marcar «Es una prueba (no cuenta para las mediciones)», y los ejemplos del catálogo se marcan solos. scripts/indicador_valor.py calcula, con cifras agregadas y sin pruebas, la precisión vivida («de las altas respondidas, cuántas eran error real», con su cantidad), el tiempo hasta la respuesta, la cobertura (por debajo del 70 %: «sin medición») y los informes en los que se corrigió algo.
- Migración 20261024_respuestas_prioridad (sobre 20261022_biblioteca_casos), con respaldo de la base antes de publicar. El primer intento de publicación no arrancó: el identificador original de la migración tenía 35 caracteres y la tabla alembic_version admite 32; se volvió a 0.10.40 en minutos, sin cambios en la base, y una prueba fija ahora el largo.
- Sin cambios en el motor (multilente-0.10.37): no se volvieron a medir los bancos.

## 0.10.40 · 24/10/2026

- Incubadora: cuando un participante escribe en el espacio docente, el docente recibe un correo «Gobernanza · Nueva consulta en <proyecto>» con el proyecto, la fecha y un enlace directo (#/proyecto-ia/<id>, que abre el proyecto en la vista docente). El correo no lleva el texto de la consulta ni datos de quien la hizo. Se manda después de guardar la consulta, así que una falla del correo no la afecta, y cada consulta genera un solo aviso, registrado en la bitácora. El destinatario se configura en DOCENTE_AVISO_EMAIL.
- Resumen diario de consultas sin respuesta (scripts/recordatorio_consultas_docente.py): las que llevan más de 2 días sin respuesta, todos los días a las 9 (hora de Argentina), en un solo correo; no se repite el mismo día.
- Sin cambios en el motor (multilente-0.10.37): no se volvieron a medir los bancos.

## 0.10.39 · 24/10/2026

- Seguridad de los datos en las dos revisiones. Se revisó en el código todo el recorrido de los datos. La revisión rápida no envía nada a proveedores de IA: no corren el lector del cuadro, ni la lectura de señales, ni la exploración. Lo único que sale del servidor es el aviso por correo de que terminó, con el número del informe y un enlace (si falla, también el mensaje del error). En la revisión profunda, las lectoras de IA reciben los rótulos y la estructura de cada cuadro con todas las cifras ocultas, años incluidos, y la lectura de las señales recibe los hallazgos del motor con sus valores. La pantalla de carga, la presentación, la ficha y la charla lo dicen así. Una prueba nueva corre la revisión rápida con toda salida de red prohibida y comprueba que el análisis termina y que el correo no lleva datos del informe.
- La ficha, la charla y la presentación decían que «la interpretación confirmada selecciona los controles». Desde 0.10.28 la interpretación con IA orienta y suma controles (presupuesto, ponderaciones, pagos, antecedentes, exploratorios) pero no apaga las cuentas, y en la revisión rápida no hay interpretación con IA: las frases se corrigieron, con una prueba que lo fija.
- Documento metodológico v9.2 publicado en Zenodo el 24/10/2026 (10.5281/zenodo.23623905; serie 10.5281/zenodo.22063241): la ficha enlaza esta versión.
- Sin cambios en el motor (multilente-0.10.37): no se volvieron a medir los bancos.

## 0.10.38 · 24/10/2026

- Incubadora: la entrega final ya no vuelve en silencio a una versión vieja. Al guardar el contexto, consultar al docente o hablar con el asistente, la pantalla reemplazaba el texto recién pegado (y todavía no guardado) por la última versión guardada; así, una entrega recortada en 16.000 caracteres por el tope anterior al 19/09 seguía apareciendo cortada. Ahora lo escrito se conserva con el aviso «Cambios sin guardar», y si sólo se guarda el contexto se avisa que la entrega tiene cambios pendientes. Entrega, contexto y consultas al docente admiten efectivamente 30.000 caracteres de punta a punta; la consulta al docente suma contador y control previo, el contador cuenta como el servidor y pasar el tope da un mensaje claro en castellano.
- Sin cambios en el motor (multilente-0.10.37): no se volvieron a medir los bancos.

## 0.10.37 · 24/10/2026

- Motor multilente-0.10.37, formato de las series de un ministerio. (1) Una fila de códigos de serie («84.2_IT_0_T_13») debajo de los rótulos es un metadato: no se toma como rótulo ni como dato, y el cuadro trimestral que sólo trae códigos toma los rótulos del cuadro de arriba. (2) Trimestres romanos con año de dos o cuatro dígitos («I-94», «III-01», «1T93»); la serie cruza el 2000 sin cortar el orden. (3) Un «Total» en un nivel intermedio de un encabezado de varios niveles («Sector Bancario» · «Total Sector Bancario») se controla contra su panel. (4) Un saldo neto con los egresos en positivo (operaciones con el FMI: Total = Ingresos − Egresos) no es un total que no cierra.
- Prueba con la hoja real «14. Bce Pagos 3-17» (planilla_oficial, sin alterar; las pruebas alteran W106 y X106 en memoria, como las copias del banco): el «Total Sector Bancario» alterado de un trimestre se señala en su celda.
- Medición antes de publicar: 123 errores insertados, 115 detectados en su celda con prioridad alta, ninguno perdido; 132 planillas oficiales publicadas, 172 señales altas, ninguna distinta de la 0.10.36. Los libros de las series de un ministerio del banco superan el tope de celdas y se siguen rechazando al cargarlos, así que este arreglo todavía no mueve esas cifras. De los 8 posibles errores reales, el motor marca los 8, 7 con prioridad alta.

## 0.10.36 · 24/10/2026

- Motor multilente-0.10.36, arreglos de lectura de planillas publicadas. (1) Paneles con un total propio repetido (una jurisdicción, estadística 9): cada panel se concilia con su total. (2) Años arriba de una fila que sólo dice la unidad («En millones de pesos», una jurisdicción): los años son el encabezado. (3) Cronogramas de deuda pública de un ministerio: paneles [instrumento, CAPITAL, INTERÉS] sin total arriba y con TOTAL al pie que los suma; un componente leído por la sangría sólo cierra donde vale 0; en hojas cuyo título dice «perfil de vencimientos» o «cronograma de …», un pico, salto o valor repetido en una celda que cierra exacto y no participa de ninguna suma que no cierra queda con prioridad media (evidencia «cierre_exacto»). (4) Una fila de categoría sin período no es una fila repetida, las filas «Como % del total» entre importes no son un cambio de escala y el ruido de punto flotante no cambia el signo.
- Se descartó el ajuste del tope del 15 % de «total de columna» por una parte corrida ×/÷ 10, 100 o 1000: detectaba un error insertado más (una jurisdicción, planilla 4), pero sumaba 43 falsas alarmas en planillas publicadas (instituto de estadística censo y pobreza, una jurisdicción permisos de edificación).
- Medición antes de publicar: 123 errores insertados, 113 → 115 detectados en su celda con prioridad alta, ninguno perdido; 132 planillas oficiales publicadas, 255 → 172 señales altas (88 planillas sin ninguna). Se fueron 84, casi todas de los cronogramas de deuda pública de un ministerio; la única nueva es el posible error real de una jurisdicción («Varios» 2016), ahora también como identidad entre cuadros. De los 8 posibles errores reales, el motor marca los 8, 7 con prioridad alta.

## 0.10.35 · 24/10/2026

- Dos revisiones. La **revisión rápida**, la opción por defecto, pasa los rayos X a todo el libro: sólo cuentas, sin IA y sin confirmación, en segundos. La **revisión profunda** es el recorrido de siempre: la IA interpreta cada cuadro, la persona confirma y corren todas las lentes.
- Motor e informe: la carga recibe `modo_revision` («rapida» por defecto, «profunda»). La rápida registra sola una interpretación con el plan aritmético —totales, coherencia, fórmulas, relaciones, conciliación, series y controles solicitados; presupuesto sólo si se declaró el dominio presupuestario—, que la barrera de confirmación valida como cualquier otra; alterarla la invalida. No corren el lector del cuadro con IA, la lectura de señales con IA, los antecedentes (Radiólogo), los cruces entre documentos y entre ediciones (Orquesta, ediciones), las asociaciones exploratorias (Rizoma, patrones) ni el Matemático de pagos. No consume el cupo diario de análisis con IA.
- El informe, el PDF y el comprobante dicen en la primera línea qué revisión fue; en la rápida, también qué no corrió («Revisión rápida: sin IA. No se corrieron: …»). Queda en el saneamiento (`modo_revision`) para la pantalla y el historial.
- Pantalla: en «Analizar», «Revisión rápida» («Sólo cuentas, sin IA. Segundos. Sirve para cualquier tamaño de libro.») como acción principal y «Revisión profunda» («La IA interpreta cada cuadro, vos confirmás y corren todas las lentes. Minutos.»). Al final del informe de una rápida, «Pasar a revisión profunda» reenvía los mismos archivos elegidos, sin volver a pedirlos; si se recargó la página, lo dice y pide elegirlos de nuevo. El encabezado del informe, el historial y el análisis en vivo dicen qué revisión fue; los informes anteriores figuran como profunda. Los ejemplos siguen mostrando el recorrido completo.
- Los 8 ejemplos con error de la aplicación: la rápida detecta 7 y los 8 correctos salen sin hallazgos, sin ninguna llamada a la IA. El octavo es una asociación exploratoria (Rizoma): sólo lo ve la profunda, y el informe rápido lo declara.
- Páginas públicas: la presentación, la charla y la ficha técnica cuentan los dos niveles; la ficha trae la tabla de qué corre en cada una. Las mediciones publicadas (113 de 123) son del motor sin la lectura con IA, es decir, de lo que corre en la rápida.

## 0.10.34 · 24/10/2026

- Motor multilente-0.10.34: una columna «Período» con el año y el mes guardados como número (2023.11) se sumaba como una cantidad más, el «Total» nunca cerraba y el control se abandonaba. Las columnas cuyo rótulo es sólo un período (Período, Año, Mes, Fecha, Trimestre, Semestre) no entran en ninguna suma; «Ejercicio 2025» o «Año 2023» siguen siendo datos.
- Medición antes de publicar: 123 errores insertados, 111 → 113 detectados en su celda con prioridad alta, ninguno perdido; 132 planillas oficiales publicadas, 255 señales altas y ninguna distinta de la 0.10.33.

## 0.10.33 · 24/10/2026

- Motor multilente-0.10.33. (1) Triangulación en los paneles «Total»: si la fila no cierra contra su total y la columna de un componente tampoco cierra contra la fila «Total», por la misma diferencia, se señala la celda donde se cruzan (antes se señalaba el total de la fila, y la celda alterada quedaba sin nombrar). (2) Un total que no cierra por 1 % o más (antes 5 %), con la evidencia aritmética exacta, es prioridad alta aunque pese poco en el cuadro: es un hecho, no una sospecha.
- Medición antes de publicar: 123 errores insertados, 106 → 111 detectados en su celda con prioridad alta, ninguno perdido; 132 planillas oficiales publicadas, 255 señales altas y ninguna distinta de la 0.10.32.

## 0.10.32 · 24/10/2026

- Motor multilente-0.10.32: un valor con decimales en una columna de conteos (personas, establecimientos, delitos) en la que los demás son enteros —19,54 establecimientos, 51,47 inscriptos— se señala con prioridad alta. Hace falta que la columna tenga ocho o más enteros distintos de cero; no cuentan el ruido de punto flotante de Excel (57,99999999999999 es 58) ni las celdas con fórmula.
- Medición antes de publicar: 123 errores insertados, 100 → 106 detectados en su celda con prioridad alta, ninguno perdido; 132 planillas oficiales publicadas, 255 señales altas antes y después.

## 0.10.31 · 24/10/2026

- Motor multilente-0.10.31. (1) Una columna «Tipo de población usuaria · Cliente oficial» (una categoría de usuarios de energía, con consumos de ocho cifras) se excluía por el filtro de privacidad como si fuera un cliente identificado o un DNI, y el total de cada mes dejaba de cerrar: un rótulo «Tipo de …» con cifras nombra una categoría y no se excluye (lo nominal —nombre, DNI, CUIT— se sigue excluyendo siempre). (2) Un total publicado con menos decimales que sus partes (11.876.225.248 contra partes con cinco decimales) puede diferir de la suma en una unidad de su último decimal: no se señala.
- Medición antes de publicar: 123 errores insertados, 97 → 100 detectados en su celda con prioridad alta, ninguno perdido; 132 planillas oficiales publicadas, 252 → 255 señales altas. Entre las nuevas, un posible error real en la energía facturada de una jurisdicción: en agosto de 2021 el total supera la suma de los tipos de usuario en exactamente 300.000 kWh, y el total anual 2021 arrastra la misma diferencia. No se comunicó al organismo.
- Quedan sin detectar 23 de 123: 7 están en dos libros de un ministerio de más de 1,2 millones de celdas, que se rechazan al cargarlos por el tope de 600.000 (declarado, no silencioso).

## 0.10.30 · 24/10/2026

- Motor multilente-0.10.30, segunda ronda para detectar nuestros errores insertados. (1) Con los años en filas y las variables en columnas (Total · Estatal · Privado), «Total = suma de su panel» no se controlaba en ninguna fila: ahora sí, con la relación que declara el rótulo. (2) Una columna «Contra las personas» (un tipo de delito) con cifras y «-» se excluía por el filtro de privacidad como si fuera un dato personal, y el total del cuadro dejaba de cerrar: las marcas de sin dato ya no vuelven sensible una columna de conteo. (3) «Distribución relativa» (porcentajes) no se suma.
- Medición antes de publicar: 123 errores insertados, 90 → 97 detectados en su celda con prioridad alta, ninguno perdido; 132 planillas oficiales publicadas, 249 → 252 señales altas: una es el posible error real de una jurisdicción (cargos docentes 2021, ahora en alta) y dos son totales de exportaciones de una jurisdicción 2011 y 2015 que no cierran por 0,42 y 0,50 millones. De los 8 posibles errores reales, el motor marca los 8, 7 con prioridad alta.

## 0.10.29 · 24/10/2026

- Motor multilente-0.10.29, para que detecte nuestros propios errores insertados. Tres causas por las que totales alterados a propósito no se veían: (1) una columna con muchos «-» (sin dato) se tomaba como texto y no se controlaba; (2) con varias columnas «Total» en paneles (Estudiantes · Total, Varón, Mujer; Egresados · Total, Varón, Mujer) el control de «Total = suma de sus partes» se abandonaba; (3) la fila «Total» arriba de su grupo no se sumaba por columna. Ahora las tres se controlan.
- Resguardos para no sumar alarmas: no se señala una fila cuya diferencia es exactamente otra columna del cuadro (Población = particulares + colectivas + en situación de calle), una con una parte no publicada («---»), una distribución que declara 100 y suma 99,8, ni las columnas de límites del intervalo de confianza («LI», «LS») o coeficiente de variación.
- Medición antes de publicar: 123 errores insertados, 79 → 90 detectados en su celda con prioridad alta, ninguno perdido; 132 planillas oficiales publicadas, 249 señales altas antes y después (89 sin ninguna). De los 8 posibles errores reales de la revisión del 22/10, el motor marca los 8 (recupera el de una jurisdicción, que antes sólo veía la lectura con IA) y el de una jurisdicción («Varios» 2016) ahora también como total que no cierra.

## 0.10.28 · 24/10/2026

- Regresión grave corregida. Desde la 0.10.1, la interpretación previa con IA decidía qué controles correr y, si la IA clasificaba un cuadro como «otro» o «desconocido», apagaba todas las cuentas; si decía «régimen no determinado», el presupuesto dejaba de controlarse. En producción, 4 de los 8 ejemplos con error de la aplicación salían sin ningún hallazgo (pagado mayor que devengado, devengado mayor que el crédito, fórmula alterada, avance financiero sin avance físico). Las pruebas no lo veían porque simulaban una IA que siempre respondía «presupuesto público».
- Ahora las cuentas no dependen de la IA: totales, coherencia, fórmulas, relaciones, conciliación y, si hay períodos, series corren siempre, también si las tres lectoras fallan. La interpretación sólo suma los controles que necesitan saber qué es el cuadro (presupuesto, ponderaciones, pagos, antecedentes) y los exploratorios. «No determinado» no es privado. Si la IA no sabe qué es el cuadro y quien cargó declaró el dominio (presupuestario, servicios), vale lo declarado.
- Los informes confirmados antes reciben el plan vigente al reanalizarse, sin volver a confirmar; queda registrado en su historial.
- Prueba nueva con una IA simulada que duda o no reconoce nada: los ejemplos con error se detectan y los correctos siguen sin señales.

## 0.10.27 · 24/10/2026

- Ficha técnica: los recuadros «En cinco frases» y «Qué podés esperar, medido» de la cabecera salían con letra casi blanca sobre fondo claro, porque una regla de la página de detalle pisaba la de 0.10.25; ahora la letra es oscura en todos los temas.

## 0.10.26 · 24/10/2026

- La ficha técnica cita el documento metodológico v9.1, publicado en Zenodo el 24/10/2026 (10.5281/zenodo.23609356): el mismo texto de la v9 con las mediciones descritas como en la 0.10.25 (copias alteradas a propósito, planillas publicadas sin alterar, ocho posibles errores con su fecha). La descripción del registro v9 también se corrigió.

## 0.10.25 · 24/10/2026

- Revisión de veracidad de las páginas públicas. «Qué podés esperar, medido» dice ahora exactamente qué se midió: el 79 de 123 es sobre copias de planillas oficiales con un error insertado (casi 2 de cada 3); el 90 de 132 es sobre planillas oficiales publicadas, sin alterar, que no son «correctas» por definición: entre ellas están los posibles errores reales. Las 951 → 249 son señales altas, no todas falsas alarmas. Los 8 posibles errores salen de la revisión del 22/10/2026 (aplicación 0.10.3); el motor 0.10.23, sin la lectura con IA, sigue marcando 7 (5 en prioridad alta y 2 en media) y el octavo (una jurisdicción) había salido de una relación leída por IA. «Cada informe empieza diciendo qué pudo leer y qué no», como hace el comprobante.
- Ficha técnica: documento metodológico v9, publicado en Zenodo el 24/10/2026 (10.5281/zenodo.23608946); 83 pruebas de JavaScript; el recuadro de la cabecera, que salía con letra clara sobre fondo claro, se lee.
- Charla: edición actualizada al 24/10/2026.

## 0.10.24 · 24/10/2026

- Mensaje único en la aplicación (inicio y pantalla de carga, también en modo básico), la presentación, la charla y la ficha técnica: Gobernanza es una segunda mirada, como llevarle una radiografía a otra persona, que te dice qué parte pudo mirar y cuál está borrosa, te señala la mancha rara y te pide que lo verifiques. En cinco frases: le traés un informe; primero te dice qué pudo leer y qué no, y sobre lo que no leyó no opina; en lo que leyó hace las cuentas y busca lo raro; te marca la celda y te sugiere qué preguntar, sin afirmar que es un error; la decisión es tuya.
- Qué se puede esperar, medido el 24/10/2026 con el motor multilente-0.10.23: avisa lo que no mira (cada informe empieza por lo que no pudo leer o controlar); en 79 de 123 planillas oficiales con un error escondido lo señala (2 de cada 3) y en planillas publicadas encontró 8 posibles errores con la cuenta a la vista; 90 de 132 planillas oficiales correctas salen sin ninguna señal de prioridad alta (las falsas alarmas bajaron de 951 a 249). No promete encontrarlo todo. La ficha técnica conserva todas las mediciones y aclara con qué vara se leen: con la de un auditor (que no se le escape nada) ninguna versión cumplió; con la de una segunda mirada, para la que está hecha, la 0.10.23 es usable.

## 0.10.23 · 23/10/2026

- Motor multilente-0.10.23: si la hoja o el título del cuadro declaran variaciones («Variaciones_Anual», «Tasa de variación interanual»), un valor de signo distinto se sigue registrando —puede ser la huella de un error de la hoja base que se propaga— pero con prioridad media, porque en una hoja de variaciones un negativo entre positivos suele ser normal. una jurisdicción, gobierno 1: 17 de sus 18 «signo aislado» estaban en la hoja de variaciones y dejan de ser ALTA; el que queda («Otros tributarios», −733,82 en el 2T 2025, un ingreso tributario negativo) sigue en alta.

## 0.10.22 · 23/10/2026

- Motor multilente-0.10.22, «valor fuera de la escala de su columna» en las series de deuda pública de un ministerio: un mismo valor en tres o más filas (el residuo 0,00001 de varios bonos) es una convención de carga, no un error de escala, que sería un dato suelto; y la columna «Total» de cada fila (perfil de vencimientos) mezcla por construcción el total general, los subtotales y cada préstamo, así que la regla no se aplica ahí.
- Medición antes de publicar: 132 planillas oficiales correctas, casos ALTA de 332 a 266 (sólo cambian las 6 ediciones de deuda pública, 11 menos cada una); 123 errores insertados, 79 detectados antes y después (ninguno perdido).

## 0.10.21 · 23/10/2026

- Motor multilente-0.10.21: en una columna que suma 100 (distribución porcentual, como «Mujeres por grupo de edad»), una participación chica (0,1 %, 0,6 %) es natural y ya no se marca como «valor fuera de la escala de su columna». Lo mismo en una fila que es una distribución (trae su 100 y el valor tiene su complemento, como «No madres» 96,3 + «Madres» 3,7). Un valor anormalmente grande se sigue marcando. una jurisdicción, estadística 27: 16 casos pasan a 0.

## 0.10.20 · 23/10/2026

- Motor multilente-0.10.20: lo que la 0.10.19 decía y no hacía del todo. Una columna con años y sus meses debajo («2010» vacío, «Enero» … «Diciembre», «2015» vacío, …) ya no se marcaba como «año no entero», pero se seguía armando como una serie y cada fila de año, sin datos, era una «celda vacía» entre dos meses. Ahora esa columna no se arma como serie vertical. una jurisdicción, estadística 18: 80 casos pasan a 0.

## 0.10.19 · 23/10/2026

- Motor multilente-0.10.19: la mayor fuente de falsas alarmas en planillas oficiales correctas era «año no entero» (504 de 932 casos ALTA del banco), en dos formatos oficiales comunes.
- Años con sus meses (o trimestres, semestres) debajo, en la misma columna («2010», «Enero» … «Diciembre», «2011», …): cada mes se marcaba como un año no entero. Ahora no se marca nada y la columna no entra en los controles temporales, porque mezcla totales anuales y meses. una jurisdicción, estadística 17 y 18: 200 casos cada una pasan a 0; estadística 8: 36 a 0.
- Año.mes como número (2021.04; 2021.1 es octubre; 2021.11): se valida como serie mensual (duplicados y retrocesos sobre el mes). una jurisdicción, comercio exterior 1: 68 casos pasan a 0.
- Un año con decimales en una serie anual (2017,5) sigue siendo una señal.

## 0.10.18 · 23/10/2026

- Motor multilente-0.10.18: falsas alarmas de encabezados en planillas oficiales correctas.
- Llamada de nota sola en el encabezado («(1)», «(2)», «(a)», «(*)», «²»): es una columna de notas entre los años, no un período. Antes «(2)» se leía como −2 (paréntesis contables) y cada celda vacía de esa columna era una «celda vacía dentro de la serie»: en la encuesta de hogares de un instituto de estadística (planilla_oficial), 184 casos ALTA pasan a 1.
- Encabezado de dos niveles variable × año (una jurisdicción: Producción, Superficie y Plantas sobre 2014 y 2017): las columnas que el modelo no asignó a una variable toman el rótulo combinado de arriba, y cada variable se lee como su propia serie. Anuarios 7, 8 y 9 de una jurisdicción: 4 «año duplicado» cada uno pasan a 0; una jurisdicción, gobierno 1: 3 «año duplicado» falsos desaparecen.
- «Ahorro» y los rótulos de resta de romanos («(I-II)», «(III - IV)») declaran un resultado y admiten cualquier signo, como «Resultado», «Superávit» o «Déficit».
- Medición antes de publicar: 132 planillas oficiales correctas, casos ALTA de 951 (49 planillas) a 934 (46); 123 errores insertados, 79 detectados antes y después (ninguno perdido). Los semestres bajo años de la encuesta de hogares (planilla_oficial) siguen pendientes.

## 0.10.17.1 · 23/10/2026

- Informe de revisión (PDF): cuando la página 1 se llenaba justo antes del salto, los espacios del final pasaban solos a una hoja nueva y el salto dejaba esa hoja en blanco. Ahora se quitan los espacios sueltos antes del salto y el salto no actúa sobre una página vacía. Informes 351 y 357: de 7 a 6 páginas; 356: de 8 a 7; ninguna en blanco.

## 0.10.17 · 23/10/2026

- Lectura previa: si una lectora de IA falla (tiempo agotado, límite de uso, respuesta cortada), se reintenta dos veces con espera (5 y 15 segundos) antes de darla por caída, y el error dice de qué tipo fue. En el reanálisis del libro por provincia (informe 356), Gemini falló en 46 tramos; esos mismos cuadros, pedidos de nuevo, se leyeron en 15 y 23 segundos.
- Analogía entre cuadros iguales: un campo sin acuerdo de dos lectoras toma el valor que acordaron al menos dos cuadros con los mismos encabezados de datos (pueden diferir sólo en la columna de rótulos), siempre que alguna lectora de ese cuadro también lo haya propuesto; nunca inventa un voto. Queda declarado en `por_analogia` y la pantalla de confirmación muestra esos cuadros sueltos para revisar, igual que los que quedaron sin eje temporal. En el 356: los 23 cuadros «sin determinar» (GPT dijo «sin eje», DeepSeek «años en columnas», Gemini falló) pasan a «años en columnas», como los otros 145.

## 0.10.16 · 23/10/2026

- Modo básico y modo avanzado (interruptor «Modo avanzado» en el encabezado; la elección se recuerda en el navegador; por defecto, básico). El modo básico oculta, sin borrarlo: el texto largo del encabezado; en el menú, Validación, Calibración y Marco; en el inicio, los avisos y los pasos de cada recorrido; en la carga, las ayudas largas, el aviso por correo, el modo de uso y las opciones avanzadas (quedan los archivos, «¿De quién es el informe?» y la pregunta opcional); en el informe, «Cómo se leyó el archivo», «Ver todo el detalle», «Consultar datos analizados» y el contador de hallazgos (queda la tarjeta con los casos y la descarga del informe). Si el lector espera una respuesta, la pregunta se muestra igual.
- La tarjeta del informe mostraba el texto técnico de las variaciones anuales que pasan a ser caso («[una jurisdicción · cuadro 63] … 139.1 veces el movimiento típico…»); ahora usan su frase llana, como en el PDF.

## 0.10.15 · 23/10/2026

- Lo que el lector del cuadro no pudo leer se dice en una línea: «lector del cuadro en 46 tramos de 23 hojas («una jurisdicción», … y otras)», con la falla más frecuente de cada lectora («gemini: El proveedor no completó la lectura»). Antes era una línea por tramo con «filas []»: en el informe 356, unas 50 líneas que desbordaban la página 1.
- Si los controles no se ejecutan porque fallaron las condiciones de validez, el informe lo dice arriba («Controles sin ejecutar: condiciones de validez no cumplidas: cambio de esquema detectado respecto del informe anterior») y en cada control, en lugar de «sin motivo registrado» y de «la pregunta declarada no pudo evaluarse» cuando no había pregunta. Visto en el informe 355, cargado con el 351 como informe anterior.

## 0.10.14 · 23/10/2026

- Consulta transversal (etapa 3 de la revisión externa del informe 351): si en un mismo período hay saltos o cambios de escala en tres o más hojas, se reúnen en una sola consulta que va primero: «En 2018 hay saltos o cambios de escala en 4 hojas a la vez (varias jurisdicciones): ¿cambió en 2018 la metodología, la cobertura o la clasificación de los datos?». Los casos quedan como su evidencia, con la cantidad de variaciones anuales de contexto de ese año. Una fila que oscila varios años seguidos no cuenta como salto de un año. En el informe 351: 2018 (4 hojas) y 2015 (3 hojas). Sólo cambia cómo se presentan las consultas; el motor y la prioridad de cada caso no cambian.

## 0.10.13 · 23/10/2026

- Motor multilente-0.10.13 (etapa 2 de la revisión externa del informe 351).
- Reclasificación entre categorías: cuando un componente salta o cae y, el mismo período, otros componentes del mismo total se mueven en sentido contrario y fuera del ritmo del total (más de 1,5 veces lo que crece o cae el total, o menos de 2/3), cubriendo al menos la mitad del desvío, con el total cerrando en los dos períodos, la evidencia lo registra y la consulta pregunta «¿se reasignaron partidas entre categorías en 2017?» en lugar de «¿se cargó con la coma corrida?». Con inflación todas las categorías suben: crecer al ritmo del total no cuenta como compensación, y movimientos menores a la décima parte del desvío no se nombran. Si el total no cierra, la hipótesis no se habilita. Libro por provincia: una jurisdicción 2017, varias jurisdicciones 2012, varias jurisdicciones 2018.
- Prioridad: un patrón (no una cuenta exacta) con impacto medio llega a ALTA sólo si pesa al menos 0,5 % del total del cuadro (una jurisdicción «BP» 2002, 0,16 %, pasa a media); un extremo de serie sin vecino posterior con impacto alto (1 % o más) ya no baja a media sólo por ser el último año (varias jurisdicciones 2018; una jurisdicción 2001).
- Medición antes de publicar: 132 planillas oficiales correctas, 951 casos ALTA en 49 planillas con y sin los cambios; 123 errores insertados, 79 detectados con y sin los cambios (ninguno perdido ni ganado); 14 compensaciones registradas en planillas correctas. Las reglas sólo actúan donde hay un total que cierra con series largas.

## 0.10.12.1 · 23/10/2026

- Informe de revisión: «No se controló» agrupa los lugares que comparten el mismo motivo (varias jurisdicciones) y, con un solo archivo, no repite su nombre en cada punto. En el libro de 168 cuadros la página 1 entra completa (antes desbordaba dos líneas a una página casi vacía).

## 0.10.12 · 23/10/2026

- «Confirmá qué contiene el informe»: con más de tres cuadros, la pantalla dice cuántos cuadros y hojas hay y los resume por tipo, institución y régimen («172 cuadros: presupuesto · organismo público · régimen público»). Cada cuadro sigue disponible en «Ver los N cuadros uno por uno», que se abre al elegir «No, modificar». Los cuadros sin acuerdo entre lectoras, sin clasificar o con una lectora fallida se muestran siempre, fuera del plegado. Antes la pantalla listaba los 172 cuadros de un libro por provincia, casi todos iguales.
- Informe de revisión (PDF): abre con las consultas al área. Antes, en un libro de 168 cuadros, la interpretación de cada cuadro ocupaba 35 de 42 páginas y las consultas aparecían en la 36. Ahora la interpretación va al anexo resumida por tipo («168 cuadros: presupuesto · organismo público · régimen público · años en columnas»), con las excepciones; el detalle por cuadro queda en el detalle técnico. El aviso de lectura parcial se dice una vez arriba y su detalle sigue a las consultas (antes salía dos veces con el mismo texto). Sin identificadores internos («ia_confirmada», «organismo_publico», «escala extremo», nombres de lentes sin tilde). «Qué pasó» del salto de escala final con sus números (antes, una frase genérica), y el salto anual dicho en veces («se multiplica por 6,1») en lugar de «139,1 veces su movimiento habitual». Los conteos dicen de dónde salen: 235 variaciones = 228 de contexto + 7 en casos; la IA, sobre cuántas señales registradas. Sin cambios en el motor ni en las señales.

## 0.10.11 · 23/10/2026

- El informe abre con una sola tarjeta: cuántos casos hay para revisar, cuántos de prioridad alta y los cinco principales, cada uno con su celda, su explicación en lenguaje llano y «Ver origen y evidencia». Si la lectura fue parcial, una línea lo dice. Las cifras, la lectura ejecutiva, las lentes, la cobertura, las descargas y la evaluación siguen disponibles, plegadas en «Ver todo el detalle». Antes la pantalla mostraba nueve bloques a la vista y los mismos casos aparecían tres veces. Los pasos 1·2·3 se ocultan cuando el resultado está listo. Cómo se leyó el archivo (la interpretación de cada cuadro y lo que quedó fuera de la lectura) también queda plegado, salvo que el lector espere una respuesta; lo que quedó fuera se nombra una sola vez por hoja y motivo, no una por tramo.

## 0.10.10 · 23/10/2026

- Mientras se analiza un informe, la pantalla consulta cada 4,5 s sólo el estado del trabajo y pide el informe completo una vez, al terminar. Antes pedía el informe completo en cada consulta: con el libro de 172 cuadros eran 8,5 MB cada 5 segundos (64 pedidos, más de 500 MB, en un análisis), lo que cargaba al servidor y al navegador y provocó un corte. Un corte aislado se reintenta sin aviso; el aviso aparece si se repite.

## 0.10.9 · 22/10/2026

- Libros enormes: la detección de encabezados usaba el libro ya abierto en lugar de reabrir el archivo en cada hoja. Con planilla_oficial (13 hojas, casi 700.000 estilos) la lectura bajó de más de 4 minutos sin terminar a 89 s, y el motor completo tarda 185 s (antes, horas). La tabla de períodos reconoce la serie por identidad y no rearma su clave en cada punto. En las 132 planillas del banco los resultados son idénticos a los de la 0.10.8.

## 0.10.8 · 22/10/2026

- «Cancelar lectura» mientras se interpreta el archivo: quien la pidió (o administración) la cancela; la lectura en curso se detiene en el próximo cuadro leído, las que faltaban no se piden a los modelos, no se ejecutan controles, el trabajo no se retoma al reiniciar y no se avisa por correo como error. La pantalla lo informa como cancelación, también si se canceló desde otra pestaña.

## 0.10.7 · 22/10/2026

- Libros grandes: la interpretación previa lee tres cuadros a la vez y un cuadro idéntico en otra hoja (el mismo cuadro por provincia) reutiliza la lectura, declarada en `lectura_compartida`; la pantalla muestra «Cuadros leídos: N de M». Antes, un libro de 27 hojas y 172 cuadros (Gasto Público Social) quedaba cerca de una hora en «Interpretando el archivo…» sin avance visible. La espera ya no se abandona por un corte breve del servidor.
- Falsas alarmas que la 0.10.6 dejó a la vista al leer bien encabezados de dos niveles, en planillas oficiales correctas: un encabezado con los años arriba y los meses abajo (con una columna «Subtotal 2025» en el medio) se lee como período mensual con su año, y «Enero» después de «Diciembre» ya no rompe la secuencia; en una serie intermitente (pagos o vencimientos con ceros entre los montos) un mes chico no es un pico, salvo que sobresalga de toda la serie; un saldo que baja antes de cancelarse (el período siguiente en cero) no es un valor aislado, y una serie intermitente tampoco da valor aislado por un mes chico; con meses abajo no se cuentan los espacios iniciales como sangría (eso queda para año + trimestre); una columna «Diferencia» no tiene escala propia, como «Variación».
- Las pruebas fijan siempre su base temporal, aunque el entorno traiga la de producción.
- Verificación con IA real en una base aislada (cuadro 4 de un censo nacional, 0.10.6 + estos cambios): original sin señales; copia alterada con la celda nombrada por el motor y la cuenta del lector en el mismo caso.

## 0.10.6 · 22/10/2026

- Encabezados de dos niveles: cuando «Código», «Jurisdicción» o «Total» están combinados con la fila de abajo y los tipos van debajo de un título que los abarca (un censo nacional, viviendas colectivas), esa fila de rótulos pasa a ser parte del encabezado. Las columnas dejan de llamarse «columna_5…» y la fila deja de leerse como dato. Una fila de unidades («pesos», «%») no se suma: sigue como metadato.
- El cruce fila × columna del motor reconoce también el total que va arriba de sus filas («Total» del país y después las jurisdicciones). Con un componente alterado, nombra la celda y el valor con el que cerrarían los dos totales. Si esa celda no tiene un número publicado (vacía o «s»), no se la nombra, se baja la prioridad y la carga ya no se cae; si la fila de total cierra en todas las columnas, se nombra el total de la fila.
- Lector del cuadro: dos cuentas que no cierran por la misma diferencia y comparten una sola celda nombran esa celda, si corregida cierran las dos y la otra cuenta también está controlada. Sus señales llevan el archivo de origen, así que se agrupan con las del motor sobre la misma celda en un único caso.
- Prueba de punta a punta en producción (0.10.5) con el cuadro 4 de un censo nacional: original sin señales; copia con un componente alterado detectada con tres señales sueltas. Con esta versión, una sola consulta sobre la celda. En 132 planillas oficiales correctas del banco, las alarmas altas del motor pasan de 1.130 a 1.010 (139 menos y 19 nuevas en planillas que ya tenían alarmas); ninguna triangulación nueva.
- Presentación, charla y ficha técnica: la repetición de 93 Excel se atribuye a la versión con que se hizo (0.10.1 y 0.10.3), se agregan las señales altas en originales sin revisar y se aclara que el conciliador presenta las señales del lector.

## 0.10.5 · 22/10/2026

- Todo cuadro con interpretación confirmada, análisis terminado y fuente vinculable entra automáticamente como antecedente de lectura para el mismo usuario, sin propuesta ni aprobación adicional. Se recupera sólo el perfil estructural y los controles ejecutados; nunca cifras ni conclusiones sobre errores.
- Una coincidencia estricta de cabeceras puede orientar la siguiente lectura, aun con un solo caso, como pista débil. La persona confirma la interpretación del nuevo informe y las reglas determinísticas hacen las cuentas. La propia fuente no se cuenta como antecedente.
- Los casos públicos con resultado evaluado siguen un proceso separado de revisión de evidencia. Sólo éstos pueden compartirse como antecedentes entre usuarios. La biblioteca no reentrena pesos ni constituye validación externa.

## 0.10.4 · 22/10/2026

- Biblioteca de casos de informes públicos: desde un cuadro interpretado y analizado se propone un caso con fuente original, resultado y fundamento; administración verifica la evidencia y lo aprueba o rechaza. Sólo los aprobados cuentan.
- Las señales requieren una respuesta compatible de quien hizo el informe. Los casos sin señal y las omisiones exigen un localizador revisado. Se conservan la huella de la fuente, el perfil confirmado y la versión del código.
- Se muestran los antecedentes comparables por control, sin contar variantes del propio archivo. Con al menos dos fuentes independientes de iguales cabeceras y lectura confirmada coincidente, los modelos reciben una orientación semántica enmascarada antes de proponer; la persona confirma el resultado y las reglas siguen haciendo las cuentas.
- Los 93 archivos de ensayo no se incorporan como casos revisados. El banco comienza vacío y crece sólo con revisiones explícitas. No se presenta como entrenamiento de pesos ni como validación externa ciega.

## 0.9.25.1 · 21/10/2026
- Canasta de crianza de un instituto de estadística: se conservan los encabezados combinados de varios niveles y los grupos de edad. Año y mes se leen juntos antes de buscar períodos aislados; se conservan los duplicados reales para su control.
- El inventario temporal cuenta las doce series mensuales por sus coordenadas. Las edades de los grupos no se confunden con fechas. Al recuperar el eje temporal dejan de aplicarse ocho alertas de Benford que no correspondían.
- El control de evolución conserva el año dentro del grupo de meses, sin inventarlo al reiniciar un ciclo. Usa los 81 meses en lugar de sólo los eneros y conserva las coordenadas de cada salto.
- El reporte ejecutivo llama temporales a los cambios de distintas frecuencias; no presenta cambios mensuales como anuales.
- Regresión del archivo público original, protegido por SHA-256; cifras intactas, grupos identificados y control positivo de mes duplicado. La versión del lector ciego y su pedido siguen en lector-1.3.

## 0.9.25 · lector 1.3 · motor multilente-0.9.20 · 21/10/2026

Correcciones a partir de la prueba con la serie pública de supermercados de un instituto de estadística:

- Las filas de unidades se separan de las observaciones y conservan la unidad de cada columna. Un índice de texto sin cifras se registra como estructura leída.
- Benford se abstiene automáticamente en cuadros con eje temporal y declara el motivo. Se conservan los controles aritméticos, las fórmulas y la detección en importes sin eje temporal.
- El lector admite hasta 512 columnas, divididas por separadores vacíos en bloques con coordenadas originales y eje textual compartido. Un cuadro contiguo no se corta por la mitad. Los límites de filas y celdas siguen declarados; se evita recorrer miles de filas vacías por hoja.
- El lector figura también en el PDF, Markdown y comprobante, incluso con cero señales. Las omisiones y las fallas de proveedores afectan el registro de cobertura. La pantalla permite consultar los bloques de columnas y filas leídos.
- Al reanalizar una lectura parcial se consultan sólo las lectoras que fallaron o faltan; las respuestas válidas permanecen en caché. Un límite temporal de un proveedor no queda fijado para siempre en el informe.
- Las consultas temporales se describen como señales que requieren contexto. Se conserva el rótulo geográfico «24 partidos del Gran una jurisdicción».
- La comparación de unidades entre columnas se limita al eje de períodos; importes y porcentajes de variables diferentes no se confunden con cambios de unidad. La lectura de señales de DeepSeek dispone de 4096 tokens y puede ampliar una vez la salida ante un corte, conservando el diagnóstico y sin superar dos intentos.
- Regresiones con controles positivos: errores más allá de la columna 80, restauración del original, celdas mal escritas conservadas, límites declarados, pertinencia de Benford y cobertura exportada.

## 0.9.24.3 · 21/10/2026

El sitio y la pantalla de análisis explican el lector del cuadro, el acuerdo de modelos, la comprobación por reglas y sus límites. La ficha distingue implementación de eficacia pendiente de medición. El detalle muestra cobertura incluso sin preguntas: una falla de proveedores ya no parece una lectura exitosa. El progreso anuncia esta etapa y declara fallas o lectura parcial. Las preguntas identifican archivo y hoja, bloquean el doble envío y mantienen un estado accesible. No cambia el método ni la versión lector-1.2. Regresiones de cobertura, continuidad de detección y comportamiento de pantalla incluidas en la barrera de calidad.

# Historia técnica

## Aplicación 0.9.24.2 · motor multilente-0.9.19 · 21 de octubre de 2026

Publica las correcciones del lector 1.1 y 1.2 (abajo). Reprocesadas sin llamadas las lecturas guardadas de 14 planillas de prueba: las mismas detecciones (5 de 7) y las mismas señales en las copias correctas que la versión anterior.

## Correcciones del lector 1.2 · 21 de octubre de 2026

- Las confirmaciones identifican el archivo, la hoja, la relación normalizada y las celdas evaluadas. Responder sobre una hoja o fórmula no confirma otra con las mismas coordenadas.
- Los informes de versiones anteriores conservan respuestas e historial como registro, pero deben reanalizarse y reconfirmarse con identificadores nuevos. La pantalla lo explica y la API rechaza confirmar preguntas antiguas (409).
- Regresiones de archivos y hojas distintos, fórmulas distintas sobre la misma zona, identidad estable al reordenar sumandos y modelos, conservación del historial y recorrido HTTP con persistencia.

## Correcciones del lector 1.1 · 21 de octubre de 2026

- El acuerdo exige la misma relación normalizada entre al menos dos proveedores. Compartir celdas ya no permite agrupar fórmulas distintas; se mantienen las sumas reordenadas y los rangos diferentes.
- Reanalizar conserva el historial completo de confirmaciones, con sus fechas y autores, además de la última respuesta. No recupera entradas que se hayan perdido en reanálisis anteriores.
- Regresiones: desacuerdo entre fórmulas superpuestas, acuerdo real que sigue detectando una suma incorrecta, cuadro correcto sin señal y confirmaciones sucesivas conservadas tras reanálisis repetidos.

## Aplicación 0.9.24.1 · motor multilente-0.9.19 · 21 de octubre de 2026

- Lector del cuadro: la lectora Gemini fallaba en producción («DefaultCredentialsError»): producción usa Gemini por
  Vertex y el lector no pasaba el archivo de credenciales configurado. Ahora lo pasa, igual que la triangulación, y
  toma sólo las partes de texto de la respuesta. Detectado en la verificación posterior a publicar la 0.9.24.

## Aplicación 0.9.24 · motor multilente-0.9.19 · 21 de octubre de 2026

**Lector del cuadro: la IA lee, las reglas verifican.** Hasta ahora las reglas sólo controlaban lo que la planilla
declara (un total con su rótulo); los errores reales que se escapaban eran relaciones que nadie escribió (un neto, un
acumulado, un total provincial). Ahora, al analizar, tres modelos (gpt, gemini y deepseek, los configurados) leen
cada hoja A CIEGAS: cada número aparece como «#» (los años se ven), para que no puedan acomodar la lectura a un dato
equivocado. Cada uno propone, de un catálogo cerrado (sumas por columnas o por filas, acumulados, índice base 100,
valores que no pueden ser cero, negativos o repetirse), qué debería cumplir el cuadro y por qué. Vale lo que
proponen al menos dos. Las reglas lo verifican con los números (intérprete cerrado, sin eval): si se cumple en la
mayoría de sus filas, los números confirman la lectura y las filas donde no se cumple son señales («la cuenta no
cierra: alguna de las celdas que intervienen no está bien»); si falla en muchas, la lectura se descarta sin señal;
si hay pocas filas para decidir, la pantalla pregunta a quien hizo el informe («Así se leyó el cuadro») y sólo su sí
la controla, al volver a analizar. Lee todas las hojas visibles con números, por tramos de 300 filas con el
encabezado repetido, y declara lo que no lee (hojas ocultas, más de 5000x80 o del tope de celdas). La grilla se
guarda al cargar (sólo para el lector) y no viaja al navegador. Una falla de los proveedores no frena el análisis.
Configuración: `LECTOR_IA=apagado|observar|activo` (`services/lector_mapa.py`).

**Se publica activo antes de terminar su medición, por decisión del usuario.** La medición con metas fijadas antes
(`/root/lector-2110/DISENO.txt` y adendas: 63 planillas correctas, 123 errores insertados, validaciones 4 y 5) corre la
noche del 21/10. Pruebas al azar del día (7 planillas oficiales con un error insertado y su copia correcta): lector 5
de 7, motor 4 de 7, juntos 6 de 7; ninguna alarma en las copias correctas salvo una diferencia real en la planilla
vigente de energía eléctrica facturada de un organismo estadístico (agosto de 2021: el total supera en 300.000 kWh la suma de los
tipos de usuario). Costo y demora: tres consultas por tramo; una planilla de 15 hojas tardó 8 minutos.

## Aplicación 0.9.23 · motor multilente-0.9.18 · 21 de octubre de 2026

**«¿Qué resultó ser esta señal?»** En cada señal del informe, quien lo hizo (con rol de analista) puede responder
«Era un error real», «El dato estaba bien» o «No sé todavía», con un comentario opcional de hasta 500 caracteres. Cada
respuesta es una fila nueva en `respuestas_senal` (nada se borra; vale la última) con una copia de la señal (lente,
regla, hoja, celda): si el informe se reanaliza y las señales se regeneran, la respuesta queda y su vínculo pasa a
nulo. Nadie responde por otra persona (ni un administrador); el rol lector ve la respuesta pero no responde; mientras
el informe se analiza se pide esperar (409). La señal que generó el motor no se modifica. Borrar el informe borra sus
respuestas. `scripts/exportar_respuestas_senal.py` exporta la última respuesta por señal sin datos de la persona, con
un seudónimo del informe distinto en cada exportación, para medir la herramienta con casos reales. Migración
`20261021_respuestas_senal` (sólo agrega la tabla). El motor no cambia.

**Chequeo previo de nitidez (medido la noche del 20/10, no se publica).** Con umbrales fijados antes de medir, mejora
poco las planillas correctas (con alguna alarma alta 26 → 22 de 63) y pierde un error real de la validación 3 (instituto de estadística
turismo emisivo, celda ×10 de menos): el propio error hace que los totales no cierren y el cuadro se juzga borroso.

## Aplicación 0.9.22 · motor multilente-0.9.18 · 20 de octubre de 2026

**Sondeo previo («radiografía»).** Antes de presentar las señales de una hoja, se mira si la lectura es confiable.
Si una misma regla aparece en 3 o más lugares distintos de una hoja (lugares = mínimo entre filas y columnas
distintas de la celda ancla de cada señal: un error que se arrastra por su fila o su columna cuenta uno), o marca la
misma celda en 3 o más hojas (salvo reglas de fórmulas), lo más probable es que el cuadro se haya leído mal: esas
señales pasan a nota de alcance, no se borran, y el comienzo del informe las declara «sin controlar» con su motivo.
Nunca se abstiene una señal corroborada por un control independiente (`services/sondeo.py`, `tests/test_sondeo.py`).
Una revisión independiente encontró fallas en la primera versión (contaba las celdas de una sola señal, mandaba lo
abstenido a contexto temporal, abstenía señales corroboradas) que se corrigieron antes de medir.

- Detecciones nuevas y arreglos de falsas alarmas con planillas oficiales reales: totales cruzados con bloques
  anidados y filas total sin rótulo, fórmula fija en la misma columna, período faltante en paneles, sufijos «Total_2»,
  claves del formato largo, filas repetidas sólo si están aisladas.
- Períodos de series largas sin costo cuadrático (misma salida, probada contra la versión anterior): un libro oficial
  de ~500 mil celdas tardaba horas.
- El informe completo ya no se rompe con una relación adicional sin total declarado (KeyError «total_declarado» en
  libros de balanza de pagos de un instituto de estadística, también en 0.9.21.1).

**Mediciones (20/10/2026).** 63 planillas oficiales vigentes y correctas: alarmas altas 2.000 (0.9.21) → 626 (sin
sondeo) → 276; planillas con alguna alarma 30 → 28 → 26. Errores insertados en ellas: 81 de 123 sin sondeo, 80 con
sondeo. Mediciones 14 y 15 sin cambios; validación 3 con las mismas detecciones; autoajuste 164/174 sin falsas y
estructura 144/150 con 4 falsas, igual que la referencia.

**Validaciones con errores reales nuevos (diseño fijado antes de correr): no mejoran.** Cuarta (instituto de estadística y un ministerio de una jurisdicción): 0 de 5 con 0.9.21.1, 0.9.22 y el sondeo; falsas alarmas en 5 de 9
controles. Quinta (instituto de estadística encuesta hotelera y banco central): 0 de 2; falsas alarmas 2 de 5 sin sondeo, 0 con sondeo. Los
errores eran relaciones que la planilla no declara (acumulados, saldos, índices, subtotales sin código): la
herramienta controla lo declarado pero no infiere lo que significa el cuadro. Se publica tal cual.

## Aplicación 0.9.21.1 · motor multilente-0.9.17 · 19 de octubre de 2026

- Pantalla del informe: si el informe no existe (404), la sesión venció (401) o falta permiso (403), avisa una vez y
  deja de pedirlo. Antes reintentaba cada 4,5 s sin fin: el 13/10/2026 dos navegadores pidieron 248 veces un informe
  borrado. Los errores transitorios se reintentan hasta 5 veces con espera creciente. Tests en
  `tests/detalle_reintentos_ui.cjs`. El motor de análisis no cambia.
- Fuera del código: backup externo a Google Drive al día (19/10/2026).

## Aplicación 0.9.21 · motor multilente-0.9.17 · 19 de octubre de 2026

Arreglos de lo que mostró la validación con planillas Excel argentinas reales (validación externa 3,
`/root/validacion-externa-03`: instituto de estadística, oficina de presupuesto, dirección de cuentas nacionales y dirección de estadística de una jurisdicción, con errores reales
corregidos después por el organismo). Con 0.9.20 se detectaron 2 de 8 errores, hubo falsas alarmas
(ALTA sobre datos correctos en la hoja puntuada) en 6 de 10 controles y cada libro de balanza de pagos
de un instituto de estadística daba entre 396 y 496 alarmas altas fuera de la hoja puntuada, casi todas «signo opuesto en la
columna» y «fuera de escala» en cuadros de flujos que pueden ser negativos. Con planillas oficiales
reales el criterio que más falla es el de pocas falsas alarmas, al revés que en las mediciones sintéticas.

**Advertencia:** estos arreglos salen de esos mismos archivos y del banco de planillas correctas usado
para medirlos. Volver a medir con ellos no prueba que generalicen: la próxima validación externa tiene
que usar otros archivos y otros errores.

- **Encabezado de dos niveles año + trimestre** (balanza de pagos de un instituto de estadística): el año se arrastra a la
  derecha, «I» a «IV» son trimestres (si aparece «III» o «IV»: «I» y «II» solos pueden ser semestres),
  «Total» queda sin período y los años sueltos forman su propio panel anual. Lo lee sólo el modelo
  común, sin «año no entero» ni trimestres como columnas sueltas. La jerarquía por sangría se arma
  con los espacios iniciales del rótulo.
- **Series de signo mixto** (flujos): un valor chico cerca del cruce por cero no es un pico ni un valor
  aislado en el cuadro; un pico cuenta si además supera 5 veces al mayor valor absoluto del resto de la
  serie (un valor cargado en otra unidad). «Signo aislado» no aplica a filas que declaran un flujo o un
  resultado (transacciones, revalorizaciones, variaciones, netos, saldos, resultado, déficit), pero sí a
  impuestos, márgenes, ajustes y saldos de deuda.
- **Marcas de sin dato:** «s/i», «s/inf» y «///» son marcas de dato no disponible. Una marca que la hoja
  usa en dos o más series es la convención del cuadro y no es «cambio de tipo»; en una sola serie sigue
  siendo señal.
- **Escala por columna:** no corre en columnas de variación ni en porcentajes o tasas de signo mixto (un
  solo negativo no alcanza); sin separación clara (menos de 10 veces) ni un factor cercano a una
  potencia de diez queda como señal media. Un salto recurrente ya calibrado por volatilidad no sube a ALTA.
- **Negativos en columnas «Total»:** las filas de resultado, saldo, variación y financiamiento (fuentes
  y aplicaciones financieras) admiten negativos; una tasa, un porcentaje o un impuesto negativos siguen
  siendo imposibles.
- **Filas idénticas:** un código padre igual a su único hijo no es una fila copiada.
- **Salvaguarda de memoria:** los libros de un ministerio con hojas formateadas hasta la columna XFD o con un
  millón de celdas con datos superaban 3 GB al leerse (el servicio tiene 2 GB: se reiniciaba y la
  persona quedaba sin respuesta). Antes de abrirlo, se mide en el XML de cada hoja (sin openpyxl ni
  pandas, en menos de 4 segundos) el rango usado —filas × columnas, contando celdas combinadas y la
  dimensión declarada— y las celdas con datos; un .xls, con xlrd hoja por hoja. Más de 3.000.000 de
  celdas de rango o de 600.000 con datos se rechaza al cargar, con el motivo y la hoja más grande
  («El libro tiene N celdas con datos; el máximo es M. Dividilo…»); con varios archivos, el grande queda
  declarado y el resto se analiza.
  Picos medidos (de a un archivo, tope de 3 GB sin swap): `planilla_oficial` (16,6 millones de celdas de
  rango) llega a 2,7 GB en 38 s y se corta; `planilla_oficial` (1 millón de datos en 65 hojas) a 3,1 GB;
  un padrón educativo de un portal de datos abiertos (1,17 millones de datos en una hoja) a 3,0 GB. Entran
  `planilla_oficial` (2,6 millones de rango, 19.000 datos: 1,3 GB), `planilla_oficial` y
  `planilla_oficial` (unos 500.000 datos: 1,2-1,4 GB, pero más de 10 minutos de análisis). De los 300
  archivos del banco de planillas correctas se rechazan 8 (siete `planilla_oficial` y el padrón): los tres
  medidos arriba y cinco más grandes que ellos en rango o en datos. Ningún caso de las mediciones
  heldout, de las validaciones ni de los bancos de autoajuste se acerca a los topes (el mayor tiene
  165.000 celdas de rango).
- Revisión independiente por agente del diff: 12 observaciones. Corregidas con pruebas
  (`tests/test_revision_0921.py`, `tests/test_salvaguarda_memoria_0921.py`): el signo mixto apagaba
  también un ×10 real entre vecinos normales; las filas que admiten negativos y signo incluían tasas,
  porcentajes, «Ganancias» y «Fuentes de agua»; un negativo suelto sacaba de la escala a una columna de
  porcentaje; la convención de sin dato se activaba con dos celdas cualesquiera de la hoja (ahora: dos
  series, o tres veces en la misma serie); semestres leídos como
  trimestres; la medición del libro no consideraba la dimensión declarada ni celdas sin referencia y
  armaba listas grandes. Quedan como limitación: con año + trimestre y años sueltos en el mismo cuadro,
  el «Total» del año no se coteja con sus trimestres; un libro Open XML estricto se convierte antes de
  medirlo.

Efecto medido:

- Validación 3 (hoja puntuada): detección 3 de 8 (antes 2: ahora también E1, el Total de
  revalorizaciones en 0 de 2024-IV); falsas alarmas en 1 de 10 controles (antes 6; queda K8, 6 ALTA en
  el Cuadro 6); ALTA fuera de la hoja puntuada en los libros de un instituto de estadística, 85-91 por libro (antes 396-496).
- Banco de planillas oficiales correctas (muestra de 73, `/root/banco-medir`): en los 63 archivos que
  se analizan con las tres versiones, 2.000 ALTA en 30 archivos (0.9.20: 4.418 en 32). `planilla_oficial` y
  el padrón se rechazan en menos de 4 segundos (con 0.9.20 el primero agotaba la memoria y el segundo
  tardaba 17 minutos al borde del tope).
- Errores insertados en planillas reales (`/root/banco-errores`, 116 casos comparables): la misma
  detección caso por caso que 0.9.20 (62 de 116: total 8/29, escala 19/29, dígito 12/29, signo 23/29);
  ALTA en los controles sin error, 261 (0.9.20: 520). Los 10 casos de `planilla_oficial` y `_11` (11,6 y
  25,8 millones de celdas de rango, más que `planilla_oficial`) ahora se rechazan al cargarlos.
- Mediciones heldout 14 y 15 (68 casos sin PDF cada una): sin detecciones perdidas ni ALTA nuevas en
  correctos; criterio 3, 42 de 42 en ambas. En L04 (heldout 15) dejan de salir 4 ALTA de «cambio de
  tipo» por «///» y «...», que el caso pide declarar como signos convencionales.
- Bancos de autoajuste idénticos a la referencia: s7011 164/174 con 0 falsas; s7008 144/150 con 4 falsas.
- Tests en `tests/test_planillas_reales_0921.py`, `tests/test_revision_0921.py` y
  `tests/test_salvaguarda_memoria_0921.py`.

## Aplicación 0.9.20.2 · motor multilente-0.9.16 · 18 de octubre de 2026

- Incubadora: «Situación a mejorar» muestra cuántos caracteres lleva (máximo 30.000) y avisa antes de guardar si se
  pasa; el chat con el asistente muestra el contador a partir de 8.000 y, si el mensaje supera 12.000, sugiere usar la
  entrega final en lugar de rechazarlo sin explicación. Los topes de la interfaz se comprueban contra los del servidor.
- Además, fuera del código: el servicio tiene un tope de CPU (2 de 4 núcleos) y el backup diario de la base guarda una
  copia por mes durante 24 meses.

## Aplicación 0.9.20.1 · motor multilente-0.9.16 · 18 de octubre de 2026

Corrección de Incubadora a partir de la consulta de una participante (05/10/2026): no podía guardar su
propuesta corregida en «Guardar contexto» (tope de 8.000 caracteres) ni enviarla al docente (12.000).

- El contexto del proyecto y las consultas e intervenciones docentes admiten 30.000 caracteres, igual que
  la entrega. El chat con el asistente conserva su tope de 12.000; al asistente se le envía el contexto
  acotado (12.000) porque la propuesta guardada ya va completa aparte.
- Dos entregas antiguas quedaron guardadas cortadas en 16.000 caracteres por una versión anterior al
  19/09/2026, que recortaba sin avisar; desde entonces el texto que supera el máximo se rechaza con
  aviso y no se recorta. Esas entregas no se pueden recuperar desde la aplicación.
- El motor de análisis no cambia. Tests en `tests/test_incubadora_topes_largos.py`.

## Aplicación 0.9.20 · motor multilente-0.9.16 · 17 de octubre de 2026

Arreglos de lo que mostró la primera validación con errores reales (`/root/validacion-externa/medicion`:
2 de 6 errores detectados, 2 falsas alarmas en 7 controles, un bloque sin revisar no declarado). Como salen
de esos mismos archivos, volver a medirlos con ellos no prueba nada: la próxima validación externa tiene
que usar errores nuevos.

- **Jerarquías por código** (1, 1.1, 1.1.1, o el código pegado al rótulo): cada cuenta se controla contra
  sus subcuentas inmediatas y un Total sin código contra el primer nivel, con la tolerancia de redondeo.
  Lo que no se puede afirmar se declara: hijos salteados o repetidos, desgloses parciales («de las
  cuales…»), filas sin código dentro del tramo, columnas que no suman en ninguna cuenta. Es el formato
  típico de presupuestos y cuentas de inversión.
- **Total separado de sus componentes por filas vacías:** se une al primer grupo de arriba con el que
  cierra (un título de sección corta la búsqueda); si no cierra con ninguno, no se fusionan bloques y se
  declara al comienzo que su cierre no se armó. Antes quedaba sin controlar y sin aviso.
- **Cambio de unidad declarado en el cuadro** («1980-1986: miles de pesos; desde 1987: millones»): la señal
  de escala en ese corte pasa a contexto con la nota, sólo si la nota es del mismo cuadro, la unidad está
  pegada al año y el sentido y el factor del salto coinciden con la nota. No se borra.
- **Pantalla de revisión de PDF:** «No suma» entiende jerarquías por código y subtotales de varios niveles
  (antes marcaba en falso el Total que cierra contra el primer nivel). Python y navegador dan lo mismo
  (9.000 tablas al azar sin diferencias).
- Revisión independiente por agente sobre el primer borrador: 7 problemas (alarmas falsas en columnas que
  no suman y en desgloses parciales, un Total con filas sin código, un total unido a otra sección, la nota
  de unidad de otro cuadro que podía ocultar un error real, sentido del salto sin verificar, frases de
  cobertura tomadas como cambio de unidad), todos corregidos con pruebas.
- Reejecutadas la sexta a la decimocuarta: sólo cambia un caso (un «Total general» separado por una fila
  vacía que ahora se controla y cierra). Bancos de autoajuste idénticos a la referencia. Tests en
  `tests/test_validacion_externa_1.py` y `tests/validacion_externa_ui.cjs`.

## Aplicación 0.9.19 · motor multilente-0.9.15 · 16 de octubre de 2026

Arreglos de lo que encontró la decimocuarta medición (`/root/eval-heldout14-20261016`): criterios 2 y 3
holgados (100 % · 100 % · 92 % y ninguna alarma alta en correctos), criterio 1 con 3 casos en silencio de
92, ninguno indiscutible.

- **Excel con formato de porcentaje:** se avisa qué guarda la celda (la fracción, o valores que ya están
  en puntos y el formato multiplica por 100), sin cambiar los valores.
- **Archivos que no son datos:** una página web con extensión .csv o .xls se rechaza diciendo que es una
  página (posible descarga fallida); una tabla HTML o una «Hoja de cálculo XML 2003» con extensión .xls,
  diciendo cómo convertirla.
- **Excel «Open XML estricto»:** se convierte en memoria y se lee, con aviso (antes se rechazaba con un
  motivo inexacto).
- **.xls binario:** los controles por celda y los cierres corren también sobre él; como sus fórmulas no se
  pueden leer, las reglas que distinguen un valor tipeado de uno calculado no corren.
- **Una columna de fecha constante** («fecha de actualización») ya no se toma como eje de períodos ni como
  rótulo de fila (daba siete falsos «período duplicado»).
- **Períodos:** bimestres («Ene-feb 24»), años exportados por R («X2017», sólo si todos los rótulos lo
  traen) y meses sin año («enero a diciembre (sin año en el rótulo)»).
- **Arrastre entre páginas** («Transporte», «Van», «Suma y sigue» al pie): se toma como total sólo con
  evidencia (iguala la suma de las filas de arriba, o el cuadro trae «Viene de…»); «Viene de…» no entra en
  la evolución.
- **Datos no publicados:** «<5» y «s.e.» se leen como dato suprimido por confidencialidad y «<0,1» como
  valor menor que la unidad publicada, cada uno con su aviso; ya no se leen como 5 ni dan un falso cambio de
  tipo, y el motivo de los cierres cita la marca real (salvo que los períodos comprobables no cierren: eso
  se dice primero).
- **Filas de promedio, mediana, porcentaje o índice** entre los componentes salen del cierre sólo si con
  ellas el total no cierra y sin ellas sí.
- **PDF:** celdas combinadas verticales completadas con los bordes del cuadro; texto en capas opcionales
  apagadas excluido y avisado (si no se puede separar con seguridad, sólo se avisa); en documentos en
  inglés sin otra evidencia, la coma se lee como separador de miles (con reglas estrictas de idioma:
  un texto mezclado sigue «ambiguo» y declarado).
- Revisión independiente por agente sobre el primer borrador: 8 problemas comprobados (filas «Tasa» y
  «Variación de existencias» sacadas de cierres que sí sumaban, un rubro «Transporte» tomado como arrastre,
  una tabla en castellano leída como inglesa ×1000, «<0,1» presentado como confidencialidad, un motivo que
  tapaba un total que no cerraba, un aviso de porcentaje falso, mensajes engañosos para tablas HTML y XML
  2003, reglas de valor tipeado sobre .xls), todos corregidos con pruebas.
- Reejecutadas la sexta a la decimocuarta: sólo cambios esperados. Bancos de autoajuste idénticos a la
  referencia. Tests en `tests/test_decimocuarta_medicion.py`.

## Aplicación 0.9.18 · motor multilente-0.9.14 · 16 de octubre de 2026

Arreglos de lo que encontró la decimotercera medición (`/root/eval-heldout13-20261016`): criterios 2 y 3
holgados (100 % · 100 % · 75 % —12 de 12 en PDF ubicando la celda por posición— y ninguna alarma alta en
correctos), criterio 1 con 5 casos en silencio de 92, dos indiscutibles.

- **Punto ambiguo en CSV** («12.345» sin otro valor que decida si es miles o decimal): se sigue leyendo
  como miles, pero ahora se declara al comienzo del informe, como ya se hacía con la coma, con un ejemplo
  tomado del archivo (antes el aviso iba sólo al anexo y citaba un «1.738» fijo).
- **Adjuntos de un PDF:** se avisan en la revisión de lectura y el informe declara al comienzo que no se
  leyeron (con su nombre), con cualquier tabla que se confirme.
- **PDF con texto ilegible** (una fuente con un mapa de caracteres inútil: se ve bien, pero el texto sale
  «&XDGUR» por «Cuadro»): la página se lee con OCR, como una escaneada, y se avisa.
- **Tabla leída con OCR:** el informe lo dice arriba («Tabla leída con OCR de …»), no sólo la pantalla.
- **Años guardados como fechas del 1 de enero** en el encabezado de un Excel: se leen como años (antes,
  como enero de cada año) y se avisa. Sólo en una fila sin otras cifras: las fechas de los datos no se tocan.
- **Duraciones [h]:mm en Excel:** se leen como horas con decimales y se avisa (antes se rechazaba la hoja).
- **CSV de R con nombres de fila** (el encabezado tiene un campo menos que todas las filas): la primera
  columna se toma como rótulo y se avisa; antes se rechazaba diciendo que no había filas. Sólo si los rótulos
  no son cifras y la última columna sí: una columna final de notas no cuenta.
- **Subtotales de columna intercalados** («1.er trim.», «Total 2025»): se controlan contra sus períodos
  (regla nueva `subtotal_columna_no_cierra`) y esos cierres se cuentan; no en filas de promedios, precios o
  stocks. Si los totales entre filas no se pudieron comprobar, se sigue diciendo por qué.
- **Carga mixta (Excel + CSV):** se cuentan también los cierres del CSV, y las filas del Excel ya no se
  declaran «sin archivo de origen».
- **Indicadores apilados** (un «Total» en otra columna de rótulos): el motivo de los cierres no comprobados
  lo dice, en vez de afirmar que no había fila de total.
- Revisión independiente por agente sobre el primer borrador: 7 problemas (fechas reales convertidas en
  años, alarmas de subtotal en filas de promedios y stocks, motivo de cierres borrado, adjuntos que marcaban
  páginas sin leer o tapaban otros avisos, una columna final de notas tomada como CSV de R, la leyenda de la
  tabla repetida, la cuenta de cierres de la carga mixta), todos corregidos con pruebas.
- Reejecutadas la sexta a la decimotercera: sólo cambios esperados (CSV con punto ambiguo que ahora se
  declaran, cargas mixtas y los casos de la 13.ª). Bancos de autoajuste idénticos a la referencia. Tests en
  `tests/test_decimotercera_medicion.py`.

## Aplicación 0.9.17 · motor multilente-0.9.13 · 16 de octubre de 2026

Arreglos de lo que encontró la duodécima medición (`/root/eval-heldout12-20261015`): criterios 2 y 3
holgados (100 % · 100 % · 92 % y una alarma alta en correctos, por un valor que se repite de verdad),
criterio 1 con 6 casos en silencio de 92, uno indiscutible.

- **Columnas fuera de los controles, también en CSV y PDF:** una columna con números cuyo rótulo no se
  reconoce como período («Ene-jun 2025») ya se declaraba en un Excel; en un CSV o en una tabla de PDF
  quedaba afuera sin aviso y el informe decía que no habían quedado partes sin leer. Ahora llega al
  comienzo del informe por la lectura del archivo.
- **Columnas auxiliares entre los años** («CV (%)», «Error estándar», «Var. %», «IC 95 %»): ya no se toman
  como períodos mal escritos (salían como consultas altas al área «corregir o justificar el período»);
  quedan fuera de las series y de los cierres y se declaran una vez al comienzo. El aviso de encabezados
  repetidos ahora llega al comienzo del informe (antes quedaba en el detalle de la hoja) y una fecha
  repetida se muestra sin la hora.
- **Meses en código SDMX** («2025M01»): se reconocen como meses.
- **CSV con cada línea de datos entera entre comillas** (así lo deja Excel al guardar con otra
  configuración regional): se separan los campos y se avisa; antes se rechazaba diciendo que no había
  filas. Sólo si las líneas forman un bloque seguido y mayoritario, con cifras y tantos campos como el
  encabezado: un título o una fuente entre comillas con «;» adentro no se tocan.
- **Señales sobre celdas que el comienzo ya declara como posiblemente mal leídas** (cifras que el texto
  del PDF no tiene, un período vacío, más de un número en la celda, una columna sin rótulo): ya no
  llegan al área como prioridad alta; quedan en media con el motivo «verificar la lectura contra el
  original». No se borran. Un total que no suma o un rótulo repetido no cuentan como problema de
  lectura: siguen siendo consultas al área.
- **PDF con las cifras en campos de formulario:** sus valores no son texto de la página; se ubican junto
  a sus rótulos, se propone una tabla y se avisa. Un campo cuyo valor ya está impreso no se cuenta; en una
  página girada sólo se avisa (y el informe lo declara).
- **PDF con un cuadro pegado como imagen en una página con texto:** se lee con OCR como tabla aparte, y la
  tabla analizada dice «leída con OCR». Si no se puede leer, se avisa en pantalla y el informe lo declara
  al comienzo. Un membrete, un pie, un logo o una foto sin cifras no se declaran, ni la página escaneada
  con su capa de texto (aunque venga en franjas). El OCR de estas imágenes tiene su propio cupo, aparte
  del de páginas escaneadas, y el recorte respeta la zona visible de la página (cropbox).
- **Página a dos columnas:** la franja de texto corrido de la columna vecina ya no entra al cuadro como
  una columna más (sólo cuando ese texto sigue también fuera del cuadro: una columna «Observaciones» se
  conserva).
- **«Mar del Plata»** ya no pierde «Mar» en el encabezado de un PDF (de paso, «Isla de los Pájaros» y
  «Velas de emergencia» en mediciones anteriores).
- **Resumen del informe:** «No hay consultas para el área» abre el párrafo con mayúscula cuando hay
  pendientes. También se ordenó un import de 0.9.16 que hacía fallar el ruff del hook pre-commit.
- Revisión independiente por agente sobre el primer borrador: 2 problemas altos y 4 medios (un membrete
  que se declaraba como contenido sin leer y gastaba el cupo de OCR, títulos de CSV desenvueltos, recorte
  con cropbox, un cuadro que sigue en otra página unido a la tabla OCR, campos girados o ya impresos, una
  columna «Observaciones» quitada), todos corregidos con pruebas.
- Reejecutadas la sexta a la duodécima: sólo cambios esperados. Bancos de autoajuste idénticos a la
  referencia (164/174 sin falsas alarmas; 144/150 con 4). Tests en `tests/test_duodecima_medicion.py`.

## Aplicación 0.9.16 · motor multilente-0.9.12 · 15 de octubre de 2026

Arreglos de lo que encontró la undécima medición (`/root/eval-heldout11-20261015`): criterios 2 y 3
holgados (100 % · 100 % · 92 % y ninguna alarma alta en correctos), criterio 1 con 6 casos en silencio
de 92, tres de ellos indiscutibles.

- **«Circuito» no es un dato personal:** la regla de columnas sensibles buscaba «cuit» dentro de
  cualquier palabra y descartaba la columna sin aviso. Ahora «cuit», «cuil» y «dni» se buscan como
  palabra (`services/sanitizacion.py`).
- **Cifras exportadas como fórmula de texto** (`="12345"`, el truco de algunos sistemas para que Excel
  no las cambie): se leen como número y se avisa.
- **Cifras con la unidad pegada** («147.348 ha», «12,5 km»): la unidad se quita para leer la cifra y se
  avisa. También la salvaguarda de cifras las reconoce.
- **Llamadas de nota en superíndice en PDF:** los dígitos de letra mucho más chica se quitan de la página
  antes de las dos lecturas de la tabla (por coordenadas y por líneas dibujadas) y del texto que usa la
  salvaguarda; antes «9.857» con su llamada «1» se leía «9.8571», mil veces más. Sólo en texto derecho:
  los dígitos de un encabezado girado no son llamadas.
- **Renglones de prosa con cifras en una página de informe** («informaron 23.037 cortes… 3,1 %») ya no
  entran a la grilla del cuadro (con ellos, las columnas no se separaban y no se proponía ninguna tabla)
  ni a la salvaguarda de cifras (no son cifras del cuadro).
- **Salvaguarda de cifras en PDF:** compara con el texto con renglones; si con el texto de pypdf la tabla
  trae cifras que el texto no tiene y con el de renglones no, la tabla está tan desarmada como ese texto
  (un cuadro impreso de costado) y manda pypdf. Los rótulos se comparan con las palabras de pypdf.
- De paso, dos PDF de la sexta medición (con un error sembrado cada uno) que se leían con varias cifras
  en una celda y rótulos genéricos ahora se leen columna por columna con sus rótulos; en uno, el error
  sembrado (un mes repetido) ahora se señala.
- Reejecutadas la sexta a la undécima: sólo cambios esperados. Bancos de autoajuste idénticos a la
  referencia. Tests en `tests/test_undecima_medicion.py`.

## Aplicación 0.9.15 · motor multilente-0.9.11 · 15 de octubre de 2026

Arreglos de lo que encontró la décima medición (`/root/eval-heldout10-20261015`): 6 casos en
silencio de 92 (3 leves), por formas de leer mal un archivo que la salvaguarda de cifras no alcanzaba.

- **CSV con líneas de comentario «#»:** no son registros; se separan de los datos y se avisa
  (`carga_archivos._comentarios_y_corte_csv`, también en los controles de `tablas_planas`).
- **CSV cortado a mitad de una línea** (descarga interrumpida: sin salto final y con menos campos que
  el resto): esa línea no se incorpora y el informe lo declara al comienzo.
- **Cuadro de PDF que sigue en la página siguiente sin repetir el encabezado:** su primera fila es de
  datos; sus filas se unen a la tabla de la página anterior, con su encabezado, y la pantalla lo avisa
  (`ocr_local._unir_continuaciones`).
- **Rótulos de fila partidos en dos líneas:** la segunda línea completa el rótulo de la fila de arriba.
- **Rótulos de columna:** la costura de dos rótulos pegados («JuanSantiago») separa la frase, y una
  frase sobre varias columnas sin un nivel de abajo que las distinga se reparte por palabra. Además de
  los casos de la décima, corrige rótulos que se perdían en archivos correctos de mediciones anteriores
  («Mar del Plata», «Industria alimentaria», «Velas comunes»).
- **Salvaguarda contra el texto del PDF:** las cifras que quedan en el encabezado de la tabla confirmada
  no se analizan y cuentan como faltantes; y los rótulos con palabras que el texto del PDF no tiene
  («Rodado Msaquinaria») se declaran al comienzo.
- **Un valor diez veces mayor en el primer período** con la serie en crecimiento queda algo por debajo
  de 10 veces su vecino: alcanza con apartarse 9 veces de la extrapolación (fallaba en la octava, la
  novena y la décima; ahora se señala en la celda).
  Sólo para un primer período MAYOR: en el último año, una caída fuerte de una serie real (2020) no
  es un error de escala, y la planilla de referencia limpia lo confirma.
- Reejecutadas la sexta a la décima: sólo cambios esperados. Bancos de autoajuste idénticos a la
  referencia. Tests en `tests/test_decima_medicion.py`.

## Aplicación 0.9.14 · motor multilente-0.9.10 · 15 de octubre de 2026

Arreglos de lo que encontró la novena medición (`/root/eval-heldout9-20261015`), la primera con la
salvaguarda de cifras: 2 casos en silencio de 92 (frente a 7 en la octava), con 17 situaciones de
lectura nuevas.

- **Notación científica** («4.203222e+06»): `perfilado.expandir_cientifica` la escribe sin exponente
  antes de leerla, con el mismo criterio que el resto de la columna; antes quedaba como texto y se
  perdía la columna entera. La salvaguarda de cifras también la reconoce como cifra.
- **PDF que se abre sin clave y sólo restringe copiar o imprimir:** se lee (`decrypt("")`); sólo se
  rechaza el que pide contraseña para abrirse, y el mensaje lo dice así.
- **Rótulos de columna pegados en el PDF** («Miembro inferiorMiembro superior» en dos columnas): si dos
  columnas vecinas quedan con el mismo nombre, cada palabra va a la columna donde está y se separan las
  palabras pegadas (`_rotulos_por_palabra_pdf`).
- **Rótulo repetido en la tabla confirmada** (la revisión lo renombra «X · X» o «X (2)»): se declara al
  comienzo del informe como celda marcada, «no se sabe qué columna es cuál».
- Pendiente anotado: un valor diez veces mayor en el primer período, con el total recalculado, sólo
  recibe una señal de contexto (octava y novena).
- Reejecutadas la sexta a la novena: sólo los cambios esperados. Bancos de autoajuste idénticos a la
  referencia. Tests en `tests/test_novena_medicion.py`.

## Aplicación 0.9.13 · motor multilente-0.9.9 · 15 de octubre de 2026

Arreglos de lo que encontró la octava medición (`/root/eval-heldout8-20261014`), que armó a propósito
situaciones de lectura nuevas: siete casos quedaron en silencio, todos por lecturas que fallaban sin
avisar. En lugar de sólo corregir cada forma de leer mal, se agregó una salvaguarda que no depende de
saber por qué falló la lectura.

- **Salvaguarda de cifras** (`services/cobertura_cifras.py`): se cuentan las cifras del archivo
  original (filas con dos o más números, sin años sueltos) y se buscan entre los datos analizados.
  Si faltan al menos 3 y al menos el 2 %, el informe lo declara al comienzo, con ejemplos y su
  ubicación. En PDF se comparan las cifras del texto de la página con las de la tabla propuesta, en
  las dos direcciones: cifras que la lectura dejó afuera y cifras de la tabla que el texto no tiene
  (un cuadro impreso de costado, leído desarmado). La pantalla de revisión lo avisa antes de confirmar,
  y la tabla confirmada lleva esas cifras al análisis (campo `cifras_original`) para que el informe
  lo diga aunque la persona confirme sin corregir. Si una página tiene cifras y no se reconoció
  ningún cuadro, la pantalla lo dice.
- **Dos cuadros en una página de PDF:** la página se separa por cada rótulo «Cuadro N» y cada cuadro
  se lee por su lado (antes, con columnas distintas, no se reconocía ninguno).
- **Signo «−» de otra fuente en un PDF:** las palabras se agrupan en filas por cercanía y no por
  franjas fijas; el signo, uno o dos puntos más arriba, caía en otra fila y la celda llegaba vacía.
- **Meses escritos «enero de 2025»** se reconocen como período, y un «Total 2025» al pie de un eje
  mensual es el total, no un período más: el cuadro se controla y sus cierres se comprueban.
- **Encabezado repetido a mitad de un CSV** (dos exportaciones pegadas): no entra como un registro;
  se avisa.
- **Rótulos en celdas combinadas en vertical:** cada fila de datos conserva el rótulo del grupo; se avisa.
- **Año repetido en el encabezado de un PDF** («2024 · 2024» tras la revisión): se señala como año
  duplicado.
- Un cuadro con un «Total» cuyo cierre no se pudo comprobar se declara al comienzo aunque no se haya
  identificado la relación candidata.
- Reejecutadas la sexta, la séptima y la octava medición: la salvaguarda declara los casos de lectura
  rota y no agrega avisos en archivos leídos bien. Bancos de autoajuste idénticos a la referencia.
  Tests en `tests/test_octava_medicion.py`.

## Aplicación 0.9.12 · motor multilente-0.9.8 · 14 de octubre de 2026

Arreglos de lo que encontró la séptima medición (`/root/eval-heldout7-20261014`).

- **Llamadas de nota pegadas al número** («171.535*», «1.234 (p)», «98,5¹»): `perfilado.partes_numero`
  quita la marca antes de leer, así la columna se lee entera con su criterio; antes esas celdas se
  leían mil veces más chicas y el informe presentaba el error de lectura como una consulta. La lectura
  avisa cuántas celdas traían la llamada.
- **Signo aislado en el primer o último período** (`controles_excel/series.py`): un único negativo
  entre positivos también se señala en el borde de la serie.
- **Rubro en otra escala con importes de un decimal:** la salvaguarda de «miles leídos como
  decimales» exige exactamente tres decimales; con importes como 34.345,3 la señal no salía.
- Cierres no comprobados con el período como figura en el archivo («2025-09», no su número interno).
- Pendiente anotado: en un cuadro mensual con varias «s/d» en un mes, ese mes se toma como período
  faltante y su cierre no se declara (se declaran las celdas sin dato).
- Bancos de autoajuste idénticos a la referencia; sin alarmas nuevas en los correctos de la séptima.
  Tests en `tests/test_septima_medicion.py`.

## Aplicación 0.9.11 · motor multilente-0.9.7 · 14 de octubre de 2026

Arreglos de lo que encontró la sexta medición (`/root/eval-heldout6-20261014`).

- **Contenido oculto, al comienzo.** Una hoja, filas o columnas ocultas que se leyeron se dicen en la
  primera página del informe ejecutivo (`reporte_ejecutivo._contenido_oculto`), no sólo en el anexo.
- **Cierres no comprobados por «s/d».** `estructura_revision.preparar` registra los períodos de una
  relación corroborada en que el total o un componente no tiene dato (`cierres_sin_comprobar`), y el
  registro de cobertura los declara al comienzo («cierre de «Total» en 2020, 2024»).
- **Revisión de lectura que llega al informe.** Al recibir una tabla confirmada, el servidor recalcula
  las mismas marcas que la pantalla (`ocr_local.celdas_dudosas`: más de un número en la celda, formato
  ambiguo, rótulos genéricos puestos en la revisión) y, si quedaron sin corregir, el informe lo dice al
  comienzo. Los archivos de una carga que se derivaron a la revisión de lectura (`derivados_revision`,
  enviado por la pantalla) se declaran en el informe de los demás.
- **Rubro entero en otra escala** (`controles_excel/rubro_escala.py`, regla `rubro_en_otra_escala`):
  si un «Total» no cierra en ningún período pero cierra en casi todos al multiplicar o dividir UN solo
  rubro por 10, 100 o 1000, se señala esa fila con el factor. No se emite cuando el resto del cuadro
  tiene miles leídos como decimales (la causa es la lectura ambigua, ya declarada).
- Bancos de autoajuste idénticos a la referencia; en los 18 correctos de la sexta medición la señal
  nueva no aparece. Tests en `tests/test_sexta_medicion.py`.

## Aplicación 0.9.10 · motor multilente-0.9.6 · 14 de octubre de 2026

Camino a 1.0.0: los seis casos en que la quinta medición encontró al informe callando algo.

- **Cierre de totales que no se pudo comprobar, al comienzo.** Con una fila de total que no coincide
  con sus componentes en suficientes períodos, el informe decía «no quedaron partes sin leer» y el
  control figuraba como no ejecutado sólo en el anexo (Excel) o en ninguna parte (CSV y PDF).
  `reportes/registro.construir` lo cuenta ahora como control no ejecutado, con su motivo, y va a la
  primera línea; `controles_excel/tablas_planas` y `routers/carga_rapida` conservan la estructura de
  totales de las tablas de CSV y PDF. Sin total en el archivo no se declara nada (no aplica).
- **Números guardados como texto con un solo punto («475.735»).** `pandas` convertía por su cuenta
  las columnas en que todos los textos se podían leer en formato inglés: 475,735 en lugar de 475.735,
  sin aviso. `excel_cobertura.leer_libro` lee sin inferencia de tipos (`dtype=object`) y los
  controles por celda (`controles_excel._formatos_texto`) aplican el mismo criterio por columna que
  la lectura del cuadro: la columna decide; si es ambigua, el cuadro; si no, el punto de miles.
- Bancos de autoajuste idénticos a la referencia (general s7011 164/174, 0 falsas; estructura s7008
  144/150, las mismas 4 falsas previas). Tests en `tests/test_criterio1.py`.

## Aplicación 0.9.9 · motor multilente-0.9.5 · 14 de octubre de 2026

- **Fórmulas con referencias fijas.** El control de fórmula fuera de patrón quitaba los «$» antes de
  comparar: una referencia fija (la fila de pesos `$C$2:$E$2` de un promedio ponderado) cambiaba de
  una fila a otra y el patrón no se reconocía, así que una celda que pasaba a promedio simple no daba
  señal. `_normalize_formula` (services/calculos/excel_utils.py) conserva ahora lo fijo sin signo
  (`R2C3`) y lo relativo con signo (`R+0C-4`); `lenguaje_llano.patron_en_celda` reubica el patrón con
  sus «$». Banco de autoajuste antes/después idéntico: general s7011 164/174 y 0 falsas alarmas;
  estructura s7008 144/150 y las mismas 4 falsas alarmas previas. Tests nuevos en
  `tests/test_lenguaje_llano.py`.
- `TEXT` y `EDATE` se muestran como `TEXTO` y `FECHA.MES`.
- README al día (decía aplicación 0.9.7).

## Aplicación 0.9.8 · motor multilente-0.9.4 · 14 de octubre de 2026

- **«Qué pasó» en lenguaje llano.** Cada observación, de todas las lentes, empieza con una frase que
  nombra la fila y la columna por sus rótulos y dice qué pasó, sin lenguaje de veredicto. La arma el
  código con plantillas por regla (`services/reportes/lenguaje_llano.py`), no la IA, y pasa por
  `sanitizar_texto()` dentro de `normalizar_hallazgo()`. Se guarda en `hallazgos.resumen_llano`
  (migración `20261014_resumen_llano`); los hallazgos anteriores la reciben al mostrarse, sin
  reescribir la base. Orden en pantalla y reportes: qué pasó, pregunta, evidencia, dónde, detalle
  técnico. En el comprobante la frase va delante de la descripción técnica, que no cambia.
- **Fórmulas en castellano** en pantalla, «Qué preguntar al área», reporte por señal y anexo de
  evidencia (`=PROMEDIO(C4:F4)`), con el analizador de openpyxl: textos entre comillas y nombres de
  hoja no se tocan; separador `;` configurable (`FORMULA_SEPARADOR_ARGUMENTOS`). La evidencia guardada
  y el comprobante conservan la fórmula del archivo. Funciones sin traducción quedan en inglés y se
  registran (en los archivos cargados hasta hoy: `TEXT`, `EDATE`).
- Revisado contra las 1598 observaciones de la base: todas con frase específica de 25 palabras o menos,
  ninguna vacía ni con lenguaje de veredicto. Una revisión independiente encontró frases que afirmaban
  algo falso (rango «corrido» que era incompleto o distinto, «único negativo» con un positivo, «por
  encima» con un valor por debajo, correlaciones negativas como «se mueven juntas», Radiólogo contra
  «casos presupuestarios» cuando comparó con el propio archivo, factor de escala de otra referencia,
  dirección física/financiera fija) y un respaldo de «Qué preguntar al área» sin la frase: corregidos,
  con una prueba por caso. Red de seguridad: si una frase quedara con un dato faltante o con lenguaje
  de veredicto, se usa la frase de la lente. Ejemplos públicos regenerados. Tests en
  `tests/test_lenguaje_llano.py`.
- Detección sin cambios (motor multilente-0.9.4). Límite anotado para después: el control de fórmula
  fuera de patrón no reconoce patrones con referencias absolutas (`$C$2`).

## Aplicación 0.9.7 · motor multilente-0.9.4 · 12 de octubre de 2026

- **Conexiones etiqueta la cohorte de cada proyecto.** El cruce abarca toda la cartera, también
  entre cohortes; para que quien decide no confunda de qué cursada viene cada proyecto, cada caso
  lleva su cohorte (`routers/proyectos_ia._cohortes_por_proyecto`). El proyecto no guarda la
  cohorte: se toma de `ActividadVotacion.proyectos_ids`; si figura en más de una actividad se
  muestran todas, y si no figura en ninguna se indica «Sin cohorte asignada». Cada cruce y cada
  oportunidad declaran además qué cohortes reúnen. La pantalla muestra la cohorte en las listas,
  en el selector de proyectos y en el detalle de cada nodo del mapa. Sin migración de base.
  Versión de la respuesta: `cartera-3`. Tests nuevos en `tests/test_conexiones_cartera.py` (3).
- **Ficha técnica:** proveedores descriptos como integraciones con modelos abiertos autoalojados
  (Renderix y Ollama), Anthropic «no habilitado», y la capacidad de que un organismo use un modelo
  autoalojado en su propia infraestructura (el despliegue de referencia corre sobre
  infraestructura de prueba). La conclusión de las mediciones distingue Excel (parejo) de CSV y
  PDF (irregular) y aclara que el PDF se midió en el circuito anterior.
- **Opciones avanzadas en lenguaje llano.** El bloque de casillas pasa a llamarse «Revisiones extra de
  fórmulas · solo archivos Excel» y aclara que las seis lentes, la capa conciliadora y el control básico de
  fórmulas corren siempre. «Activar lente Matemático» decía algo falso —la lente corre en todo análisis—: la
  casilla sólo suma `promedio_informado_simple_con_ponderadores` y ahora se llama «Promedios que no
  ponderan» y viene tildada en la pantalla (la API mantiene su valor por omisión). En el banco s7011 no
  cambia nada —164/174 y ninguna falsa alarma con o sin ella—, porque esas planillas no traen
  ponderadores. Mismos ids y parámetros. Tests en `tests/test_opciones_formulas_ui.py` (4).
- **Banco de autoajuste:** `/home/autoajuste/evaluar.py` saltea el tope diario de IA, que desde su llegada cortaba la
  ronda con HTTP 429 a partir del caso 16.
- **Documento principal v7** publicado en Zenodo el 12/10/2026 (versión v0.7.0):
  DOI 10.5281/zenodo.23329097; serie 10.5281/zenodo.22063241. `DOCUMENT_VERSION = "7"`. El archivo depositado
  (`Gobernanza-v7-12-10.docx`) describe el corte 0.9.6 (1680 pruebas Python y 52 JavaScript) y
  anticipa la etiqueta de cohorte de esta versión.
- Motor sin cambios: bancos y ejemplos públicos idénticos.

## Documento v6 y ajustes con archivos reales · 5 de octubre de 2026

- **Documento principal v6** publicado en Zenodo el 04/10/2026 (versión v0.6.0):
  DOI 10.5281/zenodo.23142298; serie 10.5281/zenodo.22063241. `DOCUMENT_VERSION = "6"`.
- **Prueba con archivos públicos del BID** (IDB Data Wall 2026, 100 hojas; Marco de Impacto,
  consolidado y detalle por proyecto). Sin errores confirmados en los datos del BID; la prueba
  expuso fallas de Gobernanza, corregidas: celdas con fecha (error 500 y fechas como
  milisegundos), año que clasifica filas (formato largo, datos diarios, una fila por país),
  años combinados sobre dos columnas, columnas auxiliares sin encabezado. Data Wall: de 1.679
  a 9 consultas. Bancos de referencia idénticos caso por caso (164/174, top20 157, 0 falsas;
  144/150, 4 falsas); ejemplos públicos idénticos.
- **Exploración con IA**: un elemento que no entra queda fuera y declarado (antes se abandonaba
  toda la exploración); el tope de consultas se informa como exploración parcial, no como
  demora ni advertencia.
- **Login**: un formulario malformado responde 400, no 500 (escáner automático).
- **Rendimiento**: lista de informes de 3,1 a 0,13 s y Actividad de 3,9 a 1,1 s (sin cargar
  datos ni resultados completos; respuesta idéntica).
- **Ficha técnica**: a lo ancho en pantallas grandes y portada con la versión vigente.
- **Fórmula equivalente (07/10)**: una suma escrita con rango (`=+U69+SUM(U72:U80)`) ya no se
  marca como «fórmula fuera de patrón» si suma las mismas celdas que el resto de la fila
  (libro de gasto, «Según categorías»!U81, que aparecía en «No cierra» del informe 306). Un rango
  incompleto se sigue marcando. Banco de valores idéntico (164/174, top20 157, 0 falsas).
- **Conteo de señales explicado (07/10)**: la página 1 cuenta señales de control (señales
  directas más variaciones anuales que integran un caso: 65 + 11 = 76 en el libro de gasto) y el anexo
  cuenta por control (señales directas más resúmenes de contexto: 65 + 16 = 81). El anexo lo
  dice en una frase y una prueba verifica que las cifras cuadren.
- **Limpieza**: README con el documento v6; `.env.example` con «gobernanza»; se retiró
  `services/controles_excel/__init__.py.orig` (copia vieja; nada que faltara en el vigente).

## Aplicación 0.9.6 · motor multilente-0.9.4 · 4 de octubre de 2026

Terreno acotado y declarado: Multilente analiza directo **Excel y CSV**. Los **PDF y las imágenes**
pasan por la revisión de lectura (`/api/ocr`): el PDF con texto se lee con la extracción existente y
el OCR local queda para escaneos e imágenes; la persona ve el original al lado de la tabla editable
(celdas dudosas resaltadas, «completar hacia abajo», formato numérico), confirma y recién ahí
«Analizar esta tabla» envía un CSV revisado. El informe dice arriba «Tabla leída de <archivo> y
revisada por una persona antes de analizar». La carga directa de PDF o imagen responde 422
`requiere_revision_lectura`. FAQ «¿Qué archivos puede leer?» en la presentación y alcance en la ficha.

Probado con el PDF oficial del libro de gasto 2001-2020 (caso del informe 284): los años en celdas combinadas
se marcan como dudosos, se completan hacia abajo y el análisis no da alarmas de período vacío.
Tests nuevos: `tests/test_revision_lectura.py` (15). Motor y ejemplos públicos sin cambios.

## Aplicación 0.9.5 · motor multilente-0.9.4 · 4 de octubre de 2026

Informe para quien decide (solo presentación; no cambia lo que se detecta):

- **Página 1 «Qué preguntar al área»:** cobertura en llano y 5 a 8 consultas agrupadas por causa,
  formuladas como preguntas con cifras es-AR (`services/reportes/consultas.py`).
- **Agrupación por causa** (`casos_revision.agrupar_consultas`): misma serie en períodos contiguos;
  cierres del mismo período con la misma diferencia (componente como origen, consolidado como efecto).
- **Detalle** en tres renglones por consulta; **anexo técnico** en el mismo PDF (resto de consultas en
  tabla, variaciones, IA, lectura, metodología y código de la corrida).
- **Formato único es-AR** (`formato.py`): «374,08», nunca notación científica, unidades legibles;
  flecha visible en el PDF (DejaVu); impacto > 100 % explicado.

Caso de referencia: libro de gasto 2001-2020 oficial, 62 casos agrupados en 52 consultas, 8 en la portada.
Tests nuevos: `tests/test_informe_decisor.py` (8). Banco sin cambios (144/150 · 4 falsas;
164/174 · top20 157 · 0 falsas). Ejemplos públicos sin cambios.

## Aplicación 0.9.4 · motor multilente-0.9.4 · 4 de octubre de 2026

Pendientes de la cuarta medición:

- **Formato numérico en PDF por cuadro y columna** (`_formato_numerico_pdf`): «1,234,567» y
  «2,078,000.0» en inglés; desempate con valores inequívocos del cuadro, del documento y del texto;
  si sigue ambiguo se declara «formato numérico ambiguo». «Table N» se reconoce como cuadro.
- **Salvaguarda de cobertura:** valores numéricos fuera de los cuadros leídos se declaran «Sin
  controlar: hoja X, filas a-b…». Encabezado de períodos pegado al cuadro anterior se separa.
- **Períodos con marca** («est.», «prel.», «proy.», «(1)»); «2025 (p)» en años verticales entra en
  los controles.
- **PDF:** página sin texto extraíble cuenta como no leída; PDF dañado nombra el archivo y, en carga
  mixta, el resto se analiza.
- **CSV:** fila con más campos que el encabezado se descarta y se declara (o se repara si el campo de
  más está vacío al final), también en `tablas_planas`.
- **Volatilidad por cuadro** (MAD de pasos logarítmicos, descontada la tendencia por rubro y el
  movimiento por período): `pico_aislado`, `escala_extremo`, `valor_aislado_en_cuadro` y
  `movimiento_compensado` son ALTA solo si superan 4 (o 3) desvíos.
- **Totales cruzados** (`controles_excel/totales_cruzados.py`): si el total de fila y el de columna
  no cierran por la misma diferencia, se señala la celda de la intersección.
- **Escala fila × columna** (`valor_fuera_de_escala_fila_columna`).

Tests nuevos: `tests/test_pendientes_094.py` (49). Banco: estructural 144/150 · top20 75 · 4 falsas;
valores 164/174 · top20 157 · 0 falsas. Ejemplos públicos sin cambios.

**Quinta medición con archivos nuevos** (`/root/eval-heldout5-20261004`, 91 archivos, series
realistas): Excel 25/30, CSV 10/12, PDF 9/12 en la celda correcta (cumple 3); 1 señal ALTA en 18
correctos y 0 en 3 volátiles (cumple 2). Criterio 1: 85/91; en silencio, números guardados como
texto en Excel («475.735») leídos como decimales en algunas columnas y el control de cierre de
totales no ejecutado sin aviso en CSV/PDF cuando un rubro entero está ×1000; en Excel ese «no
ejecutado» no figura al comienzo. Otros: período que repite entero el anterior sin señal (4 de 5),
un valor con otro formato vuelve ambigua una columna de PDF en inglés, «página 3 fuera del límite»
falso y filas CSV marcadas «sin archivo de origen» en carga mixta.

## Aplicación 0.9.3 · motor multilente-0.9.3 · 3 de octubre de 2026

- **PDF:** una columna de enteros de hasta tres cifras en la que los mayores llevan punto cada tres
  cifras («984», «1.054») usa el punto como miles (`carga_archivos._normalizar_miles_pdf`).
- **Informe ejecutivo:** lo no leído y lo no controlado, con su motivo, va en la línea siguiente al
  alcance, no sólo en «Qué se leyó».

Banco sin cambios (144/150 · 4 falsas; 164/174 · 0 falsas).

**Cuarta medición con archivos nuevos** (`/root/eval-heldout4-20261003`, 84 archivos): Excel 20/25,
CSV 7/10, PDF 10/15 en la celda correcta (cumple 3). 18 señales ALTA en 18 correctos, casi todas
`pico_aislado` sobre series sintéticas uniformes (no cumple 2). Criterio 1 no cumple: PDF en inglés
con coma de miles leídos como decimales (`pdf_controles._numero_pdf`, `perfilado.formato_columna`),
otra disposición de cuadros apilados que se pierde, columna «2025 (p)» descartada, página escaneada
de un PDF contada como leída, filas de CSV con campos de más corridas una columna, y PDF dañado
rechazado sin nombrar el archivo. Quedan como siguiente trabajo.

## Aplicación 0.9.2 · motor multilente-0.9.2 · 3 de octubre de 2026

Corrige el criterio «dice qué no revisó», que la segunda medición no cumplió:

- **Cuadros apilados:** una fila de encabezado nueva tras una fila vacía o un título abre un cuadro
  propio (`excel_estructura.encabezados_apilados`); si no se puede separar, se declara «sin
  controlar» con motivo. Un control que corrió en parte de los cuadros lo dice, y la cobertura ya no
  sale completa.
- **Unidad en el encabezado:** «2024 (miles de asistentes)» es período con unidad anotada; si difiere
  del resto, `unidad_columna_distinta`. Una columna con año en el rótulo que no se controla se
  declara.
- **Controles en cero:** «0 cierres verificados» pasa a «no ejecutado» con motivo.
- **CSV es-AR:** separador por frecuencia, encabezado por estructura saltando títulos, filas con
  campos de más declaradas, motivo exacto si no hay filas.
- **Fórmulas sin valor:** una hoja hecha solo de fórmulas se calcula con el evaluador; si no se
  puede, el motivo lo dice.
- «Total» en la columna de años no es período; formato largo con una fila en otra unidad da
  `unidad_fila_distinta` en esa fila y no alarmas de período; PDF muestra el rótulo de período
  original y detecta el año duplicado. Conteos y listas de celdas coinciden («se muestran 5 de 6»).

Tests nuevos: `tests/test_cobertura_declarada.py` (31).

Banco: estructural 144/150 · 4 falsas; valores 164/174 · top20 156 · 0 falsas (sin cambios por caso).

**Tercera medición con archivos nuevos** (`/root/eval-heldout3-20261003`, 87 archivos): Excel 33/40,
CSV 13/15, PDF 13/15 en la celda correcta; 0 señales ALTA en 17 correctos. Cumple 2 y 3; el 1 no,
porque en tres PDF «1.054» se leyó como decimal sin aviso.

## Aplicación 0.9.1 · motor multilente-0.9.1 · 3 de octubre de 2026

Corrige lo que mostró la medición con archivos nuevos de la 0.9.0 (Excel 31/33, CSV 0/12, PDF 3/12):

- **CSV y PDF con controles por celda.** `controles_excel/tablas_planas.py` arma en memoria un libro
  con una hoja por tabla de CSV o PDF con texto (sin columnas identificatorias y con texto
  redactado) y la pasa por los mismos controles que un Excel. Las ubicaciones se informan como el
  usuario las ve: «archivo.csv · fila 4, columna G» o «archivo.pdf · página 1, cuadro 1, fila 4,
  columna 2022». Las listas de registros (transacciones, microdatos) no se controlan así.
- **Períodos** «2024-Q1», «2025-T1» y «2024-12» reconocidos por su forma en el período observado.
- **Encabezado temporal** solo si la fila es de años plausibles; si una fila tomada como encabezado
  trae importes, se avisa en lo no leído.
- **Escala por fila:** un rubro chico de manera consistente en todas sus columnas no es un error de
  escala de una celda.
- **Registro:** una hoja oculta leída no figura como «sin leer»; un archivo no leído no lista
  controles ejecutados.
- **Rendimiento:** identidades entre filas con índice de valores (una tabla de 1000 filas pasó de
  33 s a menos de 1 s en ese control); igualdades entre filas que pueden darse por azar no se marcan.

Tests nuevos: `tests/test_csv_pdf_controles.py` (26).

Banco: estructural s7008 144/150 · top20 73 · 4 falsas; valores s7011 164/174 · top20 156 · 0 falsas
(sin cambios por caso respecto de 0.9.0). Los 8 pares de ejemplos públicos dan lo mismo que en 0.9.0.

**Segunda medición con archivos nuevos** (`/root/eval-heldout2-20261003`, 91 archivos, 18 temas
distintos): Excel 30/35 (86 %), CSV 9/15 (60 %), PDF 13/15 (87 %) en la celda correcta; 1 señal
ALTA en 17 correctos. Cumple los criterios 2 y 3; **no cumple el 1**: un segundo cuadro en la misma
hoja y una columna con la unidad en el encabezado quedan sin controlar y sin aviso, y algunos CSV
con línea de título se rechazan con un motivo inexacto.

## Aplicación 0.9.0 · motor multilente-0.9.0 · 3 de octubre de 2026

Correcciones de la evaluación adversarial interna del 3 de octubre (archivos y arneses en
`/root/eval-gobernanza-20261003`), más los cambios de producto de los cuatro módulos.

**Lectura.** Encabezado por estructura (no por posición), lector numérico es-AR/inglés, CSV con
separador y codificación detectados, PDF con herencia de encabezados entre páginas, tipo de archivo
por contenido (un `.xls` que por dentro es xlsx se lee). El reporte lleva `lectura_archivos` y
`avisos_lectura`: lo que no se pudo leer abre el informe.

**Controles.** Modelo común de cuadro (`controles_excel/modelo.py`, `periodos.py`, `ejes.py`):
ejes temporales en filas o columnas, formato largo, encabezados de dos niveles, notas y unidad.
Evaluación de fórmulas sin valor guardado (`evaluador.py`), valor fijo frente a la fórmula vecina
trasladada (`formulas_fijas.py`), controles transversales (`transversal.py`: signo, porcentajes que
suman 100, indigencia ≤ pobreza, activo = pasivo + PN, valor fuera de escala, valor copiado) y
matriz de valores aislados (`matriz.py`). Nuevas reglas presupuestarias: devengado > comprometido,
comprometido > vigente y crédito inicial + modificaciones ≠ vigente
(`tests/test_presupuesto_compromiso.py`).

**Cruces.** Ficha de comparabilidad por cuadro (concepto, unidad y escala, moneda, cobertura y
corte) antes de comparar ediciones: lo no comparable es una nota, no una señal por fila. Un cuadro
en «miles de millones» frente a «millones» se compara y se informa como cambio de unidad. El
emparejamiento de cuadros pondera filas por rótulo, acuerdo de valores, hoja y posición dentro de
la hoja.

**IA.** Las lecturas de los modelos se validan contra los valores del archivo
(`triangulacion_validacion.py`); se descartan las que siguen instrucciones incrustadas y las de
proveedores fallidos (que se registran como fallidos, no como desacuerdo).

**Informe.** Registro de revisión con celdas, agrupación de casos por eje y formato es-AR.

**Producto.** Tutora en voseo y con versión para organizaciones; R-1 lo inicia el equipo docente;
Incubadora reconoce la devolución docente aunque el estado siga «entregado»; Monitoreo habilitado
solo para el proyecto ganador del piloto; uso de Conexiones registrado (una marca cada 30 min).

Banco (copias congeladas, `LIMITE_ANALISIS_IA_DIA=0`):

| Semilla | 0.8.74 | 0.9.0 |
|---|---|---|
| Valores s7011 | 164/174 · top20 155 · 0 falsas | **164/174 · top20 156 · 0 falsas** |
| Estructural s7008 | 143/150 · top20 73 · 4 falsas | **144/150 · top20 73 · 4 falsas** |

Evaluación adversarial, mismos archivos usados para corregir: errores en la celda exacta 2/56 → 49/56;
archivo correcto en formato largo 207 señales altas → 0. **Medición con archivos nuevos**
(`/root/eval-heldout-20261003`, 76 archivos, criterios fijados antes de medir): Excel 31/33 en la
celda exacta, CSV 0/12, PDF 3/12; 1 caso alto (4 señales) en 15 correctos; una hoja con el
encabezado mal leído sin aviso. **No cumple los criterios de uso**: los controles por celda no
corren todavía sobre tablas de CSV ni de PDF.

## Motor multilente-0.8.72 · 2 de octubre de 2026

Cuatro mejoras, cada una con su prueba en `tests/test_motor_0872.py` (fallan con la 0.8.71 y pasan
con esta versión):

- **Notas de cobertura sin datos personales.** El Conciliador copiaba hasta 180 caracteres de una
  celda con una nota de cobertura a la evidencia, que puede llegar al prompt de los modelos. Ahora,
  si la celda está en una columna de notas, observaciones, comentarios o personas, sólo se registra
  dónde está («nota de cobertura en la fila N»); de cualquier otra columna se copia pasada por
  `sanitizacion.redactar_texto_libre` (DNI, CUIT, correos, teléfonos, expedientes).
- **Cambio de escala entre ediciones.** Cuando en todos los años comunes (al menos tres) la razón
  nueva/anterior de una fila es la misma potencia de 10 (×1000, ×100, ×10 o sus inversas, ±1 %) y
  el resto del cuadro no cambió, la regla `cambio_de_escala_entre_ediciones` lo rotula «Cambio de
  escala» con prioridad 110 (antes era una `serie_revisada_entre_ediciones` de prioridad 75). Las
  filas con fórmula («Resto», «Total») que cambian por arrastre no cuentan como cambio del cuadro.
  Si el cuadro entero se reexpresó, sigue siendo una revisión.
- **Presupuesto contra ejecutado en organizaciones.** Un cuadro Programa/Presupuesto/Ejecutado con
  rótulos como «Salud» u «Obras» daba 0 hallazgos en organización porque sólo se miraban filas de
  egreso. Con columnas que se llaman presupuesto/presupuestado y ejecutado/real, la sobreejecución
  fuerte (más de 10 %) se señala en toda fila que no sea total ni ingreso. En público se aplica
  igual (p. ej. con una columna «Real»), salvo que devengado/pagado contra vigente ya mire ese par:
  no se duplica.
- **Transferencias entre rubros en cuadros cortos.** Con cuatro períodos la serie propia no tenía
  dos pasos para estimar su variación habitual y la regla no corría. Ahora se estima con los cambios
  de participación en el total de los rubros del mismo cuadro, en los pasos que no tocan el período.

Banco (copias congeladas, `LIMITE_ANALISIS_IA_DIA=0`):

| Semilla | 0.8.71 | 0.8.72 |
|---|---|---|
| Valores s7011 | 162/174 · top20 157 · 0 falsas · transferencia 7/15 | **164/174 · top20 159 · 0 falsas · transferencia 9/15** |
| Valores s7021 (control) | 162/174 · top20 148 · 5 falsas · transferencia 5/13 | **163/174 · top20 149 · 5 falsas (las mismas) · transferencia 6/13** |
| Estructural s7008 | 141/150 · top20 72 · 4 falsas · unidades_mezcladas 20/23, top20 0 | **143/150 · top20 83 · 4 falsas (las mismas) · unidades_mezcladas 22/23, top20 11** |

## Motor multilente-0.8.71 · 2 de octubre de 2026

Una auditoría del motor reprodujo nueve problemas. Se corrigen acá, cada uno con su prueba en
`tests/test_auditoria_motor_0871.py` (fallan con la 0.8.70 y pasan con esta versión):

- **Privacidad: personas en el prompt de la IA (prioridad máxima).** Las columnas que nombran
  personas («Agente», «Empleado», «Titular», «Paciente», «Docente», «Socio», «Afiliado», «Alumno»,
  «Destinatario», «Contacto», en singular o plural) se excluyen cuando sus valores son texto y se
  conservan sólo si son cifras: «Agentes» = 120 sigue siendo un conteo válido. La lista que
  permitía «agentes» por el rótulo ya no lo hace (regla de la casa: una columna se conserva por
  sus valores, nunca por su rótulo). Tampoco se usan como rótulo de fila, ni las columnas de
  observaciones o comentarios. En texto libre se enmascaran además «DNI 12.345.678»,
  «Documento: 30.123.456», «dni nro 12345678» y «n°», el CUIT con puntos, espacios o sin
  separador (sólo con dígito verificador válido) y los teléfonos «+54 9 11 4555 1234»,
  «011 4555-1234» y «4555-1234». Los códigos presupuestarios con guiones, los años, los rangos
  («2019-2020», «ISO 9001-2015») y los montos no se tocan. Los expedientes sistema de expedientes quedan, como antes.
  Se verificó el recorrido real sanear → lentes → `triangulacion._prompt_usuario`: ni el nombre,
  ni el DNI ni el teléfono llegan al prompt.
- **Total de filas con columna temporal constante.** Con una columna «Ejercicio» = 2024 la regla de
  la 0.8.70 tomaba esa columna como rótulo y no encontraba ninguna fila «Total». Ahora busca la
  fila de total en la columna de texto que la contiene.
- **Roles de columna por palabra completa.** «Recursos humanos», «Gasto mano de obra», «Daños» o
  «Comestibles» dejaban de analizarse por temporales; «Personal», «Gasto en personal», «Número de
  casos» o «Documentos tramitados», por identificadores; «Proyectos aprobados» o «Centros de
  salud» con cifras, por dimensiones. Un negativo en «Gasto en personal» vuelve a ser señal (en
  organizaciones, una columna de gasto entera en negativo es convención contable y no se señala).
- **Conciliador.** Bajaba de alta a media toda imposibilidad que mencionara devengado, pagado,
  crédito o vigente aunque el archivo no tuviera ningún artefacto técnico. Ahora sólo modula con
  las pistas que él mismo calcula (crédito cero, reversas, retrocesos, ratios extremos, notas de
  cobertura) y, en el ámbito «organización», no modula por vocabulario de presupuesto público.
- **«Presupuesto» como crédito vigente.** En el ámbito público, una columna «Presupuesto» o
  «Presupuestado» sin otra calificación se toma como crédito vigente cuando no hay otra: un
  Programa/Presupuesto/Ejecutado con sobreejecución da hallazgo (antes daba 0).
- **Radiólogo.** Con tres o cuatro casos casi iguales, un +3 % daba «alta» a cinco sigmas. Ahora
  exige un cambio de al menos 10 % sobre la media, un piso de dispersión del 2 % de la media y
  cinco casos para «alta».
- **Orquesta.** Trataba como porcentaje cualquier columna con valores ≤ 100. Ahora decide por el
  nombre (%, porcentaje, tasa, participación; avance o cumplimiento si están en [0, 100]) o por
  valores en [0, 100] con decimales y sin rol de importe.
- **Cronista.** En una serie plana la mediana de cambios es cero y la regla callaba: un ×10 no se
  veía. Se usa como piso el 1 % del nivel mediano.
- **Total verificado.** «% del total» y otras columnas no sumables ya no cuentan como partes.

El banco estructural (s7008) se corre con `--con-anterior` (lo hace `ronda-estructura.sh`).

## Motor multilente-0.8.70 · 29 de septiembre de 2026

Regla nueva del Ajedrecista: **total de filas que no cierra en una tabla de un solo período**. Era
el punto ciego más visible en presupuesto contra real (el «Total egresos» inflado en 1,5 millones de
la pyme de prueba) y en cuadros de un solo corte: la conciliación por series exige cuatro períodos.
Una fila «Total…» o «Subtotal…» se compara con la suma de las filas de su grupo, y la relación sólo
se afirma si en la misma fila otra columna sí cierra (así se sabe que la estructura es una suma).
Se descartan los grupos con subtotales anidados, las columnas de porcentajes, tasas, promedios,
desvíos o diferencias (derivadas: repetirían el mismo error) y las tablas anchas de cuatro o más
períodos, que siguen en la conciliación por series. Tolerancia: 0,2 % o 0,05, y nunca menos que
media unidad del último decimal por cada fila sumada (tablas redondeadas). Tras la revisión
independiente también se descartan las columnas de valores unitarios, medias, participaciones,
crecimientos y conteos únicos, y cualquier «total» que queda entre el menor y el mayor de
componentes positivos: eso es un promedio o una tasa, nunca una suma. «Totales» también cuenta.

Banco de autoajuste con los mismos casos: s7011 162/174 (0 falsas); s7008, ver BITACORA de autoajuste.

## Motor multilente-0.8.69 · 28 de septiembre de 2026

Una segunda revisión independiente del código del día (0.8.65 a 0.8.68) reprodujo nueve
problemas; ninguno crítico. Se corrigen acá, cada uno con su prueba:

- **Pantalla de progreso.** Decía «exploración del libro completada» en informes sin contexto
  semántico (CSV, PDF, informes viejos): ahí sólo hubo lectura de señales, y ahora lo dice así. Si
  un modelo falla en las dos tareas, se nombran las dos.
- **Libros que se inflan.** El control de la 0.8.66 se esquivaba renombrando el .xlsx a .xls:
  ahora se valida por contenido (firma ZIP), no por extensión.
- **Presupuesto contra real.** La 0.8.65 dejó de reconocer «Real_2023» o «gasto_real» (el límite
  de palabra no corta en «_»); vuelve a reconocerlos sin tomar «Actualización» ni «Realizado».
  «Efectivo» dejó de contarse como el real en la 0.8.65 a propósito: en contabilidad suele ser caja
  («Saldo efectivo»).
- **Privacidad y montos.** Bajo un rótulo de importe («Deuda con proveedores») un «1.500.000» se
  leía como DNI con puntos y la columna se excluía. Ahí ya no se aplica la forma de DNI, y un número
  de 11 cifras sólo cuenta como CUIT si su dígito verificador es válido; en rótulos de actor
  («Clientes»), cualquier número con forma de CUIT se sigue excluyendo. La 0.8.65 también achicó la
  lista de «Nombre de…» que se conservan (quedan indicador, programa, rubro, producto, sector,
  concepto, meta, KPI, servicio, sucursal, categoría): «Nombre del proyecto», «del área», «de la
  cuenta» o «de la actividad» se excluyen porque pueden traer nombres de personas.
- **Franja pública de uso.** Contaba la cuenta de prueba que las métricas internas excluyen
  (`USUARIOS_EXCLUIDOS_METRICAS`); ahora usa la misma exclusión. Si la base no responde, no se la
  vuelve a consultar durante un minuto.
- **Reporte.** «Exploración completada» a secas se contradecía con «completada por 2 de 5
  modelos»; en análisis nuevos dice cuántos. Los informes ya guardados conservan su texto.

## Motor multilente-0.8.68 · 28 de septiembre de 2026

La pantalla de progreso del informe 245 decía «Evolución temporal: 259 señales para revisar»
mientras el comprobante separaba esas 259 variaciones anuales como contexto (agrupadas en 16) y no
dejaba ninguna señal temporal de error. Ahora cada lente informa cuántas de sus señales son
contexto y la pantalla las nombra así: «259 variaciones separadas como contexto, no como error».

En la misma pantalla:
- «No aplicable» (un control que no corresponde a ese tipo de archivo) deja de verse como alerta:
  «Antecedentes comparables: no corresponde a este archivo», con estilo informativo. «No evaluable»
  sigue como aviso.
- La exploración de la IA se explica sin jerga: «La respuesta no respetó el formato requerido. No
  afecta a los controles automáticos.» en lugar de «local-1: Respuesta no utilizable tras
  validación de esquema…».
- «No produjo señales comunicables» pasa a «Sin señales para revisar».
- El detalle de los avisos, rosado pálido sobre crema, pasa a un marrón legible.

## Motor multilente-0.8.67 · 28 de septiembre de 2026

En el comprobante del informe 244 (libro por provincia 2016–2023, 27 hojas, 172 cuadros) el resumen «Apoyo de
modelos de IA» decía «respuesta estructurada utilizable» para GPT, Gemini, Renderix y Llama,
mientras el detalle técnico mostraba 1053/1053 elementos para GPT y 0/1053 para los otros. No era
un error de datos: cada modelo hace dos tareas y el resumen sólo contaba la primera. Leer las 31
señales numéricas lo completaron los cuatro; explorar el contexto del libro, sólo GPT (Gemini sin
cuota, 429; Renderix y Llama fuera de esquema; DeepSeek cortado por extensión).

Ahora cada modelo muestra las dos: «lectura de señales utilizable (intentos: 2); exploración del
libro no completada: el proveedor no tenía cuota disponible», y una línea final dice cuántos
completaron la exploración. En la pantalla, el resumen aclara que cuenta la lectura de señales y
que la exploración se informa aparte. Los datos guardados no cambian; el comprobante se vuelve a
generar con el texto nuevo al descargarlo.

Mismo día, con el informe 245 (libro de gasto 2001–2020, la publicación oficial sin modificar): el reporte
completo tenía la misma confusión en «Comparación entre lecturas de IA» («respondió y su lectura
fue incorporada»). Ahora dice «leyó las señales…» y agrega el estado de la exploración; un corte
por tiempo («timed out») se nombra como tal en lugar de «no se completó».

## Motor multilente-0.8.66 · 28 de septiembre de 2026

Cierre del recorrido del 28/09:

- **Libros que se inflan al abrirse.** Un .xlsx es un ZIP y se lee varias veces (pandas, openpyxl,
  fórmulas, controles). Sólo se limitaba el tamaño subido (30 MB), no el descomprimido: un libro
  armado para inflarse podía agotar la memoria del servicio. Ahora se rechaza antes de leerlo si
  supera 250 MB al abrirse (el mayor del corpus ocupa 2 MB).
- **Eventos de aprendizaje.** `GET /api/aprendizaje` devolvía a cualquier usuario los últimos 200
  eventos de todos, con usuario, informe y contenido. Las métricas agregadas siguen completas; el
  detalle lo ve el admin y cada participante ve los propios.
- **Aviso por correo al encolar un análisis.** `POST /jobs/informes/{id}/analizar` aceptaba
  cualquier texto como dirección; ahora aplica la misma validación que la carga.
- **Textos del reporte para cualquier ámbito.** «No sustituye la decisión institucional»,
  «conveniencia institucional», «políticamente neutral» y «actualización presupuestaria posterior,
  ampliación/compensación» pasan a formas que sirven a un organismo y a una organización.

## Motor multilente-0.8.65 · 28 de septiembre de 2026

Una revisión independiente del código de la 0.8.63 y la 0.8.64, hecha el mismo día, reprodujo
cuatro problemas que la suite y el banco de autoajuste no cubrían. Se corrigen acá, cada uno con
su prueba (`tests/test_revision_final_20260928.py`):

- **Privacidad.** El filtro de alcance agregado conservaba una columna de actores por su rótulo
  («Proveedores nuevos», «Clientes activos», «Área responsable») aunque trajera nombres, y un
  plural con cifras aunque fueran CUIT sin guiones o DNI con puntos. Ahora el rótulo nunca alcanza:
  se conserva sólo si los valores son cifras agregadas, y cualquier valor con forma de CUIT o DNI
  (o enteros distintos de 7 u 8 cifras) la excluye. «Expedientes», «Personas» y demás plurales, que
  antes no se reconocían como sensibles, ahora sí.
- **Teléfonos.** Sin etiqueta, sólo se redactan formatos inequívocos (11-4555-1234, 15-…,
  0351-455-1234). Códigos presupuestarios como «11-001-0001» o rangos «2023-2024-2025» se tapaban
  como teléfonos, en los datos y en la pregunta del participante.
- **Sector público.** La convención de egresos en negativo corría en cualquier ámbito y se comía
  negativos reales de un informe público («Gastos en personal» −900). Ahora rige sólo en
  organizaciones: el ámbito público vuelve a comportarse como antes de la 0.8.63.
- **Presupuesto contra real.** La regla de organizaciones podía tomar una columna de comparación
  («Actual vs presupuesto», «Cumplimiento del presupuesto») como el presupuesto, o comparar
  «Real 2023» contra «Presupuesto 2024». Ahora descarta columnas de comparación, exige el mismo año
  cuando los rótulos lo tienen y no elige si hay más de un «real» posible.
- **Streaming.** Una respuesta en streaming reanuda el análisis con una copia nueva del contexto:
  las lentes posteriores al primer evento perdían el ámbito y las columnas declaradas como código.
  El análisis redeclara ambos antes de cada paso.

## Motor multilente-0.8.64 · 28 de septiembre de 2026

Al cargar un informe ahora se elige de quién es: **organismo público** (por defecto, y lo que se
aplica a todo informe anterior) u **organización** (empresa, cooperativa, ONG, universidad). El
valor queda en las opciones técnicas del informe y se declara al empezar cada análisis, con el mismo
patrón que las columnas declaradas como código (`services/ambito.py`).

En una organización:

- No se infiere el dominio presupuestario público: «Presupuesto vigente» y «Pagado» no implican
  ese régimen. Una cooperativa con esos rótulos recibía «el devengado no debería superar el crédito
  vigente» sobre una línea de ingresos, donde superar lo presupuestado es favorable.
- El Ajedrecista reemplaza las tres reglas de etapas (devengado, pagado, crédito vigente) por una
  sola: en filas de egreso, el gasto real que supera lo presupuestado, comparando magnitudes para
  admitir egresos en negativo y dejando fuera totales y resultados. En ingresos no se señala.
- El Conciliador no usa crédito cero, reversas ni ratios ejecución/crédito.
- La lectura con IA recibe una instrucción de vocabulario: presupuesto, real, ingresos, egresos,
  resultado; nunca crédito vigente, devengado, organismo, jurisdicción ni gobierno.

También, en cualquier ámbito: cuando un archivo carga los egresos en negativo, un negativo sólo se
señala en filas de ingreso («Remuneraciones» o «Mantenimiento de redes» no tienen por qué estar en
una lista de egresos para no ser marcadas); «servicio» y «tasa» dejan de contarse como egreso
porque también nombran ingresos.

La pantalla de carga pregunta «¿De quién es el informe?» y el dominio «Presupuestario» pasa a
llamarse «Presupuesto público (crédito, devengado, pagado)».

## Motor multilente-0.8.63 · 28 de septiembre de 2026

La revisión del 28/09 probó el motor con planillas típicas de organizaciones que no son del
Estado —presupuesto contra real de una pyme, estado de resultados mensual, tablero de indicadores,
ejecución de una cooperativa— y encontró que varias fallaban antes de llegar a las lentes:

- Un presupuesto contra real con título arriba no cargaba («no tiene filas con datos»): la
  detección de encabezados sólo reconocía vocabulario presupuestario público y no normalizaba
  acentos. Ahora reconoce presupuesto, real, desvío, ventas, costo, gasto, ingreso, egreso,
  resultado, margen, meta, cumplimiento y los nombres de los meses.
- El filtro de alcance agregado borraba columnas de totales por su rótulo: «Clientes activos»,
  «Cantidad de beneficiarios», «Deuda con proveedores», «Facturación», «Área responsable»,
  «Nombre del indicador». Ahora conserva los rótulos de conteo o monto y los plurales con valores
  sólo numéricos; los rótulos nominales (nombre, DNI, CUIT, correo, teléfono, legajo, domicilio)
  se siguen excluyendo siempre. De paso, «Razón social» con espacio no se excluía: ahora sí.
- Los egresos cargados en negativo por convención contable se marcaban como imposibles. La
  convención se reconoce sólo si al menos dos filas de egreso están todas en negativo; un signo
  invertido en una sola celda se sigue detectando.
- Desvío, margen, ganancia, pérdida, excedente, superávit y déficit admiten negativos; el Rizoma
  deja de proponer como asociación un desvío con el real del que se calcula.
- Una tasa («Rotación de personal %») se tomaba como categoría y armaba series «NPS · 3».
- En remuneraciones, un salto de junio o diciembre se presenta con el contexto del aguinaldo y
  severidad media, no como cambio de régimen.

Medición en el banco de autoajuste, antes y después, con los mismos casos: valores s7011
162/174 → 162/174 (0 falsas alarmas en ambos), estructural s7008 141/150 → 141/150 (4 falsas en
ambos), sin diferencias por tipo. En las planillas de organizaciones, el tablero de indicadores pasa
a detectar las ventas multiplicadas por diez que antes se le escapaban. Las reglas presupuestarias
públicas siguen aplicándose a una cooperativa que usa esos rótulos: eso requiere elegir el ámbito
al cargar y queda para la próxima versión.

## Motor multilente-0.8.62 · 27 de septiembre de 2026

Verificando con el archivo de ejemplo que un cursante reportó el 25/09 —el que mostraba «Sólo pudo
leerse el 0 % del archivo» con tres revisiones sugeridas debajo— confirmé que esa contradicción ya
no aparece: la pantalla dice ahora «5 filas de datos incorporadas · 1 de 2 hojas con datos» y
explica que la cobertura de series temporales no se pudo calcular, que es la verdad para una tabla
larga sin cuadros por período.

Pero en esa misma línea estaba «1 de 2 hoja(s) con datos». La forma abreviada seguía viva en
cuarenta y cinco lugares más: «fila(s) agregada(s) analizadas», «hallazgo(s)», «página(s)»,
«lente(s) activa(s)», «control(es) específico(s)», «registro(s)», «paso(s)», «columna(s)
mensuales». Los cursantes la marcaron como jerga y descuido, se corrigió a mano tres veces y volvió
a aparecer.

Ahora no queda ninguna, y una prueba la busca donde vive: recorre los literales de texto de
`services/`, `routers/`, `core/` y de la pantalla —con `tokenize` en Python, para no confundir un
texto con una llamada como `mapa_periodos(s)`— y falla si vuelve. La pantalla tiene su propio
`contar()`, con el mismo criterio que `services/plural.py`.

Tres pruebas existentes cambiaron su expectativa porque cambió el texto del producto: «92 período(s)»
pasa a «92 períodos», «1 de 2 hoja(s) con datos» a «1 de 2 hojas con datos», y con un solo registro
pendiente el monitoreo dice «1 registro que todavía requiere seguimiento» en lugar de «requieren».
Se corrigieron las expectativas, no el producto.

Lo que sí se conserva es la reparación de los informes viejos: el reporte sigue reconociendo
«retrocesos en 2 serie(s) acumuladas» en las descripciones ya emitidas, porque esas no se reescriben.

## Motor multilente-0.8.61 · 27 de septiembre de 2026

Buscando otra cosa en un reporte real apareció «### 2002 · una jurisdicción · cuadro 73 · **1 señales**».
La 0.8.49 había arreglado el «1 señal(es)» de un texto; el problema era más ancho y estaba en seis
lugares más: «1 casos de revisión», «1 hojas», «1 grupos anuales», «1 variaciones anuales».

Ahora el plural lo decide un solo módulo —`services/plural.py`— y los reportes, la devolución, la
lectura anual y el contexto agrupado lo usan. `contar(1, "hoja")` da «1 hoja» y `contar(2, "hoja")`
da «2 hojas»; `senales(0)` sigue distinguiendo «sin señales» de «0 señales», que no es lo mismo en
un informe.

Siete pruebas nuevas, entre ellas la que arma un reporte ejecutivo completo con una sola señal y
falla si aparece un número uno seguido de un plural. Ningún cambio en lo que el motor detecta.

Lo que **no** cambia son los informes ya emitidos: la descripción del contexto agrupado se guarda
con el hallazgo, así que un informe viejo sigue diciendo lo que dijo el día que se emitió. El texto
nuevo rige para los análisis nuevos, que es la única forma de corregir sin reescribir el registro.

## Motor multilente-0.8.60 · 27 de septiembre de 2026

Mirar la pantalla antes de darla por hecha: el mapa de pasos de la versión anterior se dibujaba en
un SVG estirado al ancho de la tarjeta, y los nodos se veían como óvalos. Ahora son nodos y tramos
de HTML, que no se deforman con el ancho, y conservan el rótulo accesible que describe el avance.

## Motor multilente-0.8.59 · 27 de septiembre de 2026

«Le aportaría incorporar a cada recorrido una síntesis con lenguaje para todo perfil de usuario, por
qué debería pasar por cada instancia y qué valor agrega cada una; y un registro visual de dónde estoy
y hacia dónde voy.» Estaba anotada como decisión de diseño por la palabra «visual», y lo que pedía de
fondo no requería ninguna decisión.

Cada tarjeta de la pantalla de inicio muestra ahora el recorrido en una línea, sus pasos con lo que
cada uno aporta, y el paso siguiente marcado. El avance no se supone: lo informa un endpoint nuevo
—`GET /proyectos-ia/mi-recorrido`— que **sólo lee**. Eso no es un detalle: el endpoint que ya existía
para traer el proyecto propio lo crea si no existe, así que usarlo en la pantalla de inicio le habría
abierto un proyecto vacío a cualquiera que entrara. Seis pruebas cubren el contrato, incluida la que
verifica que leer el recorrido no escribe nada y la que verifica que el informe de otra persona no
cuenta como propio.

Los pasos que el sistema no puede verificar —verificar un hallazgo en el archivo, comparar proyectos
en el mapa, la implementación real— lo dicen en lugar de quedar como pendientes ambiguos: «el sistema
no puede darlo por hecho». Y si el estado no está disponible, el mapa se dibuja igual, sin avance:
la síntesis y el aporte de cada paso no dependen de la red.

Cinco pruebas de interfaz nuevas, incorporadas a la barrera de calidad.

## Motor multilente-0.8.58 · 27 de septiembre de 2026

El «señal(es)» que quedaba no estaba en el reporte sino en la pantalla de resumen: «Y 3 señal(es) más
en el detalle». Ahora dice «Y 3 señales más» o «Y 1 señal más». Es el último resto de la forma
abreviada en un texto que lee una persona, y viene de la misma observación de una cursante que
motivó la 0.8.49. Una prueba de interfaz nueva lo fija, incluida la prohibición de la forma vieja.

## Motor multilente-0.8.57 · 27 de septiembre de 2026

Lo que ayer quedó arreglado sólo para los PDF ahora vale para los CSV: **un archivo que escribe los
miles con punto y los decimales con coma ya no entra con los importes divididos por mil**. Era el
pendiente de mayor consecuencia, porque afecta a cada control sin que nada avise.

La decisión se toma por columna y con el patrón repetido: si una columna numérica usa de forma
consistente el punto seguido de exactamente tres dígitos, el archivo se relee con ese criterio. Un
CSV exportado en inglés no cambia en nada, porque ahí el punto es decimal y no aparece seguido de
exactamente tres dígitos; y una columna de códigos como «8.123.456» tampoco altera los importes de
las demás. «9.765» pasa a 9765 y «6,1» a 6,1.

Medido, porque tocar el lector alcanza a todo: el catálogo de errores de valor queda en **169 de 174
con una falsa alarma** y el estructural en **141 de 150 con cuatro**, idénticos a los de antes de las
últimas siete versiones. 1063 pruebas.

Además, los tres «señal(es)» que quedaban en textos que lee una persona pasan a estar escritos.

## Motor multilente-0.8.56 · 27 de septiembre de 2026

Buscando nombrar las columnas sin rótulo apareció algo más grave: **los importes de los cuadros de
PDF se leían mil veces más chicos**. «1.738» es ambiguo —en inglés es uno con setecientos treinta y
ocho milésimos y acá es mil setecientos treinta y ocho— y el lector tomaba el punto como decimal.
Un total de 16.911 millones entraba al análisis como 16,911.

Ahora la decisión se toma por columna y sólo cuando el patrón se repite: en un cuadro donde la coma
es el decimal, un punto seguido de exactamente tres dígitos es separador de miles, y se quita. Si la
columna no muestra ese patrón, el valor queda como está. «9.765» pasa a 9765 y «1.234,56» a 1234,56;
«1.5» y «0,6» no se tocan.

Con los números bien leídos aparece además lo que se buscaba: una columna sin rótulo cuyos valores
son el porcentaje de otra queda nombrada por lo que hace. Si B es el porcentaje de A sobre un total,
100·A/B da ese total y es el mismo en todas las filas: eso se verifica sin conocer el total y sin
adivinar nada. En el libro de gasto 2001-2020, tres columnas pasan a llamarse «2017 · %», «2018 · %» y
«2019 · %», y ese cuadro deja de contar como ilegible: las filas revisables pasan de 182 a 194 y los
cuadros sin rótulo confiable de 3 a 2.

Los dos controles aritméticos siguen sin encontrar nada en los PDF oficiales, ahora con las
magnitudes correctas, que es la prueba que faltaba: 540 comparaciones que cierran. Siete pruebas
nuevas.

## Motor multilente-0.8.55 · 27 de septiembre de 2026

Segunda igualdad sobre los cuadros de un PDF: **las partes de cada bloque tienen que sumar su total**,
Nación + Provincias = Total, rubro por rubro y año por año. Es independiente de la suma por fila y se
apoya en algo que el cuadro declara.

Para eso hubo que resolver los bloques. El año de cada bloque aparece una sola vez porque en el PDF
está en una celda combinada **centrada**: cae en la fila del medio, no en la primera. Arrastrarlo
hacia abajo, que fue lo primero que probé, deja el año corrido una fila y rompe todo: de 171
comparaciones cerraban 7. Los bloques se cierran ahora en su fila de total y el año se toma de
donde esté dentro del bloque. Con eso, los tres cuadros del libro de gasto 2001-2020 quedan en veinte bloques
cada uno, 2001 a 2020, y las comparaciones cierran.

También se agrega la tolerancia que faltaba: un cuadro redondeado a la unidad produce diferencias de
un punto que no son un error. Sin ella aparecían dos observaciones por 324 contra 323.

Resultado sobre los dos PDF oficiales: **ninguna observación en 540 comparaciones**, que es el
resultado correcto —esas igualdades cierran— y la prueba de que el control no inventa. La detección
se verifica con cuadros sintéticos: un desvío de 120 en un año se señala con su página, su año y su
columna. Tres pruebas nuevas.

## Motor multilente-0.8.54 · 27 de septiembre de 2026

Un cuadro leído de un PDF empieza a revisarse como se revisa una planilla. El primer control es el
que más se usa: **los rubros de cada fila tienen que sumar el total que la propia fila declara**.

Con los mismos criterios que en Excel, que son los que evitan inventar relaciones. La igualdad no se
afirma sin corroborarla: tiene que cerrar en al menos el 80 % de las filas del cuadro para que las
que no cierran signifiquen algo, y hacen falta cuatro filas comparables. Las diferencias por debajo
del 0,2 % son redondeo y no se informan. Una columna llamada «total» que no es la suma de los rubros
—un porcentaje, un subtotal de otra cosa— no habilita ninguna conclusión.

Sobre los dos PDF oficiales del corpus, ninguna observación: esos totales cierran, y eso es el
resultado correcto. La detección se prueba con cuadros sintéticos, incluido el caso de la diferencia
de redondeo que no debe informarse y el de la columna que no es una suma. Cinco pruebas nuevas.

Queda para la próxima la otra igualdad que estos cuadros traen servida: Nación + Provincias = Total,
que exige reconocer los bloques de tres filas por año y arrastrar el año de la celda combinada.

## Motor multilente-0.8.53 · 27 de septiembre de 2026

El encabezado de un cuadro de PDF se compone por columna. Un rótulo que abarca varias columnas
—«Primera infancia» sobre «M $» y «%»— se reparte entre todas, y el nivel de abajo distingue cada
una: «Primera infancia · M $». Un rótulo cortado en dos líneas —«Condiciones» arriba, «de vida»
abajo— se une en un solo nombre, porque una palabra que empieza en minúscula es la continuación de
la anterior y no otro nivel. Y el título del cuadro deja de tomarse como encabezado: no nombra
ninguna columna.

Sobre el libro de gasto 2001-2020, la secuencia completa del día:

| | Al empezar | Columnas por coordenadas | Con encabezados |
|---|---|---|---|
| Filas extraídas | 73 | 277 | 283 |
| Filas revisables | 9 | 0 | **182** |
| Cuadros con celdas pegadas | 5 de 7 | 0 | 0 |
| Cuadros sin rótulo confiable | — | 7 de 7 | **3 de 7** |
| Estado declarado | insuficiente | insuficiente | **parcial** |

Cuatro de los siete cuadros quedan con sus columnas nombradas: «Año», «Nivel de gobierno», «Ayuda
directa», «Condiciones de vida», «Nutrición y alimentación». Los tres que faltan tienen columnas de
porcentaje sin rótulo en ninguno de los dos niveles, y el estado lo dice en lugar de suponerlo.
Tres pruebas nuevas sobre los tres casos: dos niveles, rótulo cortado y título.

## Motor multilente-0.8.52 · 27 de septiembre de 2026

Las columnas de un PDF se reconstruyen por la posición de cada palabra en la página y no por los
espacios del texto. Una columna es una franja vertical que ninguna palabra cruza, y eso no depende de
cómo quedó el espaciado: con esto desaparecen las celdas que traían tres valores juntos. Los cortes se
calculan sólo con las filas de datos, porque un título que ocupa el ancho de la página taparía todos
los huecos. Entre estrategias de lectura ya no gana la que trae más filas, sino **la que trae más
filas con las columnas separadas**.

Sobre el libro de gasto 2001-2020: de 73 filas con 5 de 7 cuadros pegados a **277 filas con los 7 cuadros
separados**.

Y queda a la vista el problema siguiente, que esta versión declara en lugar de tapar: al separar por
coordenadas, un encabezado de varias palabras se reparte entre columnas vecinas y deja rótulos como
«de vida» o «Sociales»; en otros casos el encabezado detectado era una fila de datos y los nombres
quedan numéricos. Las columnas están separadas, pero no se puede decir de qué es cada número. La
cobertura de lectura cuenta esos cuadros aparte y el documento queda «insuficiente» con **0 filas
revisables**, que es la verdad: sin rótulo, un valor no es revisable.

Es peor número que el de ayer y es mejor información. Diez pruebas nuevas.

## Motor multilente-0.8.51 · 27 de septiembre de 2026

Fui a hacer que los cuadros leídos de un PDF pasaran por los controles tabulares y encontré que la
premisa era falsa. De los siete cuadros que se extraen del libro de gasto 2001-2020, **cinco vienen con
varias columnas metidas en una sola celda**: «Ayuda directa: 994 120 1.115» son tres valores —Nación,
Provincias y Total— que el encabezado de dos niveles dejó juntos. En uno de esos cuadros la columna
de años se perdió entera. De las 73 filas que la 0.8.24 celebró, **9 son filas de tabla de verdad**.

Construir un control aritmético sobre eso habría sido construir sobre arena. Lo que corresponde
primero es decirlo: ahora la cobertura de lectura de PDF cuenta aparte las filas cuyas celdas traen
dos o más números juntos, informa cuántos cuadros no pudieron separarse en columnas y usa las filas
revisables —no el total— para decidir si el documento quedó revisado. Sobre el mismo archivo, el
estado pasa de «completa» a «insuficiente», que es la verdad:

> PDF: se leyeron 58 de 58 páginas y se extrajeron 73 filas de datos. 5 de los 7 cuadros no pudieron
> separarse en columnas —sus celdas traen varios números juntos, como pasa con los encabezados de dos
> niveles—, así que quedan 9 filas revisables. La ausencia de observaciones no indica que el
> documento esté bien: casi no se lo pudo revisar.

El arreglo de fondo es reconstruir las columnas por la posición de las palabras en la página, no por
los espacios del texto. Queda planteado, con una medida para saber si funciona. Ocho pruebas nuevas.

## Motor multilente-0.8.50 · 26 de septiembre de 2026

«Contrato de datos acordado (JSON opcional): yo sé qué es un JSON, pero para alguien sin formación
técnica es directamente jerga.» La respuesta anterior a esa sugerencia fue explicar el formato mejor.
Esta es sacar el formato del camino: dos casillas —qué columnas no pueden faltar, y si la moneda tiene
que estar informada y ser la misma— escriben el contrato por detrás.

Lo declarado no cambia: se envía el mismo JSON que antes había que tipear, con las mismas
consecuencias. Y sigue a la vista en el cuadro de texto, porque la persona tiene que poder ver qué
declaró: es una condición que puede dejar al informe sin conclusión. Quien ya sabe escribirlo lo
sigue escribiendo, y si edita a mano, las casillas dejan de tocar el texto y se lo avisa en lugar de
pisar lo que escribió.

Tres pruebas de interfaz, incorporadas a la barrera de calidad.

## Motor multilente-0.8.49 · 26 de septiembre de 2026

Restos de plantilla en el texto que lee una persona, encontrados leyendo el reporte de un informe
real de punta a punta. Ninguno cambia lo que el sistema detecta; los tres hacían dudar de todo lo
demás.

- «- Contexto técnico: 0 registros de señales; .» pasa a «- Contexto técnico: sin señales.», y
  «1 registros» a «1 señal». El motivo vacío ya no deja un punto y coma suelto.
- «1 señal(es) para revisar» pasa a «1 señal para revisar», con un solo lugar que decide el plural.
- El índice del anexo decía «- caso-167fe8003c59b260: None!None · media; 1 señales.» Ahora dice
  «- Conexiones exploratorias · media · 1 señal. Referencia técnica: caso-167fe8003c59b260.» La
  huella se conserva —sirve para comparar dos corridas del mismo archivo— pero deja de encabezar una
  línea que nadie puede leer, y no se inventa una ubicación cuando el archivo no tiene hojas.

Dos pruebas nuevas y dos actualizadas: cambió el texto del producto, así que cambia lo que esperan.

## Motor multilente-0.8.48 · 26 de septiembre de 2026

Lo que la consulta declara ahora tiene efecto. Era el fondo del problema detrás de las señales sin
sentido del informe de importaciones: la persona había escrito «los códigos NCM y de país son
identificadores, no cantidades: no los sumes», el sistema leyó esa frase y corrió sus pruebas
numéricas igual.

El reconocimiento es determinístico y conservador. Sólo se toman nombres de columna **que existen en
los datos**, y sólo cuando el texto los declara: una oración con una señal explícita de exclusión
—«son códigos», «no son cantidades», «no los sumes»— o un paréntesis que presenta la columna como
código, que es la forma en que la gente las describe: «país de origen (Porg, código numérico de
instituto de estadística)». Nombrar una columna no alcanza; declarar una columna inexistente no hace nada.

El efecto se aplica en el único lugar donde alcanza a todo: el rol de la columna. Una columna
declarada pasa a valer como identificador, y con eso queda fuera de cada control que pide columnas
numéricas, sin tocar una sola lente. La declaración pesa incluso cuando los valores parecen una
cantidad, que es justamente el caso donde el filtro por valores no puede ayudar.

Y se declara en el reporte, arriba, junto al resultado de la consulta: «Por indicación de la
consulta, «NCM», «Porg» se trataron como identificadores y quedaron fuera de los controles
numéricos». Una restricción que no se puede auditar sería un filtro invisible. Seis pruebas nuevas.

## Motor multilente-0.8.47 · 26 de septiembre de 2026

Sigue la lista de la misma cursante: «jerga: rizoma, cronista · corte_temporal, señal individual».
Tenía razón: el resumen ejecutivo mostraba el identificador interno de la lente cuando el hallazgo
no venía de una hoja de Excel, que es justo lo que pasa con un CSV. Ahora usa el nombre con el que
cada lente se anuncia en pantalla —«conexiones exploratorias», «evolución temporal», «cálculos y
métodos»—, los códigos de regla se escriben sin guiones bajos, y «señal individual» pasa a decir
«señal única: no se encontraron otras señales relacionadas», que es lo que significa.

Sobre su informe, los cinco títulos dejan de decir «rizoma» y «matematico». Una prueba nueva.

## Motor multilente-0.8.46 · 26 de septiembre de 2026

El informe de importaciones de una cursante traía cinco señales y dos eran la prueba de Benford
aplicada a la posición arancelaria (NCM) y al país de origen (Porg). Son códigos: el primer dígito
describe el nomenclador, no el registro de una cantidad. Peor todavía, ella lo había declarado en
la consulta: «los códigos NCM y de país son identificadores, no cantidades». El sistema lo leyó y
corrió la prueba igual.

El filtro que había era por nombre de columna —usuario, legajo, identificador— y ningún nombre
alcanza para todos los nomencladores. Ahora la decisión se toma por los valores: **enteros
encerrados en una misma escala son un código**, no una cantidad. Se exige que los valores positivos
abarquen al menos tres órdenes de magnitud y que ninguno concentre más del 85 %, y sólo se descarta
la columna cuando además no tiene decimales: una serie angosta con decimales todavía puede ser un
importe y se sigue evaluando.

Sobre el archivo real: los importes van de centésimos a cientos de millones —once órdenes de
magnitud, ninguno con más del 31 %— y la posición arancelaria tiene el 98,9 % de sus valores en un
solo orden. Las dos señales sin sentido desaparecen y las demás quedan intactas. Dos pruebas nuevas.

## Motor multilente-0.8.45 · 26 de septiembre de 2026

Segunda sugerencia de una cursante, sobre su propio informe de importaciones: «la conclusión más
importante para mí —que la pregunta declarada no pudo evaluarse con la estructura disponible—
aparece recién en la sección 2. Debería ser lo primero que se lee».

Tenía razón y el orden estaba mal por una razón concreta: el bloque de encabezado miraba solamente
los controles solicitados, mientras el estado general del barrido —que era justamente
«pregunta no evaluada»— se informaba más abajo, entre las secciones técnicas. Ahora, cuando la
consulta no pudo evaluarse, esa es la primera línea del reporte, y dice también qué son las señales
que siguen: un barrido general que no responde la pregunta declarada. Dos pruebas nuevas.

## Motor multilente-0.8.44 · 26 de septiembre de 2026

Una cursante señaló una contradicción en la pantalla de detalle: el sistema decía «sólo pudo leerse
el 0 % del archivo» y debajo mostraba tres revisiones sugeridas. La causa: la cobertura de lectura
se calcula sobre cuadros por período y ese archivo era una tabla larga, sin series que contar. La
medición devolvía vacío y el vacío se mostraba como cero.

La primera mitad ya estaba corregida en la 0.8.26: el porcentaje no se informa cuando no hay series
que contar, y el rótulo pasó a ser «series temporales reconocidas», que es lo que efectivamente se
mide. Faltaba la segunda mitad: **no poder calcular ese porcentaje no autoriza a callar cuánto del
archivo entró**. Ahora, cuando no hay series por período, la pantalla muestra las filas de datos
incorporadas y en cuántas hojas, y el reporte agrega el detalle por hoja con su motivo. El lector
recibe una medida en lugar de un silencio.

## Motor multilente-0.8.26 a 0.8.43 · 26 de septiembre de 2026

Dieciocho versiones de trabajo sobre cómo se lee y cómo se comunica, con el detalle de cada una en
`docs/`. Lo que sigue es el resumen por tema.

**Claridad de lo que se dice (0.8.26 y siguientes).** Se corrigieron rótulos y mensajes que decían
otra cosa de la que hacían: el porcentaje de series por período pasa a llamarse cobertura temporal,
la pantalla «Aprendizaje» pasa a «Calibración del sistema», y los avisos de error dejan de
desaparecer solos —quedan hasta que la persona los cierra, en la aplicación, en el lector OCR y en
la demo pública—. Varias de estas correcciones salieron de las sugerencias de los cursantes.

**Progreso real (0.8.34).** La pantalla esperaba doce segundos aunque el informe ya estuviera listo,
y mostraba un mensaje de consolidación que no correspondía a ningún trabajo. Se eliminaron los dos.
El sondeo real de trabajos sigue cada 4,5 segundos. En la misma calibración apareció una carrera: una
respuesta tardía podía reemplazar el informe que la persona acababa de abrir; ahora solo actualiza el
detalle si sigue siendo el informe pedido.

**Orden temporal (0.8.35).** Un cuadro con los años en orden descendente ocultaba picos y escalas
extremas: la validación de encabezados los aceptaba, pero las ventanas de anomalías exigían paso +1.
Reproducido en doce casos de tres semillas, en ambas orientaciones.

**Subtotales intermedios (0.8.28).** Un subtotal ubicado antes de sus componentes no se reconocía
como relación; se agrega, limitada al siguiente total y a un solo nivel, sin relajar la exigencia de
corroboración.

**Variación intermensual (0.8.36).** Exige meses consecutivos reconocidos, excluye meses ambiguos y
bases cero, registra qué comparaciones quedaron afuera y declara cobertura parcial. Antes del cambio
fallaban nueve de trece casos de regresión.

**Campañas de ensayo.** Seis campañas nuevas, cada una con pares correcto/alterado y verdad conocida
con celda e importe exactos: formatos (54 casos), períodos (48), subtotales (42), límites (60),
ausencias (42) y encabezados (30). Todas incluyen prohibiciones explícitas de falsa alarma.

**Lector OCR local (0.8.31 a 0.8.33).** Piloto autenticado para leer imágenes y PDF escaneados con
Tesseract, sin IA paga y sin guardar la sesión en base. Cinco páginas por documento, límites de
tiempo y de resolución declarados, palabras con confianza baja señaladas. **La persona corrige,
previsualiza, confirma y descarga un CSV**: los números leídos por OCR no se analizan solos, y
cualquier edición revoca la confirmación.

**Sugerencias.** Cada persona puede ver y corregir las propias, que era justamente una de las cosas
que pidieron.

Sobre el banco de errores plantados, medido contra el motor en producción: catálogo de valor 169 de
174 con una falsa alarma y catálogo estructural 141 de 150 con cuatro, **idénticos a los de la
0.8.25**. Dieciocho versiones sin mover la detección. 1013 pruebas.

## Motor multilente-0.8.25 · 25 de septiembre de 2026

Los números de los hallazgos estaban escritos al revés de como se escriben acá: «0.05%» y
«1,234.56», con el punto donde va la coma. En un informe que se lee en la administración pública
argentina eso no es un detalle: es un número que dice otra cosa. Ahora los controles tabulares
escriben «0,05 %» y «1.234,56», con un formateador compartido.

Además, la fila de referencia se nombra una sola vez por frase. Antes el hallazgo decía «vale
0,90 % de «En millones de $» en esta hoja y 68,22 % de «En millones de $» en las otras 23»;
ahora la segunda mención se omite, que es como lo escribiría una persona.

## Motor multilente-0.8.24 · 25 de septiembre de 2026

Lo que se lee de un PDF tiene que ser un cuadro. Al revisar qué había quedado adentro de las 124
filas que la versión 0.8.16 empezó a leer del libro de gasto 2001-2020, cuarenta y una de cada cien eran
los rótulos de un gráfico de barras: columnas llamadas «27,5» y «25,5», celdas con dos números
pegados y ninguna fila que dijera de qué hablaba. Un hallazgo construido sobre eso es ilegible.

Ahora se exige que el cuadro diga de qué habla: o el encabezado nombra las columnas, o la primera
celda de cada renglón trae el concepto. Sobre el mismo documento se pasa de 124 filas a 73, y las
73 son filas de cuadro con su rubro —«Condiciones de vida», «Nutrición y alimentación»— y sus
columnas «Mill. $» y «%». Leer menos y que lo leído sirva.

Además, cuando el cuadro no trae una columna llamada «Indicador» o «Concepto», el rótulo del
renglón se toma de su primera celda con texto, en lugar de mostrar sólo «fila 28».

## Motor multilente-0.8.23 · 24 de septiembre de 2026

La comparación entre hojas se extiende a lo que antes quedaba afuera.

**Valores por persona y porcentajes.** Un importe en millones depende del tamaño de la
jurisdicción y sólo se puede comparar como proporción; un valor por habitante o un porcentaje, en
cambio, es del mismo orden en todas las hojas y se compara en su propio valor, sin necesidad de
una fila de referencia. Con eso quedan a la vista los «en $ por niño/a» cargados en otra unidad,
que son filas sueltas y no forman un cuadro con otras.

**La propia fila de referencia.** Si casi todos los rubros de una hoja se apartan de las demás, lo
que está fuera de lugar no es cada rubro sino la fila con la que se los compara. En ese caso se
señala esa fila, una vez, en lugar de emitir una observación por rubro.

Catálogo estructural: 137 a 140 de 150; unidades mezcladas 19 a 22 de 25. El catálogo de errores
de valor y las falsas alarmas no cambian. Sobre las planillas oficiales sin alterar aparecen dos
observaciones nuevas, las dos verificadas: en el libro por provincia, «Cuidado y educación» de
una jurisdicción vale 49,71 contra un total provincial de 5.368,74 —en las demás provincias ese rubro es
cerca del 60 % del total—, y «Ayuda directa» queda en 0,05. Es el mismo patrón ya documentado en
una jurisdicción: el total cierra, el reparto entre categorías no.

## Motor multilente-0.8.22 · 24 de septiembre de 2026

Esta versión reúne dos líneas de trabajo: la lectura de estructuras irregulares y dos controles
nuevos que apoyan la revisión en referencias externas al cuadro.

**Lectura estructural.** La separación de cuadros pasa a un módulo propio (`excel_estructura`):
distingue las celdas sueltas con un año —separadas del cuadro por columnas vacías y sin datos
debajo— de las columnas que sí pertenecen a la tabla, y reconoce paneles anuales laterales. Un
archivo real de 27 hojas y 689 series deja así de producir alarmas por celdas que no son parte del
cuadro. El costo está medido: cuatro años duplicados plantados justamente en esas celdas dejan de
señalarse (177 a 173 de 183 en el catálogo de errores de valor). Una campaña nueva
(`scripts/ensayo_estructuras.py`) desplaza cuadros, cambia rótulos, intercala filas vacías, apila o
coloca cuadros al costado y reordena hojas, y exige que la misma diferencia aritmética se siga
señalando en la misma coordenada.

**Exploración semántica (0.8.21).** El contexto del Excel que se envía a los modelos pasa por un
plan con cobertura declarada: si el barrido global no entra, se exigen todos los lotes locales y
una segunda pasada de relaciones entre hojas. Los modelos devuelven referencias, no datos: las
citas y las ubicaciones se reconstruyen localmente. Se agrega diagnóstico por intento, sin claves.

**Casos de revisión (0.8.18).** Las señales se agrupan por causa común propuesta, sin eliminar
ninguna, y una corrida puede compararse con la anterior para ver qué cambió entre versiones.

**El mismo rubro en las demás hojas.** Los informes provinciales repiten la misma estructura hoja
por hoja: veinticuatro versiones del mismo cuadro. Un rubro cargado en otra unidad, o dos rubros
intercambiados, dejan la hoja internamente coherente —los totales siguen cerrando— pero rompen la
proporción que ese rubro tiene en todas las demás jurisdicciones. Solo se afirma algo cuando esa
proporción es pareja en el resto y el desvío supera veinte veces el extremo de las demás hojas, no
su promedio: hay rubros casi nulos en dos o tres provincias. Cuando dos rubros tienen cada uno la
proporción del otro, se nombran juntos.

**Filas que cambiaron de lugar entre ediciones.** Si una serie completa coincide con la que la
edición anterior publicaba en otra fila del mismo cuadro, y ya no con la suya, se señala; si el
cambio es mutuo, se informa como intercambio. No es una afirmación estadística, así que bastan tres
años comunes, que es lo que tienen las ediciones cortas. La coincidencia tiene que ser única y la
fila debe existir en la edición anterior: sin esas dos condiciones aparecían 164 observaciones
nuevas sobre las planillas oficiales, casi todas un total que coincide con el indicador de la hoja.

**Alcance de lectura.** El valor por omisión pasa a «Todas las aperturas». El modo automático
dejaba fuera las aperturas menores cuando el cuadro tenía más de 40 series.

Medición sobre el banco de errores plantados (19 planillas oficiales, en copias aisladas del
código): catálogo estructural 125 a 137 de 150; rubros intercambiados 16/26 a 25/26; unidades
mezcladas 16/25 a 19/25. Falsas alarmas sin cambio. Sobre las planillas oficiales sin alterar, ocho
observaciones nuevas y cinco que dejan de emitirse; las ocho fueron verificadas a mano. Entre ellas,
dos que el propio organismo corrigió en su edición siguiente: «Educación» de una jurisdicción, que valía
0,4 % del gasto provincial desde 2010 y vuelve al 70 % en la edición 2023, y «GEA» de una jurisdicción,
que pasa de 13,7 a 2.790,8 en la edición 2019-2022.

## Motor multilente-0.8.17 · 23 de septiembre de 2026

Valor repetido exacto. Cuando una columna de un cuadro queda corrida un período, todos los valores
se mueven un año y el archivo sigue siendo internamente coherente: los totales formulados se
recalculan solos y ningún control aritmético lo ve. Lo único que queda a la vista es la costura: el
año donde el valor se repite exacto respecto del anterior. La regla nueva señala esa repetición
cuando el resto de la serie es todo distinto, el valor tiene al menos cuatro dígitos significativos
—por debajo de eso dos años pueden coincidir por redondeo— y la serie se mueve más de un 2 % por
período. Sobre el catálogo de errores estructurales, las columnas corridas pasan de 4 de 19 a 19 de
19, y el catálogo completo de 110 a 125 de 150. El catálogo de errores de valor no cambia (172/183
en entrenamiento, 177/183 en una tanda nunca vista) y las falsas alarmas se mantienen en 1.

En las planillas oficiales sin alterar aparecen seis observaciones nuevas, todas verificables a
mano: en la edición 2001-2021, cinco rubros de una jurisdicción repiten en 2021 el valor exacto de 2020
mientras los otros diecinueve cambian; en una jurisdicción el «En % del gasto público social» coincide en 2017 y 2018 con
diez dígitos. Cinco pruebas nuevas.

## Motor multilente-0.8.16 · 22 de septiembre de 2026

Lectura de PDF. Un documento de trabajo de 58 páginas terminaba «sin observaciones» con 14 filas
analizadas: el límite por omisión eran 30 páginas y los cuadros de estos informes están en el
anexo, después de esa página. El límite pasa a 60 (máximo 80). Con el mismo archivo oficial
(libro de gasto 2001-2020) se leen ahora las 58 páginas y se extraen 124 filas en lugar de 14. Se agrega
además una segunda estrategia para cuadros maquetados sin líneas: se toman tramos contiguos de
filas alineadas, en páginas rotuladas como tabla o cuadro, con celdas de más de un carácter, para
no confundir los ejes de un gráfico con datos. Y la cobertura de lectura de PDF reconoce ese modo.
Cuatro pruebas nuevas. Tiempo de lectura del documento completo: unos 7 segundos.

## Motor multilente-0.8.15 · 22 de septiembre de 2026

Lectura de cuadros de tres períodos. Un cuadro con menos de cuatro columnas de año no se leía, así
que archivos enteros quedaban sin revisar y sin que se notara. Ahora se leen desde tres períodos y
cada control sigue exigiendo su propio mínimo. Cobertura de lectura sobre las 19 planillas
oficiales: de 15 al 100 % y cuatro entre 0 % y 6 %, se pasa a 18 al 100 % y una sola en 6 %
(libro por provincia 2016-2017, que sólo tiene dos períodos: con dos años no hay serie). Promedio 95 %. La
detección no cambia (172/183 en entrenamiento) ni las falsas alarmas. Se probó además recortar el
encabezado al tramo contiguo de años, para ignorar celdas sueltas: costaba cuatro detecciones y se
descartó; esos años sueltos se siguen informando como advertencia de cobertura.

## Motor multilente-0.8.14 · 22 de septiembre de 2026

Cobertura de lectura. Un control sólo puede fallar sobre lo que el motor logró interpretar, y
hasta ahora un archivo ilegible y un archivo correcto se veían igual: los dos terminaban «sin
observaciones». El comprobante abre ahora con cuánto se pudo leer, medido aparte de los
controles: cuántas series de las que un lector humano reconocería quedaron disponibles, y por
qué no las demás (encabezado con un período repetido, celdas sueltas entre las columnas de año,
cuadros con menos de cuatro períodos). Si la lectura queda por debajo del 50 %, el estado pasa a
«COBERTURA DE LECTURA INSUFICIENTE» y deja de poder leerse como un resultado limpio; entre 50 % y
80 % se declara lectura parcial. Medición sobre las 19 planillas oficiales: quince se leen al
100 %, y las otras cuatro al 0 %, 1 % y 6 %, siempre por la misma razón (cuadros de dos o tres
períodos y encabezados con celdas sueltas). Tres pruebas nuevas.

## Motor multilente-0.8.13 · 22 de septiembre de 2026

Errores sistemáticos: una fila entera copiada sobre otra, dos rubros intercambiados, una fila
cargada en otra unidad o una columna corrida. Como Excel recalcula los totales, el archivo queda
internamente consistente y ningún control aritmético los ve. Se agregan dos reglas: filas
idénticas dentro de un cuadro (dos rubros del mismo nivel con exactamente la misma serie, sin
relación de jerarquía y sin que el patrón se repita en más filas) y serie revisada entre
ediciones (más del 80 % de los años comunes cambian respecto de la edición anterior). Banco de
autoajuste con un catálogo nuevo de siete errores estructurales (150 casos): 67/150 → **110/150**
con la edición anterior adjunta; fila duplicada 0/16 → 12/16, unidades mezcladas 2/25 → 16/25,
rubros intercambiados 3/26 → 16/26. El catálogo original no cambia (172/183) y las falsas alarmas
se mantienen. En las planillas oficiales no aparecen filas idénticas; las series revisadas entre
ediciones son entre 0 y 10 por par de ediciones sobre unas 500 series comparables.

## Motor multilente-0.8.12 · 22 de septiembre de 2026

Identidad entre cuadros de la misma hoja. El mismo importe suele publicarse en dos aperturas
(«Obras sociales» por categorías y «OO.SS» por clases, o «Ayuda directa» e «Indirecto»). La
igualdad no se supone por el nombre: se acepta cuando los valores coinciden en al menos el 80 %
de los períodos y en cuatro como mínimo, con no más de dos desvíos y sobre series que varían.
Entonces se señala el período en que dejan de coincidir. Banco de autoajuste: entrenamiento
168 → 172 de 183 (transferencias 1/10 → 5/10, consolidado 15/15) y tanda nueva 175 → 177
(transferencias 2/6 → 4/6); falsas alarmas 1 → 1. En las planillas oficiales aparecen 15
observaciones; las revisadas son diferencias reales entre aperturas, por ejemplo una jurisdicción 2017 y
2018 y una jurisdicción 2019 (OO.SS distinto de Obras Sociales) o una jurisdicción 2019 (GBPA 35,84 frente a
Ciencia y técnica 0,08). Tres pruebas nuevas.

## Motor multilente-0.8.11 · 22 de septiembre de 2026

Piso de materialidad en la conciliación. Una diferencia menor al 0,2 % entre un total y la suma
de sus componentes es redondeo de la fuente y ya no se informa (antes bastaba con superar el
0,1 % de tolerancia). Banco de autoajuste: las falsas alarmas de la tanda s4004 bajan de 4 a 1 y
la detección no cambia (175/183; entrenamiento 168/183); en las planillas oficiales se retiran 2
observaciones de ese orden. Dos pruebas nuevas.

## Textos de alcance · 22 de septiembre de 2026

El comprobante decía «sin conciliación automática entre hojas ni informes anteriores», que ya no
es exacto. Ahora explica la conciliación entre cuadros, si se compararon ediciones y, cuando no,
sugiere cargar la edición anterior; y declara el límite de las reclasificaciones chicas que no
alteran el total. La pantalla de carga sugiere subir la edición anterior cuando el informe se
publica todos los años. Se probó además confirmar extremos finales con 8 veces de salto y 8 de
extrapolación: detectaba el ÷10 de Deportes 2020 de la planilla de prueba (que resultó estar ya en
la planilla oficial libro de gasto 2001–2020), pero sumaba 8 observaciones dudosas en las planillas
oficiales, entre ellas crecimientos reales de transferencias; se descartó.

## Motor multilente-0.8.10 · 22 de septiembre de 2026

Ajuste de la comparación entre ediciones: las celdas con fórmula cambian por arrastre cuando
cambia un componente, así que ya no cuentan para decidir que un año entero fue revisado. Con la
edición anterior adjunta: 171 → 172 de 183 en entrenamiento (transferencias 3/10 → 4/10) y 178 en
control; falsas alarmas sin cambios. Nota: desde la 0.8.9 estas observaciones tienen prioridad
media, por eso aparecen menos entre los 20 primeros que en la medición inicial.

## Motor multilente-0.8.9 · 22 de septiembre de 2026

Comparación con la edición anterior. Si en la misma carga se suben dos ediciones del mismo
informe (por ejemplo libro de gasto 2001–2022 y 2001–2023), se comparan los años que ambas publican. Se
señala un valor que cambió más de 5 % mientras el resto de su serie quedó idéntico (al menos 3
años iguales) y el resto del año no se revisó (no más de 2 rubros cambiados en ese año de la
hoja). El último año de la edición anterior se excluye por provisorio. Prioridad media: muchas
diferencias son correcciones legítimas que conviene documentar. Con la edición anterior adjunta,
el banco de autoajuste pasa de 168 → 171 y de 176 → 178 de 183 (transferencias 1/10 → 3/10 y
4/8 → 5/8); falsas alarmas 1 → 1 y 1 → 2. Sin edición anterior nada cambia. Sobre las planillas
oficiales con su edición previa aparecen 22 observaciones: valores históricos que el Ministerio
cambió entre ediciones sin revisar el resto de la serie (p. ej. una jurisdicción 2022, per cápita,
corregido en la edición 2023). Tres pruebas nuevas.

## Motor multilente-0.8.8 · 22 de septiembre de 2026

Movimientos compensados. Un importe que pasa de un rubro a otro deja la suma intacta y la
conciliación no lo ve. Nuevo control: en un mismo período, dos rubros del mismo nivel se apartan
de su tendencia (interpolación geométrica) en sentidos opuestos y por montos que se compensan
(margen 20 %), al menos uno en 30 % y ambos 3 veces por encima de su variación habitual, mientras
el total se aparta menos de un cuarto del monto movido. Banco de autoajuste: transferencias 1/10
→ 1/10 (entrenamiento) y 2/8 → 4/8 (control); total 168 → 168 y 174 → 176 de 183; falsas 1 → 1.
En las planillas oficiales aparecen 3 observaciones, reclasificaciones visibles de la fuente
(una jurisdicción 2021: clase E +5.501 y clase A −5.512; una jurisdicción 2018: Cuidado y educación +589 y Salud
−630). Una variante más permisiva detectaba 3/10 pero sumaba 15 observaciones en las planillas
oficiales; se descartó. La mayoría de las reclasificaciones chicas sigue sin ser detectable dentro
de un solo archivo: la vía más prometedora es comparar con la edición anterior del mismo informe.
Tres pruebas nuevas.

## Motor multilente-0.8.7 · 22 de septiembre de 2026

Último año de la serie. Un ×10 en el año final se confirmaba sólo si superaba 10 veces la
extrapolación local; con crecimiento previo (inflación) queda en 8-9 veces y necesitaba una
conciliación que no siempre existe. Ahora basta 7 veces la extrapolación cuando el salto contra
el año anterior es de 10 veces o más, y se admite que los dos años previos se separen hasta 4
veces (antes 3). Banco de autoajuste: último año ×10 16/20 → 19/20 y 11/12 → 12/12; total 165 →
168 y 173 → 174 de 183; falsas alarmas 1 → 1. En las planillas oficiales aparecen 3 observaciones
nuevas del mismo tipo que las ya señaladas en la fuente (p. ej. una jurisdicción 2022, Deporte:
499 frente a 41 el año anterior). Tres pruebas nuevas.

## Motor multilente-0.8.6 · 22 de septiembre de 2026

Picos aislados con inflación alta. La regla exigía que los dos años vecinos no se separaran más
de 4 veces; con la inflación de 2022–2023 eso deja fuera series donde un ×10 o un ÷10 es evidente
(una jurisdicción, Ayuda directa: 504 → 9.751 → 2.449). Ahora, si los vecinos se separan entre 4 y 10 veces,
se compara contra la interpolación geométrica y se exige un desvío de 6 veces, 3,5 veces respecto
de cada vecino, importes de al menos 1 millón y un resto de serie regular (pasos menores a 3
veces). Banco de autoajuste: ×10 15/16 → 16/16 (entrenamiento), ÷10 11/12 → 12/12, total 164 →
165 y 171 → 173 de 183; falsas alarmas 1 → 1. En las planillas oficiales sin alterar aparecen 2
observaciones nuevas, las dos anomalías visibles de la fuente (una jurisdicción 2020 Nutrición 0,003
entre 117,8 y 13,5; libro por provincia 2016–2021 Según clases, Obras sociales 2020: 2.045 entre 7.721 y 31.242).
Una primera versión sin exigir regularidad agregaba 41 observaciones en series chicas y volátiles;
se descartó. Cinco pruebas nuevas.

## Motor multilente-0.8.5 · 22 de septiembre de 2026

Series cortas con un dato faltante. El análisis de una serie exigía 4 valores numéricos; en las
ediciones de 4 años, un vacío o un «s/d» dejaba 3 y la serie no se revisaba, así que justamente
esos errores quedaban ocultos. Ahora, con 3 valores numéricos (y al menos 75 % de la serie), se
aplican los controles de estructura (vacío interior, texto en serie numérica, signo aislado); los
estadísticos siguen exigiendo 4. Banco de autoajuste: «s/d» 11/14 → 14/14 y 15/18 → 18/18; vacío
10/13 → 13/13 y 18/19 → 19/19. Total 158 → 164 y 167 → 171 de 183; falsas alarmas 1 → 1; ninguna
observación nueva en las planillas oficiales sin alterar. Seis pruebas nuevas.

## Motor multilente-0.8.4 · 22 de septiembre de 2026

Nuevo control de coherencia entre el importe ("En millones de $") y el valor por persona
("En $ por niño/a") del mismo cuadro: el cociente es la población implícita, que cambia poco
entre años. Si salta más de 50 % respecto de sus vecinos y el resto de la serie es estable
(pasos menores a 15 %), se señala el valor que más se aparta de sus propios vecinos. Cuando la
celda ya estaba señalada por otra regla, la corrobora en lugar de repetir la alarma. Banco de
autoajuste: per cápita alterado 11/13 → 12/13 (entrenamiento) y 13/15 → 15/15 (control); entre
los 20 primeros, 4 → 12 y 8 → 14. Total detectado 157 → 158 y 164 → 167 de 183; falsas alarmas
1 → 1. En las planillas oficiales sin alterar aparecen 3 observaciones nuevas y las tres son
incoherencias reales de la fuente: una jurisdicción 2019 (libro de gasto 2001–2019), una jurisdicción 2020 (libro de gasto
2001–2020) y una jurisdicción 2022 (libro por provincia 2016–2022), donde la población implícita se reduce a la mitad
o se multiplica por diez. Cuatro pruebas nuevas.

## Motor multilente-0.8.3 · 22 de septiembre de 2026

Conciliación en series cortas. Para afirmar que un total no cierra, el motor exigía que la
relación Total = suma de rubros se cumpliera en al menos 4 períodos y en el 80 % de los
comparables. En las ediciones con 4 años (libro de gasto 2019–2022, libro por provincia 2016–2019) un solo total
alterado dejaba 3 de 4 y el control no se aplicaba. Ahora, con exactamente 4 períodos, basta
que cierre en 3; las series largas no cambian. Medido con el banco de autoajuste
(/home/autoajuste: 19 planillas oficiales con errores plantados): entrenamiento 147 → 157 de 183,
control 157 → 164 de 183, falsas alarmas 1 → 1 y ningún control nuevo sobre los originales sin
alterar. Tres pruebas nuevas (detección, serie sana y dos desvíos). Decidido por Maxi (opción A).

## Aplicación 0.8.1 · 21 de septiembre de 2026

Correcciones de consistencia (detalle en `docs/revision-081/CORRECCIONES.md`):
Rizoma unifica el mínimo en cinco observaciones completas por par y declara como
no evaluables los pares constantes, obvios o insuficientes (motor pasa a
**multilente-0.7.3**); Incubadora exige devolución docente y material del
participante antes de guardar «revisado»; `MODELOS_SUSPENDIDOS` retira proveedores
de la triangulación sin borrar credenciales y el estado del sistema distingue
«configurado» de «habilitado»; Monitoreo queda habilitado solo para el proyecto
indicado en `MONITOREO_PROYECTO_ID` y el resto en solo lectura; el paquete de
distribución exige los ocho ZIP de la demo. En la aplicación, Conexiones incorpora
la vista «De la cartera a tres desarrollos conjuntos». En las páginas públicas la
ficha pasa a llamarse «ficha técnica», el correo deja de ser un enlace y los datos
de uso se actualizan al 21/09 (88 informes, 387 observaciones). La portada conserva
la idea de identidad («No propone nuevos principios…») y la frase del consenso, y
suma la invitación a señalar errores. 366 pruebas Python (20 regresiones nuevas
de la 0.8.1 y las 6 de la 0.8.0). README y evidencia pública regenerados. API
0.3.0, B-1 v1.2 y R-1 v1.1 no cambian. El documento v5 publicado describe el motor
0.7.2 y contiene la errata «||rige» (sección de restricción político-partidaria);
ambas cosas se corrigen en la próxima edición, no en el registro publicado.

## Aplicación 0.8.0 y documento v5 · 20 de septiembre de 2026

La aplicación pasa a 0.8.0: consolida las correcciones funcionales del 19 y 20/09
y unifica la identidad de Gobernanza Multilente —«lleva los principios de
gobernanza a algo que se puede comprobar»— en acceso, aplicación, presentación,
ficha, demo pública y PDF (paleta, mensaje y firma «Una segunda lectura antes de
decidir»). Los PDF de los ocho pares públicos se regeneraron con la nueva paleta.
El documento principal adopta la numeración de su serie en Zenodo y pasa a **v5**
(DOI de la serie 10.5281/zenodo.22063241); la ficha enlaza ese DOI. Seis pruebas
nuevas separan regresiones que antes vivían dentro de otras: 340 pruebas Python.
Motor multilente-0.7.2, API 0.3.0, B-1 v1.2 y R-1 v1.1 no cambian.

El documento v5 se publicó en Zenodo el 20/09/2026 con DOI 10.5281/zenodo.22863746
(archivo idéntico al generado: MD5 0d830bbca7f45cf234b045335b401245). La ficha enlaza
el DOI de la versión y el de la serie.

## Revisión documental 0.7.5 · 19 de septiembre de 2026

El documento principal pasa a v0.7.5: incorpora una subsección de diálogo con
marcos de gobernanza y gestión de riesgos de IA, explicita la contribución
metodológica, unifica el corte técnico de referencia (334 pruebas Python y seis
JavaScript) y reduce reiteraciones. Solo cambia `DOCUMENT_VERSION`, el README,
la lista de documentos no públicos de un test y la evidencia pública regenerada.
Aplicación 0.7.3, motor multilente-0.7.2, API 0.3.0, B-1 v1.2 y R-1 v1.1 no se
modifican; los registros históricos (286, 323, 326, 329 pruebas) conservan sus
cifras. Ver `docs/revision-075/INFORME-REVISION.md`.

## Páginas públicas rearmadas · 20 de septiembre de 2026

`/presentacion` queda en cuatro secciones (portada, preguntas, ejemplos y prueba
institucional): la evidencia técnica pasa a la ficha, el contacto aparece una sola
vez y cada pregunta frecuente cierra con un pase a la sección correspondiente de
`/detalle`. La ficha se reorganiza en seis bloques con índice lateral, las siete
lentes en formato de tabla y el detalle secundario plegable; conserva todos los
textos, límites y anclas. No cambian lentes, umbrales, protocolos ni versiones.

## Correcciones funcionales del control de consistencia · 19 de septiembre de 2026

Se corrigen la demo pública bajo CSP, la autorrevisión de proyectos, el recorte
silencioso de entregas, la confirmación de entregas fallidas y la escritura de
aprendizajes curados (commit `6797905`), con cinco regresiones nuevas: 334
pruebas. No cambian lentes, umbrales ni protocolos. El documento 0.7.4 alineó
antes ese mismo día propósito de módulos, niveles, lentes y principios (329).

Cierre de pendientes del mismo control (posterior al documento 0.7.5, sin
cambiar versiones ni el conteo de 334 pruebas): un proyecto sin entrega final ni
aportes propios no puede marcarse «entregado» y la interfaz pide confirmación
si el texto está vacío; la pre-devolución muestra su fecha y avisa si el
proyecto se guardó después; el acceso usa la misma fuente local que las páginas
institucionales; en `/presentacion` y `/detalle` se alinean las tarjetas de
ejemplo, se reduce el hueco bajo las preguntas frecuentes y la ficha suma un
acceso «↑ Inicio» en pantallas chicas. Lentes, umbrales y protocolos no cambian.

`/presentacion` incorpora, como una de las preguntas frecuentes, el contenido
«De los principios a la práctica» (texto final del 20/09/2026): cinco principios
reconocidos llevados a mecanismos concretos, visibles y contrastables, en lenguaje
llano y sin confrontar con los marcos generales. La portada precisa qué registro
deja cada revisión (alcance, exclusiones y contexto necesario). Solo cambia
el HTML de la presentación y aserciones de pruebas existentes (334 sin cambios).

## Retiro de la descarga pública del Word · 18 de septiembre de 2026

El documento principal v0.7.3 queda destinado a publicación externa en Zenodo.
Se retiran de `static/` los Word v0.7.0 y v0.7.3, se eliminan sus rutas públicas
del middleware y `/presentacion` y `/detalle` dejan de ofrecer una descarga
directa. No cambian lentes, controles, umbrales, protocolos, datos ni informes.

## Revisión integral documental de 0.7.3 · 18 de septiembre de 2026

El Word v0.7.3 pasa a ser el documento principal y reemplaza como referencia
vigente al Word v0.7.0. Se revisaron sus afirmaciones contra la aplicación 0.7.3,
el motor multilente-0.7.2, la suite de 323 pruebas y los cambios de 0.7.1 a 0.7.3.
Las páginas públicas `/presentacion` y `/detalle` se alinean con el mismo corte.
El enlace de descarga que acompañó inicialmente esta revisión fue retirado por
la decisión posterior de publicar el documento en Zenodo. Las versiones
anteriores se conservan como antecedentes históricos. No cambian lentes,
controles, umbrales, protocolos, base de datos ni informes ya generados.

## 0.7.3 · 18 de septiembre de 2026

B-1: se desactiva la entrada visible al protocolo desde el recorrido habitual, sin eliminar el módulo ni sus datos. Router, servicios, modelos, migraciones, tests y registros históricos de B-1 quedan intactos; deja de ofrecerse como paso sugerido en el detalle del informe (se retira el párrafo y el enlace en app.js) y como tarjeta destacada en la pantalla de inicio (se retira de "¿Qué produce la gobernanza?", que pasa a describir una sola constancia, R-1; el badge de actividad pasa de "B-1 · R-1" a "R-1"). En la presentación institucional se reescribe el párrafo de B-1 v1.2: pasa de leerse como una instancia posterior disponible dentro del recorrido a una capa institucional opcional, fuera del recorrido habitual, que la institución activa por acceso directo cuando su normativa exige una instancia de revisión humana documentada. El acceso directo ya existente (`/tecnico.html?informe={id}`) no cambia; `routers/certificaciones.py`, `tecnico.html` y `tecnico.js` quedan intactos. No se modificaron controles, umbrales, lentes, protocolos ni resultados. Suite completa: 323/323 pruebas aprobadas, sin tests nuevos ni modificados. Aplicación y documento principal 0.7.3; motor multilente-0.7.2, API 0.3.0 y protocolos institucionales sin cambios.

## Ajuste editorial de alcance · 18 de septiembre de 2026 (publicado)

Clarificación editorial que separa qué acredita el comprobante automático de qué exige una revisión institucional B-1: no detectar inconsistencias no demuestra que un informe sea verdadero, y lo no evaluado no equivale a un control superado. Afecta la pantalla de resultados, la presentación pública, el reporte y el comprobante descargable; no reescribe registros históricos ni modifica el preprint DOCX publicado. Ver `docs/alcance-de-la-revision.md`.

La preparación había quedado completa el 18/09 a las 16:14 (huellas, respaldo y suite verde sobre los 7 archivos), pero el despliegue quedó detenido por un bloqueo de E/S del servidor durante el fsync del primer archivo temporal, antes de reemplazar cualquier destino: producción conservó la versión anterior sin cambios. Verificado que el bloqueo era puntual (proceso ajeno al servidor, sin recurrencia), se reintentó y se publicó efectivamente el 18/09/2026 a las 18:00:15 (hora local), reemplazando los 7 archivos de forma atómica, con reinicio de servicio y health check en verde. Suite completa reejecutada tras la publicación: 323/323 pruebas aprobadas, sin fallos ni omisiones. No hubo migraciones ni modificación de la base de datos.

## 0.7.2 · 18 de septiembre de 2026

Correcciones derivadas de la revisión de los ocho pares de ejemplos:
evidencia numérica completa, períodos observados separados del período de carga,
coordenadas Excel verificadas, contexto de retrocesos sin alerta duplicada ni doble
reducción de severidad, y recálculo acotado del patrón de fórmulas ya detectado.
Las lecturas relacionadas se identifican sin borrar controles ni evidencias.
El PDF no trunca explicaciones, evita líneas huérfanas y muestra criterios y
limitaciones de los cálculos temporales. Rizoma conserva su separación exploratoria.
El catálogo v2 conserva las planillas anteriores y utiliza pares comparables;
el caso 5 usa grupos sintéticos, no registros de estudiantes.
Aplicación y motor se identifican como 0.7.2; documento metodológico 0.7.0,
API 0.3.0 y protocolos institucionales sin cambios. Ver `docs/revision_ocho_casos.md`.

## 0.7.1 · 18 de septiembre de 2026

Se agrega el botón «Ejecutar ambos y descargar ZIP» a cada uno de los ocho
pares de ejemplos. Reutiliza la carga, cola, controles y generación de PDF
habituales; no agrega ni omite controles y no emite sellos. El ZIP contiene
dos originales intactos y sus dos reportes recién generados. Se comprueban
permisos, finalización y proveniencia antes de descargar. Este recorrido no
envía correos ni usa la demora visual de la demostración. Las cargas manuales
conservan su comportamiento de notificaciones. Ver `docs/ejemplos_zip.md`.

## Revisión documental de 0.7.0 · 18 de septiembre de 2026

Se contrastó la entrega con el código de referencia `ad9e4f0`, sin agregar
funcionalidades, lentes ni controles. Se corrigieron textos de documentación,
interfaz y reporte; B-1 vigente es v1.2 y R-1 es v1.1. Se regeneró el DOCX con
python-docx y se volvió a ejecutar la suite de esta versión: 286/286 aprobadas.
El registro completo, las diferencias y las afirmaciones no verificables están
en `docs/revision-070/`. Monitoreo registra seguimiento, no calcula impacto;
la votación es exclusivamente pedagógica. No se declara validación empírica.
Los registros fechados que siguen describen sus respectivos cortes históricos.

## 0.7.0 · 17 de septiembre de 2026

Se formalizan proveniencia de archivos y evidencias, condiciones de validez,
huella de esquema, manifiesto y registro persistente de ejecuciones. Se agrega
registro de calibraciones y consulta retrospectiva con reevaluación humana,
sin revocar constancias automáticamente. Las siete lentes se conservan.

El comprobante automático permanece independiente de B-1 opcional. B-1 1.2
conserva los once controles y versiona la exclusión exploratoria; las evaluaciones
históricas retienen su versión. R-1 permanece en su versión institucional.
Votaciones por cohorte, apertura/cierre sin redeploy y justificación de ambas
rondas, sin modificar evaluación docente, R-1 ni Monitoreo. Se conserva el
historial completo de Monitoreo y se reorganizan los tests de Benford.

No se declara validación externa ciega ni eficacia institucional demostrada.
La API mantiene 0.3.0 como contrato técnico independiente. Ver
`docs/actualizacion_070.md` para cambios, migraciones y límites.

Los scripts de reconstrucción y migraciones manuales anteriores se conservaron como material histórico, pero no forman parte de la aplicación en ejecución.
Se retiraron del despliegue para evitar confundirlos con código operativo y quedaron preservados en `/home/gobernanza-history/_scripts_historicos-20260913`.
La evolución vigente de datos y protocolos se realiza mediante los mecanismos versionados del sistema.
