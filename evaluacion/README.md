# Mediciones contra los criterios de uso

Resumen de las mediciones de Gobernanza Multilente contra sus propios criterios de «usable», de las
validaciones con errores reales y del banco de planillas con el que se controla cada versión del motor.

Por decisión del proyecto, este repositorio publica sólo resultados anónimos: no incluye los archivos de
cada medición, ni las planillas o publicaciones usadas, ni referencias a los organismos que las publicaron.

## Los tres criterios

Fijados el 03/10/2026, antes de conocer el resultado de la primera medición:

1. **Dice qué no revisó.** Todo archivo, hoja, parte o control que no se pudo leer o ejecutar aparece al
   comienzo del informe, con su motivo. Cumplimiento total: un solo caso en silencio lo incumple.
2. **No alarma sin motivo.** Como máximo una señal de prioridad alta cada cinco archivos correctos.
3. **Encuentra una parte razonable de los errores comunes.** Al menos la mitad de los errores de
   totales, escala, signo, período y unidad, señalados en la celda correcta, en cada formato: Excel, CSV
   y PDF con texto.

Cumplirlos no significa que la herramienta detecte todos los errores: habilita a usarla como
complemento de una revisión, no como garantía.

## Mediciones con conjuntos sintéticos

| Medición | Motor | Archivos | Errores en la celda correcta<br>Excel · CSV · PDF | Alarmas altas en correctos | Dice qué no revisó |
|---|---|---|---|---|---|
| 1.ª · 03/10/2026 | multilente-0.9.0 | 76 | 94 % · 0 % · 25 % | 4 en 15 | No |
| 2.ª · 03/10/2026 | multilente-0.9.1 | 91 | 86 % · 60 % · 87 % | 1 en 17 | No |
| 3.ª · 03/10/2026 | multilente-0.9.2 | 87 | 82,5 % · 87 % · 87 % | 0 en 17 | No |
| 4.ª · 03/10/2026 | multilente-0.9.3 | 84 | 80 % · 70 % · 67 % | 18 en 18 | No |
| 5.ª · 04/10/2026 | multilente-0.9.4 | 91 | 83 % · 83 % · 75 % | 1 en 18 | No (85 de 91) |
| 6.ª · 14/10/2026 | multilente-0.9.6 | 92 | 90 % · 92 % · 67 % | 1 en 18 | No (90 de 92) |
| 7.ª · 14/10/2026 | multilente-0.9.7 | 92 | 93 % · 100 % · 100 % | 1 en 18 | No (91 de 92) |
| 8.ª · 14/10/2026 | multilente-0.9.8 | 92 | 97 % · 100 % · 92 % | 1 en 18 | No (85 de 92) |
| 9.ª · 15/10/2026 | multilente-0.9.9 | 92 | 97 % · 100 % · 83 % | 0 en 18 | No (90 de 92) |
| 10.ª · 15/10/2026 | multilente-0.9.10 | 92 | 97 % · 100 % · 92 % | 1 en 18 | No (86 de 92) |
| 11.ª · 15/10/2026 | multilente-0.9.11 | 92 | 100 % · 100 % · 92 % | 0 en 18 | No (86 de 92) |
| 12.ª · 15/10/2026 | multilente-0.9.12 | 92 | 100 % · 100 % · 92 % | 1 en 18 | No (86 de 92) |
| 13.ª · 16/10/2026 | multilente-0.9.13 | 92 | 100 % · 100 % · 75 % | 0 en 18 | No (87 de 92) |
| 14.ª · 16/10/2026 | multilente-0.9.14 | 92 | 100 % · 100 % · 92 % | 0 en 18 | No (89 de 92) |
| 15.ª · 17/10/2026 | multilente-0.9.16 | 92 | 100 % · 100 % · 92 % | 0 en 18 | No (90 de 92) |

Desde la sexta medición, el PDF pasa por la revisión de lectura (una persona simulada que confirma lo que
ve sin corregir) antes del análisis. Desde la octava, los casos de lectura se arman a propósito con
situaciones que no se usaron en ninguna medición anterior.

