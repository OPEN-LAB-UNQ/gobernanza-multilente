"""Materialidad, signo y evidencia insuficiente en conciliaciones."""

import pytest

from scripts.ensayo_limites import VARIANTES, construir
from scripts.ensayo_relaciones import evaluar
from services.controles_excel.conciliacion import analizar
from tests.test_formatos_adicionales import serie


@pytest.mark.parametrize("seed", (9413, 10211, 12007))
@pytest.mark.parametrize("variante", VARIANTES)
@pytest.mark.parametrize("alterado", (False, True))
def test_limites(seed, variante, alterado):
    raw, truth = construir(seed, variante, alterado)
    resultado = evaluar(raw, truth)
    assert not resultado["errores"], resultado


@pytest.mark.parametrize("valor", (0, 0.001))
def test_ceros_o_importes_insignificantes_no_corroboran(valor):
    filas = [
        serie("Componente A", 2, [valor] * 6),
        serie("Componente B", 3, [-valor] * 6),
        serie("Total", 4, [0, 1000, 0, 0, 0, 0]),
    ]
    assert analizar(filas) == []
