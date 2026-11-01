"""Conciliación entre bloques y encabezados decrecientes legítimos."""

import pytest

from scripts.ensayo_unidades import VARIANTES, construir, evaluar
from services.controles_excel.temporal import validar
from tests.test_formatos_adicionales import serie


@pytest.mark.parametrize("seed", (13711, 15217, 17401))
@pytest.mark.parametrize("variante", VARIANTES)
@pytest.mark.parametrize("alterado", (False, True))
def test_unidades(seed, variante, alterado):
    raw, truth = construir(seed, variante, alterado)
    resultado = evaluar(raw, truth)
    assert not resultado["errores"], resultado


@pytest.mark.parametrize(
    "periodos,regla",
    [
        ([2023, 2022, 2021, 2020, 2019, 2018], None),
        ([2023, 2022, 2022, 2020, 2019, 2018], "anio_duplicado"),
        ([2024, 2023, 2021, 2020, 2019, 2018], "discontinuidad_anual"),
        ([2018, 2019, 2021, 2020, 2022, 2023], "anios_no_crecientes"),
    ],
)
def test_encabezados_orden_y_errores(periodos, regla):
    s = serie("Encabezado temporal", 1, periodos)
    s["periodos"] = periodos
    hs, ok = validar(s)
    if regla is None:
        assert ok and not hs
    else:
        assert not ok and any(h["evidencia"]["regla"] == regla for h in hs)
