"""Sondeo previo («radiografía», 20/10/2026): una regla que aparece en muchos lugares distintos de una hoja, o en
la misma celda de varias hojas, se abstiene; sus señales quedan como nota de alcance («sin controlar») y el
comienzo del informe lo dice."""

import models
from services import casos_revision, sondeo


def _h(regla, hoja, celda, lugares=None, archivo="a.xlsx", **extra):
    ev = {"regla": regla, "hoja": hoja, "archivo_origen": archivo, **extra}
    if celda:
        ev["celda"] = celda
    if lugares:
        ev["celdas_participantes"] = [x if "!" in x else f"{hoja}!{x}" for x in lugares]
    return {"lente": "ajedrecista", "severidad": "alta", "descripcion": f"{hoja}!{celda} · señal", "evidencia": ev}


def _senal(h):
    return casos_revision.prioridad(h) not in ("contexto", "nota")


def test_regla_en_muchos_lugares_distintos_se_abstiene_y_queda_sin_controlar():
    hs = [_h("signo_aislado", "Cuadro 1", c) for c in ("B5", "D9", "F14")]
    abst = sondeo.aplicar(hs, lambda h: True)
    assert all(casos_revision.prioridad(h) == "nota" for h in hs)
    assert all(not casos_revision.es_contexto(h) for h in hs)
    assert all(h["evidencia"]["sondeo"]["version"] == sondeo.VERSION for h in hs)
    assert all(h["descripcion"].startswith("[Sin controlar por el sondeo previo]") for h in hs)
    assert len(abst) == 1 and abst[0]["senales"] == 3 and abst[0]["hoja"] == "Cuadro 1"
    assert abst[0]["donde"] == "control «signo distinto del resto de la serie» en la hoja «Cuadro 1»"
    assert "3 lugares distintos" in abst[0]["motivo"] and "signo_aislado" not in abst[0]["motivo"]


def test_error_que_se_arrastra_por_una_fila_cuenta_como_un_lugar():
    # Un acumulado mal sumado falla en la misma fila en tres columnas: es un solo error, no una placa movida.
    hs = [_h("fila_no_cierra_total", "c1", c) for c in ("D13", "H13", "L13")]
    assert sondeo.aplicar(hs, lambda h: True) == []
    assert all("sondeo" not in h["evidencia"] for h in hs)


def test_error_que_se_arrastra_por_una_columna_cuenta_como_un_lugar():
    hs = [_h("columna_total_no_cierra", "c1", c) for c in ("E9", "E16", "E34")]
    assert sondeo.aplicar(hs, lambda h: True) == []


def test_dos_lugares_no_alcanzan_para_abstenerse():
    hs = [_h("pico_aislado", "Cuadro 2", c) for c in ("B5", "D9")]
    assert sondeo.aplicar(hs, lambda h: True) == []


def test_reglas_distintas_y_hojas_distintas_no_se_suman():
    hs = [_h("signo_aislado", "Cuadro 1", "B5"), _h("pico_aislado", "Cuadro 1", "D9"),
          _h("signo_aislado", "Cuadro 2", "F14"), _h("signo_aislado", "Cuadro 3", "G20")]
    assert sondeo.aplicar(hs, lambda h: True) == []


def test_una_sola_senal_que_abarca_un_bloque_cuenta_un_lugar():
    # filas_identicas trae las dos filas completas como participantes: es un lugar, no un bloque de lugares.
    h = _h("filas_identicas", "Hoja", "B5", lugares=[f"{c}{f}" for c in "BCDEF" for f in (5, 9)])
    assert sondeo.aplicar([h], lambda h: True) == []


def test_dos_pares_de_filas_copiadas_no_se_abstienen():
    hs = [_h("filas_identicas", "Hoja", "B5", lugares=[f"{c}{f}" for c in "BCDE" for f in (5, 6)]),
          _h("filas_identicas", "Hoja", "B12", lugares=[f"{c}{f}" for c in "BCDE" for f in (12, 13)])]
    assert sondeo.aplicar(hs, lambda h: True) == []


def test_ancla_sale_de_la_ubicacion_en_su_hoja_si_no_hay_celda():
    hs = [_h("periodo_faltante", "Serie", None, ubicaciones_excel=[f"Serie!{c}:{c.replace('B', 'H')}"]) for c in ("B4", "C8", "D12")]
    hs[0]["evidencia"]["ubicaciones_excel"] = ["Otra!Z1", "Serie!B4:H4"]
    assert [sondeo.ancla(h["evidencia"]) for h in hs] == [("B", 4), ("C", 8), ("D", 12)]
    assert sondeo.aplicar(hs, lambda h: True)[0]["senales"] == 3


