# Documentación de Gobernanza

Ordenada el 11/10/2026 (solo se movieron archivos, con `git mv`; no se borró nada).
Los informes fechados conservan sus rutas internas originales: usar la tabla de abajo.

| Carpeta | Qué contiene |
|---|---|
| `operacion/` | Lo vigente para operar: instalación desde cero, control de calidad, restauración del backup, controles tabulares y ensayos automáticos. |
| `motor/` | Notas de calibración, ensayos y correcciones del motor multilente 0.8.x (una por versión). |
| `documento/` | Revisiones del documento principal (Word) y su consistencia con la app: 0.7.3, 0.7.5, 0.8.1 y v5. |
| `historico-07x/` | Etapa 0.7.x (agosto–septiembre de 2026): entrega, actualización 0.7.0, cierre técnico, ejemplos y jornadas. |
| `revision-070/` | Paquete reproducible de la revisión 0.7.0. Queda en su lugar: `REPRODUCIR.md` usa esta ruta. |
| `entrega-2026-09-18/` | Entrega del 18/09/2026 (Word 0.7.0, LEEME y MANIFIESTO). Queda en su lugar por la misma razón. |

## Ruta anterior → ruta actual

| Antes (`docs/…`) | Ahora (`docs/…`) |
|---|---|
| `CONTROL-CALIDAD.md`, `RESTAURACION-BACKUP.md`, `CONTROLES-TABULARES.md`, `ENSAYOS-AUTOMATICOS.md` | `operacion/` |
| `CALIBRACION-*`, `CORRECCION-258.md`, `CORRECCIONES-CLARIDAD-0826.md`, `ENSAYO-*`, `ERRORES-VISIBLES.md`, `ESTABILIDAD-RESULTADOS.md`, `ESTRUCTURA-REVISION.md`, `EXPLORACION-*`, `OCR-*`, `ORDEN-TEMPORAL-0835.md`, `PROGRESO-REAL-0834.md` | `motor/` |
| `revision-073/`, `revision-075/`, `revision-081/`, `revision-v5/` | `documento/` |
| `actualizacion_070.md`, `entrega_070.md`, `cierre_tecnico_gobernanza.md`, `ejemplos_zip.md`, `revision_ocho_casos.md`, `alcance-de-la-revision.md`, `paquete_presentacion_jornadas.md`, `aprendizajes_gobernanza.md` | `historico-07x/` |
| `LEEME-ENTREGA-GOBERNANZA-2026-09-18.md`, `MANIFIESTO-ENTREGA-2026-09-18.json` (estaban en la raíz del repo) | `entrega-2026-09-18/` |

Los respaldos tienen su propio índice en `backups/INDICE.md` (fuera de git).
