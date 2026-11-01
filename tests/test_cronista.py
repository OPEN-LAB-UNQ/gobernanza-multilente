"""Tests de la lente Cronista."""
from __future__ import annotations

from conftest import _presupuesto_largo

from services.lentes import cronista


def test_cronista_detecta_corte_temporal():
    datos = _presupuesto_largo(salto_area="Infraestructura", salto_periodo="2026-05", salto_factor=2.6)
    hallazgos = cronista.analizar(datos)
    assert hallazgos
    assert hallazgos[0]["modo"] == "corte_temporal_conjunto"
    assert "may" in hallazgos[0]["descripcion"].lower() or "2026-05" in str(hallazgos[0]["evidencia"])


def test_cronista_formato_ancho_detecta_corte_en_una_fila():
    """Formato ancho (meses como columnas, una fila = una serie). Se usa
    solo cuando no hay formato largo ni anio/mes explicitos -- con un
    salto grande en el ultimo mes debe detectar corte_temporal (no
    _conjunto, porque hay una sola serie/fila)."""
    datos = [{
        "programa": "Formacion continua",
        "Enero": 100,
        "Febrero": 102,
        "Marzo": 101,
        "Abril": 103,
        "Mayo": 500,
    }]
    hallazgos = cronista.analizar(datos)
    assert hallazgos
    assert hallazgos[0]["modo"] == "corte_temporal"
    assert hallazgos[0]["evidencia"]["orientacion"] == "fila"
    assert "Mayo" in hallazgos[0]["descripcion"]



def test_cronista_baja_tono_en_series_mensuales_estacionales():
 datos = [
 {"periodo": f"2023-{i:02d}", "produccion_lechera": 100 + i}
 for i in range(1, 7)
 ] + [
 {"periodo": "2023-07", "produccion_lechera": 250},
 {"periodo": "2023-08", "produccion_lechera": 260},
 {"periodo": "2023-09", "produccion_lechera": 270},
 {"periodo": "2023-10", "produccion_lechera": 280},
 ]

 hallazgos = cronista.analizar(datos)

 assert hallazgos
 assert hallazgos[0]["severidad"] == "media"
 assert hallazgos[0]["evidencia"]["requiere_contexto_estacional"] is True
 assert "estacionalidad" in hallazgos[0]["descripcion"]
