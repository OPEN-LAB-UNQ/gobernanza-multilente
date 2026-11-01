"""La orientación cronológica no debe ocultar una anomalía local."""

import random

import pytest
from openpyxl.utils import get_column_letter

from services.controles_excel.temporal import ventana_valida
from tests.test_controles_tabulares import analizar_libro, caso


@pytest.mark.parametrize("seed", (25013, 27329, 29527))
@pytest.mark.parametrize("vertical", (False, True))
@pytest.mark.parametrize("inverso", (False, True))
@pytest.mark.parametrize("extremo", (False, True))
@pytest.mark.parametrize("alterado", (False, True))
def test_misma_anomalia_en_ambos_ordenes(seed, vertical, inverso, extremo, alterado):
    base = random.Random(seed).randint(1100, 1700)
    years = list(range(2000, 2007))
    values = [base + i * 13 for i in range(7)]
    pos = 6 if extremo else 3
    periodo = years[pos]
    if alterado:
        values[pos] *= 10
    if inverso:
        years.reverse()
        values.reverse()
        pos = 6 - pos
    hs = analizar_libro(caso(values, years, vertical=vertical))
    if not alterado:
        assert not hs
        return
    regla = "escala_extremo" if extremo else "pico_aislado"
    target = f"B{pos + 2}" if vertical else f"{get_column_letter(pos + 2)}2"
    matching = [h["evidencia"] for h in hs if h["evidencia"].get("regla") == regla]
    assert any(e["celda"] == target and e["periodo"] == periodo for e in matching), hs


@pytest.mark.parametrize("years", [[2023, 2022, 2020], [2023, 2022, 2022], [2023, 2021, 2022], [2023, 2022.5, 2021]])
def test_no_unir_periodos_ambiguos_o_saltos(years):
    assert not ventana_valida({"periodos": years}, range(3))