def test_senales_sin_celda_no_dan_base_para_abstenerse():
    hs = [_h("cambio_tipo", "Hoja", None) for _ in range(5)]
    assert sondeo.aplicar(hs, lambda h: True) == []


def test_senal_corroborada_por_un_control_independiente_no_se_abstiene():
    hs = [_h("valor_fuera_de_escala_columna", "Cuadro 1", c) for c in ("B5", "D9", "F14")]
    hs[1]["evidencia"]["corroboracion_independiente"] = True
    sondeo.aplicar(hs, lambda h: True)
    assert "sondeo" not in hs[1]["evidencia"] and "sondeo" in hs[0]["evidencia"] and "sondeo" in hs[2]["evidencia"]


def test_misma_celda_misma_regla_en_varias_hojas_se_abstiene_una_vez_por_regla():
    hs = [_h("valor_fuera_de_escala_columna", mes, c) for mes in ("Ene", "Feb", "Mar", "Abr") for c in ("C12", "D20")]
    abst = sondeo.aplicar(hs, lambda h: True)
    assert all(casos_revision.prioridad(h) == "nota" for h in hs)
    assert len(abst) == 1 and abst[0]["senales"] == 8 and abst[0]["hojas"] == ["Abr", "Ene", "Feb", "Mar"]
    assert "C12, D20" in abst[0]["motivo"] and "4 hojas" in abst[0]["donde"]


def test_formula_reemplazada_en_la_misma_celda_de_todas_las_hojas_no_se_abstiene():
    hs = [_h("valor_fijo_distinto_de_formula", mes, "C12") for mes in ("Ene", "Feb", "Mar")]
    assert sondeo.aplicar(hs, lambda h: True) == []


def test_mismos_lugares_en_otro_archivo_no_se_mezclan():
    hs = [_h("signo_aislado", "Cuadro 1", "B5", archivo="a.xlsx"), _h("signo_aislado", "Cuadro 1", "D9", archivo="b.xlsx"),
          _h("signo_aislado", "Cuadro 1", "F14", archivo="c.xlsx")]
    assert sondeo.aplicar(hs, lambda h: True) == []


def test_contexto_notas_y_senales_sin_hoja_no_se_sondean():
    sin_hoja = {"lente": "matematico", "severidad": "baja", "descripcion": "Benford", "evidencia": {"regla": "benford"}}
    ctx = [_h("variacion_anual", "Cuadro 1", c) for c in ("B5", "D9", "F14")]
    for h in ctx:
        h["evidencia"]["naturaleza"] = "contexto"
    hs = [sin_hoja, *ctx]
    assert sondeo.aplicar(hs, _senal) == []
    assert "sondeo" not in sin_hoja["evidencia"]
    assert all("sondeo" not in h["evidencia"] for h in ctx)


def test_casos_no_mezclan_lo_sin_controlar_con_contexto_ni_con_casos():
    abst = [_h("signo_aislado", "Cuadro 1", c) for c in ("B5", "D9", "F14")]
    sondeo.aplicar(abst, lambda h: True)
    real = _h("conciliacion_aritmetica", "Cuadro 1", "B5", total_declarado=10.0, total_reconstruido=9.0, diferencia_absoluta=1.0)
    g = casos_revision.agrupar([*abst, real])
    assert g["senales_sin_controlar"] == 3 and len(g["sin_controlar"]) == 3
    assert g["contexto"] == [] and g["notas_alcance"] == 0
    assert g["casos_revision"] == 1 and g["casos"][0]["related_findings"] == []


def test_registro_declara_lo_que_quedo_sin_controlar_por_el_sondeo():
    from services.reportes.registro import construir

    hs = [_h("signo_aislado", "Cuadro 1", c) for c in ("B5", "D9", "F14")]
    abst = sondeo.aplicar(hs, lambda h: True)
    informe = models.Informe(id=1, datos=[{"x": 1, "archivo_origen": "a.xlsx"}], periodo="2026-09",
                             saneamiento={"archivos_origen": ["a.xlsx"], "sondeo": {"version": sondeo.VERSION, "abstenciones": abst}})
    reg = construir(informe, hs, {})
    assert reg["estado"] != "completo"
    p = [x for x in reg["pendientes"] if "signo distinto" in x["donde"]]
    assert p and p[0]["tipo"] == "no_controlado" and "lugares distintos" in p[0]["motivo"]
    assert "Sin controlar" in reg["primera_linea"] and "signo distinto del resto de la serie" in reg["primera_linea"]
    assert reg["cruces"]["detalle"] == []


def test_regla_sin_nombre_llano_se_muestra_sin_guiones_bajos():
    assert sondeo.nombre_control("regla_nueva_x") == "regla nueva x"