**Conclusión hasta hoy:** ninguna versión cumplió los tres criterios a la vez, así que todavía no
consideramos la herramienta usable. Los resultados se publican también cuando son desfavorables.

## Protocolo

Cada medición la hizo un evaluador separado del proceso de corrección:

1. **Motor congelado.** Una copia del código en un commit fijo, con su huella registrada antes y después.
2. **Conjunto nuevo.** Archivos generados con una semilla propia, con temas que no se usaron antes ni
   sirvieron para corregir el motor. La composición típica: 18 correctos, 3 correctos volátiles, 54 con un
   error común cada uno y 17 casos de lectura. El diseño se fija antes de correr el motor y ningún caso se
   modifica después.
3. **Corrida** con una base en memoria, sin IA y sin correo, reproduciendo el circuito de la pantalla.
4. **Puntaje** automático y revisión manual de los casos de lectura y de una muestra de los ordinarios.
5. **Informe** con el resultado por criterio, los fallos caso por caso, el veredicto y las limitaciones.

## Validaciones con errores reales

Errores de publicaciones oficiales que los organismos corrigieron después, con un diseño fijado antes de
correr. No se publican los archivos, las publicaciones ni los organismos.

| Validación | Archivos | Motor | Detectados | Controles con falsa alarma |
|---|---|---|---|---|
| 1.ª · 16/10/2026 | Publicaciones de dos ministerios | multilente-0.9.15 | 2 de 6 | 2 de 7 (y un caso en silencio) |
| 2.ª · 17/10/2026 | Informes en PDF de dos institutos de estadística | multilente-0.9.16 | 0 de 6 | 4 de 8 |
| 3.ª · 17/10/2026 | Planillas Excel de cuatro organismos | multilente-0.9.16 | 2 de 8 | 6 de 10 |
| 4.ª · 20/10/2026 | Planillas con errores nuevos | 0.9.21.1, 0.9.22 y 0.9.22 con sondeo | 0 de 5 | 5 de 9 |
| 5.ª · 20/10/2026 | Dos casos (resultado anecdótico) | 0.9.21.1 y 0.9.22 con sondeo | 0 de 2 | 2 de 5 y 0 de 5 |

En la segunda, cuatro de los seis casos requerían controles que la herramienta no tiene. La versión 0.9.21
se corrigió a partir de la tercera: con esas mismas planillas detecta 3 de 8 y da falsas alarmas en 1 de 10
controles, lo que no prueba la mejora frente a planillas nuevas. En la cuarta, la meta fijada antes de
correr (al menos 3 de 5 y a lo sumo 2 de 9) no se cumplió con ninguno de los tres motores.

## Banco de planillas oficiales

Con el que se controla cada versión del motor antes de publicarla: 132 planillas oficiales publicadas, sin
alterar, y 123 copias con un error insertado a propósito. Con el motor multilente-0.10.59 (28/10/2026; las
versiones posteriores no cambiaron los controles):

- señala 119 de los 123 errores insertados;
- 88 de las 132 planillas publicadas salen sin ninguna señal de prioridad alta (169 señales altas en total).
  No es una tasa de acierto: las otras 44 tienen al menos una señal alta, que puede ser un error real o una
  falsa alarma;
- marca los 8 posibles errores reales con la cuenta a la vista hallados en esas planillas: 7 con prioridad
  alta y 1 media.

## Limitaciones

- Los conjuntos de las mediciones son sintéticos: series generadas y PDF construidos con ReportLab. Se buscó
  que fueran realistas, pero no reemplazan una prueba con informes reales cerrados.
- Las hizo el mismo equipo que desarrolla la herramienta, con evaluadores separados del proceso de
  corrección: no reemplaza una evaluación externa.
- La regla automática de «celda correcta» cuenta una señal como exacta si la celda verdadera está entre sus
  lugares; algunas reglas listan un total con sus componentes, lo que la vuelve generosa.
- Las pruebas automáticas publicadas usan datos sintéticos: las regresiones con planillas oficiales reales no
  se incluyen en este repositorio.
