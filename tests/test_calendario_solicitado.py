"""No llamar intermensual a una comparación que salta meses."""

import pytest

from services.controles_solicitados import evaluar

P = "Identificar el mayor incremento porcentual entre meses de la deuda bruta total."


def control(pares, inverso=False):
    pares = list(pares)
    if inverso:
        pares.reverse()
    return evaluar([{"Concepto": "Deuda bruta total", **dict(pares)}], P)


@pytest.mark.parametrize("inverso", (False, True))
@pytest.mark.parametrize("ausente", (False, True))
def test_no_puentear_mes_faltante(inverso, ausente):
    pairs = [("2026-01", 100), ("2026-03", 300), ("2026-04", 330)]
    if ausente:
        pairs.insert(1, ("2026-02", None))
    r = control(pairs, inverso)
    c = r["controles"][0]
    assert c["evidencia"]["mayor_incremento"]["variacion_pct"] == 10
    assert len(c["evidencia"]["variaciones"]) == 1
    assert r["estado"] == "parcialmente_evaluado"
    assert c["evidencia"]["pares_excluidos"]


@pytest.mark.parametrize(
    "pairs",
    [
        [("2026-01", 100), ("2026-03", 300)],
        [("I trimestre 2026", 100), ("II trimestre 2026", 300)],
        [("Importe A", 100), ("Importe B", 300)],
    ],
)
def test_sin_meses_comparables_no_inventa_variacion(pairs):
    assert control(pairs)["controles"][0]["estado"] == "no_evaluable"


def test_alias_mismo_mes_no_se_usan_como_periodos_distintos():
    r = control([("2026-01", 100), ("2026-02", 110), ("febrero 2026", 999), ("2026-03", 130), ("2026-04", 143)])
    c = r["controles"][0]
    assert c["evidencia"]["mayor_incremento"]["desde"] == "2026-03"
    assert c["evidencia"]["mayor_incremento"]["variacion_pct"] == 10
    assert r["estado"] == "parcialmente_evaluado"


@pytest.mark.parametrize("inverso", (False, True))
def test_cambio_de_anio_es_mensual(inverso):
    r = control([("2025-12", 100), ("2026-01", 125), ("2026-02", 130)], inverso)
    assert r["estado"] == "evaluado"
    assert r["controles"][0]["evidencia"]["mayor_incremento"]["variacion_pct"] == 25


def test_descenso_no_se_describe_como_incremento():
    c = control([("2026-01", 100), ("2026-02", 90), ("2026-03", 80)])["controles"][0]
    assert "no hubo incrementos" in c["resultado"].lower()


def test_base_cero_se_declara_excluida():
    r = control([("2026-01", 0), ("2026-02", 100), ("2026-03", 110)])
    assert r["estado"] == "parcialmente_evaluado"
    assert r["controles"][0]["evidencia"]["mayor_incremento"]["variacion_pct"] == 10


def test_no_mezcla_trimestre_con_mes_adyacente():
    r = control([("I trimestre 2026", 100), ("2026-02", 300), ("2026-03", 330)])
    c = r["controles"][0]
    assert c["evidencia"]["mayor_incremento"]["variacion_pct"] == 10
    assert r["estado"] == "parcialmente_evaluado"
    assert c["evidencia"]["pares_excluidos"][0]["motivo"] == "periodo_trimestral_no_mensual"
