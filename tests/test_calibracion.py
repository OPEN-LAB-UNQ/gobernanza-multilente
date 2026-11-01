"""Tests de calibracion cruzada entre lentes (smoke tests generales)."""
from __future__ import annotations

from conftest import _presupuesto_largo

from services.lentes import ajedrecista, cronista


def test_datos_estables_sin_falsos_positivos():
    """Calibracion: datos coherentes, sin anomalias, no deberian generar
    hallazgos ni en ajedrecista ni en cronista."""
    datos = _presupuesto_largo()
    assert ajedrecista.analizar(datos, None) == []
    assert cronista.analizar(datos) == []

