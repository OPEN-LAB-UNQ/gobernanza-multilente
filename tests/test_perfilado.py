"""Tests de services.perfilado."""
from __future__ import annotations

from services import perfilado


def test_perfilado_fecha_correctitud_formatos_y_trimestre():
    """Regresion tras optimizar perfilado.fecha (prefiltro por digito +
    memoizacion): deben seguir reconociendose los mismos formatos y
    quedar sin reconocer los mismos casos de antes."""
    from datetime import datetime

    assert perfilado.fecha("2026-05-01") == datetime(2026, 5, 1)
    assert perfilado.fecha("2026-05") == datetime(2026, 5, 1)
    assert perfilado.fecha("01/05/2026") == datetime(2026, 5, 1)
    assert perfilado.fecha("3er trimestre 2025") == datetime(2025, 7, 1)
    assert perfilado.fecha("IV trim 2024") == datetime(2024, 10, 1)
    assert perfilado.fecha("Poder Legislativo Nacional") is None
    assert perfilado.fecha("") is None
    assert perfilado.fecha(None) is None
    assert perfilado.fecha("no es una fecha") is None


def test_perfilado_fecha_no_se_degrada_con_texto_sin_digitos_repetido():
    """Calibracion de rendimiento: antes de la optimizacion, 50k llamadas a
    fecha() sobre texto sin digitos (el caso mas comun en columnas
    descriptivas de archivos reales) tardaban varios segundos por
    recompilar patrones de strptime en cada llamada. Ahora el prefiltro
    por digito descarta esos valores sin tocar strptime -- debe ser
    practicamente instantaneo."""
    import time

    textos = [f"Descripcion de programa numero {i % 37}" for i in range(50)]
    textos_sin_digitos = [t for t in textos if not any(c.isdigit() for c in t)]
    # si el fixture cambia y algun texto queda con digito, no invalida el test
    muestra = (["Formacion y Sancion de Leyes Nacionales"] * 50000) if not textos_sin_digitos else textos_sin_digitos * 1500
    t0 = time.time()
    for t in muestra:
        perfilado.fecha(t)
    dt = time.time() - t0
    assert dt < 1.0, f"perfilado.fecha tardo {dt:.2f}s en {len(muestra)} llamadas sin digitos (deberia ser subsegundo)"

