# Ensayos automáticos para mejorar los controles

## Funcionamiento

El laboratorio genera libros sintéticos con valores, períodos y sumas conocidos. Antes de consultar al motor, registra la verdad terreno de cada mutación: ubicación, original, cambio y regla esperada. Varia nombres de hojas, desplazamiento de filas/columnas, magnitudes, tendencias, año inicial y orientación horizontal/vertical.

Por semilla ejecuta 32 variantes: ocho mutaciones individuales, siete errores combinados y siete casos válidos, en las dos orientaciones. Cubre blancos interiores, texto en series numéricas, signo, multiplicación/división por diez, años duplicados/fraccionarios y ruptura de un total. Los controles válidos incluyen números textuales con coma decimal, negativos habituales, ceros, bordes vacíos, fórmulas sin caché y un movimiento compartido entre series. No baja umbrales para convertir contexto en error.

Comprueba detección, regla, ubicación, presencia entre los primeros 20 controles y cobertura. Para conciliación exige la participación de la celda y la diferencia esperada; no la confunde con atribución exclusiva. El generador no depende del resultado del motor para decidir qué debería encontrar.

## Uso automático

`scripts/verificar_calidad.py` y el empaquetado ejecutan:

1. La suite existente, los corpus reales de los libros por provincia y la regresión del comprobante 194.
2. Una campaña fija que permite detectar regresiones.
3. Cuatro semillas derivadas de la huella del código: cada versión recibe escenarios diferentes, reproducibles con esa misma huella.

Un fallo devuelve código distinto de cero y bloquea el gate de publicación. La carpeta indicada como `Evidencia de mutaciones` permanece en `/tmp` después de terminar; conservarla en almacenamiento durable si se necesita historial permanente.

## Campañas ampliadas

```bash
venv/bin/python scripts/ensayo_controles.py --inicio 2000 --semillas 32 --salida /tmp/ensayo-gobernanza-2000
```

La salida debe ser nueva. Se copian fuentes a un entorno temporal y se eliminan del entorno las credenciales, SMTP y DATABASE_URL del servicio. No se llama a modelos ni se cargan informes en la base de producción.

Cada campaña conserva `resumen.json`, `resumen.md`, `casos.json`, la huella del motor y del generador. Cada fallo guarda original, variante, verdad terreno y hallazgos. Los libros pasan por el lector y saneamiento reales y por los controles tabulares. La cola, persistencia y PDF están cubiertos por las pruebas integradas de los corpus reales, no por cada libro sintético.

## Ciclo de mejora

Generar → medir → conservar contraejemplo → corregir la causa → repetir caso y corpus completo → publicar con respaldo.

La generación, evaluación y barrera de regresiones están automatizadas. La modificación de las reglas requiere revisión y las mismas comprobaciones; el laboratorio no reescribe ni publica código por sí solo. No existe aquí un servicio periódico ni una promesa de trabajo en segundo plano.

Un resultado sin fallas significa que pasó esta campaña, no que pueda detectar cualquier error. La tasa de falsas alertas se refiere sólo a estos casos válidos conocidos. Aún deben ampliarse familias como fórmulas con caché, relaciones entre múltiples hojas y cambios de unidades; los corpus existentes cubren algunos casos de esas familias sin constituir generación exhaustiva.

## Primera falla encontrada automáticamente

En 0.8.1, las series horizontales compuestas enteramente por números guardados como texto con coma decimal podían clasificarse como estructura sin datos. El nuevo motor 0.8.2 reconoce esos números al decidir si un cuadro contiene datos cuantitativos, preservando los valores originales y sin convertir fechas ni rótulos. Hay regresiones del caso válido y de una anomalía sembrada dentro de él.
