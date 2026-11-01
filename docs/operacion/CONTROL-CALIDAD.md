# Prevención de regresiones de Gobernanza

## Antes de publicar

La segunda lectura de citas de Incubadora usa `OPENAI_MODEL_VERIFICADOR_INCUBADORA`
(por defecto `gpt-5.4-mini`), separado de `OPENAI_MODEL` para el chat. Cambiarlo requiere
contrastar pertinencia, rectificaciones y controles positivos con el proveedor real;
la suite sin credenciales no mide la calidad semántica del modelo. Esta lectura
recibe sólo citas y aclaraciones humanas, y agrega costo de IA a la revisión.
El modelo operativo es reemplazable: comprobar su disponibilidad y ciclo de vida
en la documentación del proveedor antes de una migración.

Ejecutar desde el proyecto con su entorno de desarrollo instalado:

```bash
venv/bin/python scripts/verificar_calidad.py
```

El comando crea una copia temporal sin `.env`, sin base de datos real y sin credenciales de modelos o correo. Ejecuta la suite Python y las pruebas JavaScript. Un fallo devuelve un código distinto de cero: no publicar hasta investigar y resolverlo. Ejecutar sobre la versión exacta que se va a desplegar; repetir si se cambia código después de la comprobación.

El empaquetador ejecuta además la barrera de Excel **antes** de crear el ZIP. Si falta un caso o falla una prueba, no genera el paquete. Las copias del libro por provincia se incluyen expresamente para poder repetir los controles después de distribuir el programa.

Esta barrera protege el proceso de empaquetado. No intercepta una copia manual por SSH ni reemplaza la comprobación posterior al despliegue. Toda publicación manual debe ejecutar el comando completo antes de reemplazar archivos.

## Qué protege el corpus del libro por provincia

- Original y variante aportada por el usuario, identificados por SHA-256.
- Cobertura completa: 27 hojas y 690 filas del archivo de prueba, aunque cambie el orden de las hojas.
- Ausencia de las falsas alertas de fórmulas observadas en el comprobante 191.
- Detección de una referencia incorrecta introducida deliberadamente en una copia en memoria.
- Carga HTTP, persistencia con claves reordenadas como JSONB, cola real, motor y ambos PDF.
- Separación entre variaciones temporales que requieren contexto y anomalías de otros controles.
- Casos pequeños complementarios: encabezados, cuadros apilados, totales con varios componentes y valores manuales.

## Cuando aparezca un caso nuevo

1. Conservar el archivo o crear una reproducción mínima sin datos personales.
2. Especificar qué debería detectar y qué no debería afirmar el control, con hoja y celda cuando corresponda.
3. Añadir primero una prueba que reproduzca el fallo; añadir también un control positivo o negativo para evitar desactivar la detección.
4. Corregir la causa, ejecutar la suite y revisar cobertura y salida final.
5. Conservar los informes anteriores como evidencia y verificar un nuevo resultado cuando cambie el motor.

No cambiar los resultados esperados ni los archivos de referencia sólo para hacer pasar una prueba. Las expectativas se actualizan cuando cambia justificadamente el comportamiento esperado, dejando constancia del motivo.

## Alcance

Estos controles previenen la reaparición de los fallos conocidos y amplían la cobertura. No prueban la corrección de cualquier Excel posible ni garantizan detectar todas las alteraciones numéricas. Los proveedores de IA y el correo están sustituidos durante las pruebas: su disponibilidad requiere una comprobación operativa independiente.

## Regresión del reporte 214 (libro de gasto 2019–2022)

El original en las planillas de regresión (no publicadas) está protegido por SHA-256. Se comprueban carga HTTP, procesamiento, persistencia y PDF: 27 hojas, 689 series, período 2019–2022 y conservación de las nueve señales numéricas. P6 y S6, separadas del cuadro por columnas vacías y sin datos debajo, quedan registradas como celdas aisladas. No se excluyen columnas contiguas vacías ni celdas alejadas con datos; un año duplicado dentro del cuadro continúa produciendo una observación.

La cobertura cuenta filas con valores de serie, sin sumar rótulos vacíos. Sólo una proporción íntegra se presenta como completa; el porcentaje incompleto no se redondea a 100 %. La cobertura de lectura no equivale a que todos los controles sean aplicables.

## Robustez estructural del motor 0.8.20

La barrera también ejecuta `scripts/ensayo_estructuras.py`: conserva la misma aritmética mientras desplaza cuadros, cambia rótulos, introduce filas vacías, dispone cuadros laterales o apilados, agrega encabezados aislados y cambia el orden de hojas. Cada variante se prueba correcta y con un total deliberadamente alterado; se exige la coordenada y la diferencia esperada, incluso si la conciliación queda adjunta a otra observación.

Las semillas se derivan de la huella del código y el ensayo registra resultados reproducibles. Cada fallo conserva el Excel, la verdad esperada y la evidencia. Puede ejecutarse otra campaña sin datos reales ni proveedores IA:

```sh
venv/bin/python scripts/ensayo_estructuras.py --inicio 1000 --semillas 4 --salida /tmp/campana-estructuras-nueva
```

La cobertura cruza el inventario de series por hoja/coordenadas con las celdas efectivamente incorporadas. Duplicar una serie leída no compensa una serie ausente. Se incluyen tablas verticales anuales, cuadros desplazados, rótulos distintos, series sin rótulo y paneles laterales separados por columnas vacías. No se infiere que todos los controles sean aplicables por alcanzar el 100 % de lectura.

El rango de pruebas sigue siendo acotado: no demuestra ausencia universal de errores ni certifica los datos. Un formato nuevo o ambiguo requiere contraste con la fuente y, si revela una limitación, una nueva regresión.

## Artefactos de evaluación versionados

`evaluacion-motor/` y `evaluacion-una-hoja/` guardan el resultado de dos regresiones
(`tests/test_benchmark_integracion.py`, `tests/test_benchmark_una_hoja.py`). Una corrida común de
la suite los escribe en una carpeta temporal, para no dejar el repositorio modificado. Para
regenerar los versionados a propósito:

    GOBERNANZA_REGENERAR_EVALUACION=1 venv/bin/python -m pytest tests/test_benchmark_integracion.py tests/test_benchmark_una_hoja.py
