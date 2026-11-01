"""Distinguir ceros, ausencias, fórmulas y períodos ambiguos."""

import pytest

from scripts.ensayo_ausencias import VARIANTES, construir, evaluar


@pytest.mark.parametrize("seed", (19001, 21317, 23143))
@pytest.mark.parametrize("variante", VARIANTES)
@pytest.mark.parametrize("alterado", (False, True))
def test_ausencias(seed, variante, alterado):
    raw, truth = construir(seed, variante, alterado)
    resultado = evaluar(raw, truth)
    assert not resultado["errores"], resultado
