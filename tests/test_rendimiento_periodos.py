"""Períodos de una serie larga (20/10/2026): mapa_periodos y ventana_valida dan lo mismo que antes y no son cuadráticos.
Un libro oficial de ~500 mil celdas (planilla_oficial) tardaba horas en ventana_valida → mapa_periodos."""

import random
import time

from services.controles_excel import temporal
from services.controles_excel.comun import numero


def _mapa_anterior(s):
    ordinales = s.get("ordinales")
    if ordinales:
        return {o: i for i, o in enumerate(ordinales) if o is not None and ordinales.count(o) == 1}
    nums = [numero(y) for y in s["periodos"]]
    return {int(n): i for i, n in enumerate(nums) if n is not None and n.is_integer() and nums.count(n) == 1}


def _ventana_anterior(s, indices):
    mapa = _mapa_anterior(s)
    inverso = {i: k for k, i in mapa.items()}
    indices = list(indices)
    if any(i < 0 or i >= len(s["periodos"]) or i not in inverso for i in indices):
        return False
    anos = [inverso[i] for i in indices]
    pasos = [b - a for a, b in zip(anos, anos[1:])]
    return all(p == 1 for p in pasos) or all(p == -1 for p in pasos)


def _series_azar(rnd):
    for _ in range(300):
        n = rnd.randint(0, 25)
        tipo = rnd.choice(["anios", "ordinales", "mezcla"])
        if tipo == "anios":
            base = rnd.randint(1990, 2020)
            per = [rnd.choice([base + i, base + i, str(base + i), float(base + i), None, "", "2019 4º trim", base + i + 0.5,
                               base + rnd.randint(-2, 2)]) for i in range(n)]
            yield {"periodos": per}
        elif tipo == "ordinales":
            ords = [rnd.choice([i, i, i, None, rnd.randint(0, n)]) for i in range(n)]
            yield {"periodos": [f"p{i}" for i in range(n)], "ordinales": ords}
        else:
            yield {"periodos": [rnd.choice([2001, "2001", 2001.0, "s/d", None, 2002]) for _ in range(n)], "ordinales": []}


def test_mismo_resultado_que_la_version_anterior():
    rnd = random.Random(2010)
    for s in _series_azar(rnd):
        assert temporal.mapa_periodos(s) == _mapa_anterior(s), s
        n = len(s["periodos"])
        for i in range(-1, n + 1):
            for ventana in ((i - 1, i, i + 1), (i - 1, i), (i, i + 1, i + 2, i + 3)):
                assert temporal.ventana_valida(s, ventana) == _ventana_anterior(s, ventana), (s, ventana)
        assert temporal.periodos_ambiguos(s) == list(dict.fromkeys(
            str(y) for i, y in enumerate(s["periodos"]) if i not in set(_mapa_anterior(s).values())))


def test_mapa_devuelto_es_una_copia():
    s = {"periodos": [2001, 2002, 2003]}
    temporal.mapa_periodos(s)[2001] = 99
    assert temporal.mapa_periodos(s) == {2001: 0, 2002: 1, 2003: 2}


def test_serie_larga_no_es_cuadratica():
    s = {"periodos": [f"m{i}" for i in range(6000)], "ordinales": list(range(6000))}
    t0 = time.perf_counter()
    assert all(temporal.ventana_valida(s, (i - 1, i, i + 1)) for i in range(1, 5999))
    assert time.perf_counter() - t0 < 5
