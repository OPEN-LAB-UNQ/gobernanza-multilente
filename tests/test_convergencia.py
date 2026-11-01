"""Tests de convergencia multilente."""
from __future__ import annotations

from services import convergencia


def test_convergencia_multilente_agrupa_por_locus_compartido():
    """Dos lentes distintas que evidencian el mismo periodo deben agruparse
    como convergencia; una sola lente repetida sobre el mismo locus, no."""
    hallazgos = [
        {"id": 1, "lente": "cronista", "evidencia": {"periodo": "2026-05"}},
        {"id": 2, "lente": "orquesta", "evidencia": {"periodo": "2026-05"}},
        {"id": 3, "lente": "matematico", "evidencia": {"periodo": "2026-01"}},
        {"id": 4, "lente": "matematico", "evidencia": {"periodo": "2026-02"}},
    ]
    grupos = convergencia.detectar_convergencia(hallazgos)
    assert len(grupos) == 1
    assert grupos[0]["locus_tipo"] == "periodo"
    assert grupos[0]["locus_valor"] == "2026-05"
    assert set(grupos[0]["lentes"]) == {"cronista", "orquesta"}
    assert set(grupos[0]["hallazgo_ids"]) == {1, 2}


def test_convergencia_normaliza_formato_de_periodo_entre_lentes():
    """cronista guarda el periodo como 'ago 2026'; orquesta como el valor
    crudo de la columna temporal. Sin normalizar, el mismo periodo real
    nunca converge por diferencia de formato."""
    hallazgos = [
        {"id": 1, "lente": "cronista", "evidencia": {"periodo": "ago 2026"}},
        {"id": 2, "lente": "orquesta", "evidencia": {"periodo": "2026-08-01"}},
    ]
    grupos = convergencia.detectar_convergencia(hallazgos)
    assert len(grupos) == 1
    assert grupos[0]["locus_valor"] == "2026-08"
    assert grupos[0]["fuerza"] == "debil"  # cronista+orquesta es un par de co-disparo esperado


def test_convergencia_marca_fuerte_cuando_el_par_no_es_de_co_disparo_esperado():
    hallazgos = [
        {"id": 1, "lente": "cronista", "evidencia": {"periodo": "ago 2026"}},
        {"id": 2, "lente": "matematico", "evidencia": {"periodo": "2026-08"}},
    ]
    grupos = convergencia.detectar_convergencia(hallazgos)
    assert len(grupos) == 1
    assert grupos[0]["fuerza"] == "fuerte"


def test_convergencia_cuenta_hallazgos_ya_explicados_por_conciliador():
    hallazgos = [
        {"id": 1, "lente": "cronista", "evidencia": {"periodo": "2026-08"}, "limites": {"contexto_tecnico": "explicado"}},
        {"id": 2, "lente": "matematico", "evidencia": {"periodo": "2026-08"}},
    ]
    grupos = convergencia.detectar_convergencia(hallazgos)
    assert grupos[0]["con_contexto_tecnico"] == 1
    assert grupos[0]["total_hallazgos"] == 2

