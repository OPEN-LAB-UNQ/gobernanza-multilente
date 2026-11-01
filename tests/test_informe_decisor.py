"""Informe para quien decide (0.9.6): consultas agrupadas por causa, formato es-AR y anexo en el PDF.

La agrupación es sólo de presentación: los casos y su prioridad no cambian.
"""
import datetime
import io
from types import SimpleNamespace

from services.casos_revision import agrupar, agrupar_consultas
from services.reportes.formato import normalizar_documento, numero, unidad_legible

FICHA = dict(unidad="pesos_millones_corrientes", periodos=list(range(2008, 2016)),
             celdas=[f"{c}40" for c in "IJKLMNOP"], ambito="Gasto por categorías")


def pico(celda, periodo, anterior, valor, posterior, fila="40", hoja="Tierra del Fuego", factor=30.0):
    return dict(
        lente="ajedrecista", modo="control_tabular", severidad="media",
        descripcion=f"{hoja}!{celda} · Protección · {periodo}: {anterior} → {valor} → {posterior}; se aparta.",
        evidencia=dict(archivo_origen="x.xlsx", hoja=hoja, bloque_excel=7, celda=celda, indicador="Protección",
                       periodo=periodo, regla="pico_aislado", naturaleza="control", valor_observado=valor,
                       valor_anterior=anterior, valor_posterior=posterior, factor_escala=factor,
                       ubicaciones_excel=[f"{hoja}!{celda}"], ficha_serie=dict(FICHA, concepto="Protección")),
    )


def cierre(celda, total, recon, participantes, componentes, ambito, indicador, periodo=2018):
    dif = total - recon
    return dict(
        lente="conciliador", modo="control_tabular", severidad="alta",
        descripcion=f"Según categorías!{celda} · {indicador} · {periodo}: Total declarado {total}; reconstruido {recon}; diferencia {dif:.3f}.",
        evidencia=dict(archivo_origen="x.xlsx", hoja="Según categorías", celda=celda, indicador=indicador, periodo=periodo,
                       regla="conciliacion_aritmetica", naturaleza="control", total_declarado=total,
                       total_reconstruido=recon, diferencia_absoluta=abs(dif), diferencia_con_signo=dif,
                       diferencia_porcentual=100 * abs(dif) / total, tolerancia_absoluta=0.05,
                       celdas_participantes=participantes, componentes=componentes,
                       ubicaciones_excel=[f"Según categorías!{celda}"],
                       ficha_serie=dict(concepto=indicador, ambito=ambito, unidad="pesos_millones_corrientes")),
    )


def _s49_s10():
    s49 = cierre("S49", 2601.781725483223, 2227.6971115756965,
                 ["Según categorías!S49", "Según categorías!S50", "Según categorías!S51"],
                 [{"celda": "Según categorías!S50", "indicador": "   Asignaciones familiares", "valor": 0},
                  {"celda": "Según categorías!S51", "indicador": "   Resto de ayuda directa", "valor": 2227.6971115756965}],
                 "Provincias", "Ayuda directa")
    s10 = cierre("S10", 66372.5824398635, 65998.49782595597,
                 ["Según categorías!S10", "Según categorías!S30", "Según categorías!S51"],
                 [{"celda": "Según categorías!S30", "indicador": "Resto de ayuda directa", "valor": 63770.80071438028},
                  {"celda": "Según categorías!S51", "indicador": "Resto de ayuda directa", "valor": 2227.6971115756965}],
                 "Consolidado Nación-Provincias", "   Resto de ayuda directa")
    return s49, s10


def test_a_misma_serie_en_periodos_contiguos_es_una_sola_consulta():
    hs = [pico("K40", 2010, 26.67, 0.552, 18.89), pico("L40", 2011, 0.552, 18.89, 0.586),
          pico("M40", 2012, 18.89, 0.586, 27.65), pico("O40", 2014, 27.0, 900.0, 28.0)]
    r = agrupar(hs)
    assert r["casos_revision"] == 4  # los casos no cambian: sólo su presentación
    g = agrupar_consultas(r["casos"])
    assert len(g) == 2  # K40, L40, M40 juntos; O40 (2014) no es contiguo a M40 (2012)
    juntos = next(x for x in g if len(x["casos"]) == 3)
    assert juntos["motivo"] == "misma serie en períodos contiguos"
    assert juntos["origen"]["primary_finding"]["evidencia"]["celda"] == "K40"


def test_a_no_agrupa_otra_fila_ni_cierres_de_anios_distintos():
    hs = [pico("K40", 2010, 26.67, 0.552, 18.89), pico("L41", 2011, 1.0, 40.0, 1.0)]
    assert len(agrupar_consultas(agrupar(hs)["casos"])) == 2
    a = cierre("S10", 100.0, 90.0, ["Según categorías!S10", "Según categorías!S11"], [], "Consolidado", "Total", 2018)
    b = cierre("T10", 120.0, 100.0, ["Según categorías!T10", "Según categorías!T11"], [], "Consolidado", "Total", 2019)
    assert len(agrupar_consultas(agrupar([a, b])["casos"])) == 2


def test_b_consolidado_que_no_cierra_por_la_misma_diferencia_que_un_componente():
    s49, s10 = _s49_s10()
    r = agrupar([s10, s49])
    assert r["casos_revision"] == 2
    g = agrupar_consultas(r["casos"])
    assert len(g) == 1
    consulta = g[0]
    assert consulta["origen"]["primary_finding"]["evidencia"]["celda"] == "S49"  # el componente es el origen
    assert [c["primary_finding"]["evidencia"]["celda"] for c in consulta["efectos"]] == ["S10"]  # el consolidado, el efecto


