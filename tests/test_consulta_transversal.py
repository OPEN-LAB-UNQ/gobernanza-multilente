"""0.10.14: saltos el mismo año en varias hojas se preguntan una vez, como causa común, y van primero."""
from services.reportes.consultas import _transversales


def _consulta(hoja, periodo, prioridad="alta", regla="escala_extremo", periodos=None):
    casos = [{"primary_finding": {"evidencia": {"hoja": hoja, "periodo": p, "regla": regla, "indicador": "BP"}},
              "prioridad": prioridad} for p in (periodos or [periodo])]
    return {"casos": casos, "origen": casos[0], "prioridad": prioridad, "posicion": 0, "donde": f"{hoja}!S23",
            "resumen": f"caso de {hoja}"}


def test_tres_hojas_el_mismo_anio_forman_una_consulta_comun_que_va_primero():
    suelta = _consulta("Santa Fe", 2017)
    lista = [suelta, _consulta("Chaco", 2018), _consulta("Jujuy", 2018), _consulta("San Juan", 2018, "media")]
    out = _transversales(lista, {"contexto": [{"periodo": "2018", "cantidad": 69}]})
    assert len(out) == 2 and out[1] is suelta
    t = out[0]
    assert t["transversal"] and t["prioridad"] == "alta" and len(t["casos"]) == 3
    assert t["resumen"] == ("En 2018 hay saltos o cambios de escala en 3 hojas a la vez («Chaco», «Jujuy» y «San Juan»): "
                            "¿cambió en 2018 la metodología, la cobertura o la clasificación de los datos?")
    assert "69 variaciones anuales" in t["que_pasa"]


def test_dos_hojas_o_filas_que_oscilan_varios_anios_no_alcanzan():
    lista = [_consulta("Chaco", 2018), _consulta("Jujuy", 2018),
             _consulta("Salta", 2018, periodos=[2018, 2019])]
    assert _transversales(lista, {}) == lista


def test_reglas_que_no_son_saltos_no_se_agrupan():
    lista = [_consulta(h, 2018, regla="conciliacion_aritmetica") for h in ("A", "B", "C")]
    assert _transversales(lista, {}) == lista
