"""Conciliación: relaciones corroboradas en distintos formatos y magnitudes."""

import pytest

from scripts.ensayo_relaciones import VARIANTES, construir, evaluar
from services.controles_excel.conciliacion import analizar, relaciones_cuadro
from tests.test_formatos_adicionales import serie


@pytest.mark.parametrize("seed", (871, 1917, 3301))
@pytest.mark.parametrize("variante", VARIANTES)
@pytest.mark.parametrize("alterado", (False, True))
def test_relaciones(seed, variante, alterado):
    raw, truth = construir(seed, variante, alterado)
    resultado = evaluar(raw, truth)
    assert not resultado["errores"], resultado


def test_subtotal_intermedio_respeta_limites_y_niveles():
    filas = [
        serie("Otro", 2, [7] * 6),
        serie("Subtotal Salud", 3, [30] * 6),
        serie("Atención", 4, [10] * 6),
        serie("Detalle", 5, [10] * 6, 1),
        serie("Prevención", 6, [20] * 6),
        serie("Subtotal siguiente", 7, [90] * 6),
        serie("Otro universo", 8, [90] * 6),
    ]
    candidatos = [
        x
        for x in relaciones_cuadro(filas)
        if x[0]["etiqueta"] == "Subtotal Salud" and x[2] == "total_precede_componentes"
    ]
    assert len(candidatos) == 1
    assert [x["etiqueta"] for x in candidatos[0][1]] == ["Atención", "Prevención"]


def test_subtotal_intermedio_exige_corroboracion():
    filas = [
        serie("Otro", 2, [7] * 6),
        serie("Subtotal Salud", 3, [99] * 6),
        serie("Atención", 4, [10] * 6),
        serie("Prevención", 5, [20] * 6),
    ]
    assert analizar(filas) == []