def test_b_no_agrupa_diferencias_distintas_ni_periodos_distintos():
    s49, s10 = _s49_s10()
    s10["evidencia"]["diferencia_absoluta"] = 521.11
    assert len(agrupar_consultas(agrupar([s10, s49])["casos"])) == 2
    s49, s10 = _s49_s10()
    s10["evidencia"]["periodo"] = 2019
    assert len(agrupar_consultas(agrupar([s10, s49])["casos"])) == 2


def test_formato_es_ar_unico():
    assert numero(374.0846139075293) == "374,08"
    assert numero(2601.781725483223) == "2.601,78"
    assert numero(1827) == "1.827"
    assert numero(0.552166) == "0,55"
    assert numero(0.0232704) == "0,023"
    assert "e" not in numero(1e-7).lower() and "e" not in numero(2.1e10).lower()
    valores = [374.0846139075293, 61.82496, 4.146557, 1.4763532]
    texto = normalizar_documento("diferencia 374.085; 4.14656 → 61.825 → 1.47635; 0,0161 %", valores)
    assert "374,08" in texto and "374.085" not in texto
    assert "61,82" in texto and "61.825" not in texto
    assert "4,15" in texto and "1,48" in texto and "0,0161 %" in texto  # bajo 1, cifras significativas
    assert normalizar_documento("coeficiente 0.99634") == "coeficiente 0,9963"
    assert unidad_legible("pesos_millones_corrientes") == "millones de pesos corrientes"
    assert normalizar_documento("unidad: pesos_miles_de_millones_constantes") == "unidad: miles de millones de pesos constantes"
    # «0,036» es un decimal, aunque la evidencia tenga un 36 entero.
    assert normalizar_documento("pasa de 0,036 (2001)", [36.0, 0.0358]) == "pasa de 0,036 (2001)"


def _informe(hallazgos):
    excel = {"hojas": [{"archivo": "x.xlsx", "hoja": "Según categorías", "estado": "incluida", "filas_preparadas": 9}],
             "bloques": [{"hoja": "Según categorías"}]}
    cob = {"lentes": [{"lente": "ajedrecista", "estado": "con_senales", "hallazgos": 2, "ejecutado": True}], "excel": excel,
           "manifiesto": {"version_motor": "multilente-test", "version_codigo": "abc123def4567890"}}
    return SimpleNamespace(id=7, datos=[{"Concepto": "x", "2018": 1.0}], periodo=None, creado_en=datetime.datetime(2026, 10, 4),
                           saneamiento={"archivos_origen": ["x.xlsx"], "excel": excel, "estructura_revision": {"cantidad_cierres": 1827}},
                           devolucion=SimpleNamespace(cobertura=cob), hallazgos=hallazgos)


def test_pagina_1_con_consultas_y_anexo_presente():
    from services.reportes.markdown import render_reporte_markdown

    s49, s10 = _s49_s10()
    hs = [s10, s49, pico("K40", 2010, 26.67, 0.552, 18.89), pico("L40", 2011, 0.552, 18.89, 0.586)]
    md = render_reporte_markdown(_informe(hs), hs, True, True, pieza="ejecutivo")
    pagina1 = md.split("<!-- salto-pagina -->")[0]
    assert "## Qué preguntar al área" in pagina1
    assert "1.827 cierres" in pagina1 and "no quedaron partes sin leer" in pagina1
    assert "Motor:" not in pagina1 and "Código de la corrida" not in pagina1  # la metodología va al anexo
    assert "2.601,78" in pagina1 and "2.227,70" in pagina1 and "Asignaciones familiares en 0" in pagina1
    assert "?" in pagina1 and "374,08" in pagina1
    assert pagina1.count("\n1. ") == 1 and "\n2. " in pagina1 and "\n3. " not in pagina1  # 4 casos, 2 consultas
    assert "pesos_millones_corrientes" not in md and "millones de pesos corrientes" in md
    assert "374.085" not in md
    assert "## Detalle de las consultas" in md and "**Qué pasó:**" in md and "**Evidencia:**" in md and "**Dónde:**" in md and "**Qué preguntar:**" in md
    assert "Tierra del Fuego!K40:L40" in md
    anexo = md.split("## Anexo técnico")[1]
    assert "Código de la corrida: abc123def4567890" in anexo
    assert "Detalle técnico PDF" in anexo  # dice dónde está el detalle completo
    assert "Lectura de IA:" in anexo and "se cortó" not in md
    assert "Rareza:" not in md  # sin los tres ejes repetidos en cada caso


def test_pagina_1_sin_consultas_lo_dice_y_muestra_la_cobertura():
    from services.reporte_ejecutivo import lineas

    texto = "\n".join(lineas(_informe([]), []))
    pagina1 = texto.split("<!-- salto-pagina -->")[0]
    assert "no hay consultas para el área" in pagina1
    assert "Se revisó 1 hoja" in pagina1


def test_pdf_con_flechas_visibles_y_anexo():
    import pypdf

    from services.reportes.markdown import (
        _fuente_unicode,
        _sin_glifos_faltantes,
        render_reporte_markdown,
        render_reporte_pdf,
    )

    assert "→" not in _sin_glifos_faltantes("a → b") and "≈" not in _sin_glifos_faltantes("≈3")
    s49, s10 = _s49_s10()
    hs = [s10, s49, pico("K40", 2010, 26.67, 0.552, 18.89)]
    md = render_reporte_markdown(_informe(hs), hs, True, True, pieza="ejecutivo")
    pdf = render_reporte_pdf(md + "\n\n- Serie: 1 → 2\n")
    texto = "\n".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(pdf)).pages)
    assert "Qué preguntar al área" in texto and "Anexo técnico" in texto
    if _fuente_unicode()[0]:
        assert "1 → 2" in texto
    else:
        assert "1 » 2" in texto
