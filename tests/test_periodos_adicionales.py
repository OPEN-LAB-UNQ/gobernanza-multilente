"""Regresión de conciliaciones frente a cambios de columnas y períodos."""

import pytest

from scripts.ensayo_periodos import VARIANTES, construir
from scripts.ensayo_relaciones import evaluar


@pytest.mark.parametrize("seed", (4523, 6079, 8291))
@pytest.mark.parametrize("variante", VARIANTES)
@pytest.mark.parametrize("alterado", (False, True))
def test_periodos_adicionales(seed, variante, alterado):
    raw, truth = construir(seed, variante, alterado)
    resultado = evaluar(raw, truth)
    assert not resultado["errores"], resultado
