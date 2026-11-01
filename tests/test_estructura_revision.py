"""Contratos generales y metamorfismos: estructura, escala, cobertura y salida."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from openpyxl import Workbook

from services import casos_revision
from services.estructura_revision import enriquecer, preparar
from services.resultado_revision import alcance, separar_datos
from services.semantica_excel import validar_por_elemento
from tests.test_controles_tabulares import analizar_libro


def series_base(escala=1):
    def serie(label, row, nivel, values):
        return dict(
            archivo="a.xlsx",
            hoja="H",
            cuadro=1,
            etiqueta=label,
            nivel=nivel,
            unidad="pesos",
            ambito="Transferencias",
            periodos=list(range(2001, 2008)),
            celdas=[f"{c}{row}" for c in "BCDEFGH"],
            valores=[v * escala for v in values],
        )

    return [
        serie("Ayuda", 2, 0, [4, 5, 0.2, 6, 7, 8, 9]),
        serie("Componente cero", 3, 1, [0] * 7),
        serie("Resto", 4, 1, [4, 5, 0.2, 6, 7, 8, 9]),
        serie("Otro", 5, 0, [9996, 9995, 9999.8, 9994, 9993, 9992, 9991]),
        serie("Total", 6, 0, [10000] * 7),
    ]


@pytest.mark.parametrize("escala", [1, 1000000, 0.001])
def test_relacion_y_materialidad_invariantes_a_unidad(escala):
    ss = series_base(escala)
    resumen = preparar(ss)
    assert resumen["cantidad_cierres"] == 14
    assert ss[0]["equivalencias"]["2003"] == ss[2]["equivalencias"]["2003"]
    assert ss[0]["materialidad"]["2003"]["porcentaje_total"] == pytest.approx(0.002)
    assert ss[2]["materialidad"]["2003"]["porcentaje_total"] == pytest.approx(0.002)
    # Un valor repetido sin relación estructural no se agrupa.
    ss[2]["nivel"] = 0
    for s in ss:
        s.pop("equivalencias", None)
    preparar(ss)
    assert not ss[0].get("equivalencias")


def test_agrupa_sin_perder_evidencia_y_no_confunde_periodos():
    ss = series_base()
    preparar(ss)
    hs = [
        dict(
            lente="ajedrecista",
            modo="control_tabular",
            severidad="alta",
            descripcion="Salto",
            evidencia=dict(
                archivo_origen="a.xlsx", hoja="H", celda=cell, periodo=2003, regla="pico_aislado", factor_escala=20
            ),
        )
        for cell in ["D2", "D4"]
    ]
    enriquecer(hs, ss)
    r = casos_revision.agrupar(hs)
    assert r["casos_revision"] == 1 and r["senales_control"] == 2
    assert r["casos"][0]["prioridad"] == "media"
    hs[1]["evidencia"]["periodo"] = 2004
    assert casos_revision.agrupar(hs)["casos_revision"] == 2
    hs[0]["evidencia"]["corroboracion_independiente"] = True
    assert casos_revision.prioridad(hs[0]) == "alta"


@pytest.mark.parametrize("desplazamiento", [0, 3, 8])
def test_contexto_y_celda_sobreviven_desplazamientos(desplazamiento):
    w = Workbook()
    s = w.active
    s.title = "Serie"
    for _ in range(desplazamiento):
        s.append([])
    for row in [
        ["En millones de pesos corrientes"],
        ["Transferencias entre niveles"],
        ["Concepto", 2001, 2002, 2003, 2004, 2005, 2006, 2007],
        ["Rubro", 100, 110, 120, 1, 140, 150, 160],
        ["Otro", 900, 890, 880, 999, 860, 850, 840],
        ["Total", 1000, 1000, 1000, 1000, 1000, 1000, 1000],
    ]:
        s.append(row)
    hs = analizar_libro(w)
    h = next(h for h in hs if h["evidencia"].get("indicador") == "Rubro")
    assert h["evidencia"]["ficha_serie"]["ambito"] == "Transferencias entre niveles"
    assert h["evidencia"]["ficha_serie"]["unidad"] == "pesos_millones_corrientes"
    assert h["evidencia"]["celda"] == f"E{4 + desplazamiento}"


def test_pdf_ambiguo_se_excluye_por_cuadro_sin_descartar_tablas_buenas():
    malos = [
        {
            "archivo_origen": "a.pdf",
            "pagina_pdf": 1,
            "tabla_pdf": 1,
            "extraccion_pdf": "tabla",
            "columna_1": i,
            "columna_2": i * 2,
            "Completa": i * 3,
        }
        for i in range(6)
    ]
    buenos = [
        {
            "archivo_origen": "a.pdf",
            "pagina_pdf": 2,
            "tabla_pdf": 2,
            "extraccion_pdf": "tabla",
            "Periodo": 2000 + i,
            "Producción": i,
            "Demanda": i * 2,
        }
        for i in range(6)
    ]
    original = deepcopy(malos + buenos)
    datos, excluidos = separar_datos(original)
    assert datos == buenos and len(excluidos) == 1 and original == malos + buenos
    from services.lentes import rizoma

    assert rizoma.evaluar_relaciones(malos) == []


def test_composiciones_no_generan_correlacion_espuria_y_par_independiente_si():
    from services.lentes import rizoma

    datos = [{"Primaria": 50 - i, "Secundaria": 20 + i, "Superior": 30} for i in range(8)]
    assert rizoma.evaluar_relaciones(datos) == []
    datos = [{"Lluvia": i, "Consultas": 3 * i + 1} for i in range(8)]
    assert rizoma.evaluar_relaciones(datos)


def test_exploratorias_fuera_de_casos_de_control():
    h = dict(lente="rizoma", descripcion="Asociación", severidad="media", evidencia={})
    r = casos_revision.agrupar([h])
    assert r["casos_revision"] == 0 and r["senales_exploratorias"] == 1


def test_hipotesis_valida_sobrevive_a_vecina_invalida():
    ctx = {
        "elementos": [
            dict(id="a", texto="Salud", celda="A1", hoja="H"),
            dict(id="b", texto="Educación", celda="A2", hoja="H"),
        ]
    }
    buena = dict(
        tipo="taxonomia",
        referencias=["a", "b"],
        explicacion="Comparar 'Salud' y 'Educación'.",
        alternativa="Puede ser una apertura legítima.",
    )
    mala = {**buena, "referencias": ["inventada", "b"]}
    validas, rechazadas = validar_por_elemento([mala, buena], ctx)
    assert len(validas) == 1 and len(rechazadas) == 1 and rechazadas[0]["indice"] == 0


def test_limite_ampliado_y_recorte_explicito():
    from services.carga_archivos import DEFAULT_LIMITE_PAGINAS_PDF, MAX_PAGINAS_PDF, normalizar_limite_paginas_pdf

    assert DEFAULT_LIMITE_PAGINAS_PDF == 150 and MAX_PAGINAS_PDF == 300
    assert normalizar_limite_paginas_pdf(None) == 150
    assert normalizar_limite_paginas_pdf(500) == 300
    informe = SimpleNamespace(
        saneamiento={
            "pdf": dict(
                cantidad_archivos=1,
                paginas_documento=350,
                paginas_analizadas=300,
                filas_pdf=30,
                filas_pdf_utiles=30,
                modos_extraccion=["tabla"],
                truncado_por_paginas=True,
            )
        },
        devolucion=None,
    )
    assert alcance(informe)["pdf"]["estado"] == "parcial"


def test_reporte_unico_conserva_cobertura_insuficiente():
    from services.reporte_ejecutivo import lineas
    from services.reportes.markdown import _encabezar_consulta

    meta = {
        "pdf": dict(
            cantidad_archivos=1,
            paginas_documento=27,
            paginas_analizadas=27,
            filas_pdf=20,
            filas_pdf_utiles=0,
            cuadros_pdf=2,
            cuadros_pdf_sin_rotulos=2,
            modos_extraccion=["tabla"],
        )
    }
    i = SimpleNamespace(id=1, saneamiento=meta, datos=[], devolucion=None)
    for text in ["\n".join(lineas(i, [])), _encabezar_consulta("# Reporte\n", i, [])]:
        assert "INSUFICIENTE" in text and "0 filas revisables" in text


def test_caida_a_casi_cero_no_oculta_impacto_material():
    ss = series_base()
    ss[0]["valores"] = [4000, 4000, 0.2, 4000, 4000, 4000, 4000]
    ss[2]["valores"] = list(ss[0]["valores"])
    ss[3]["valores"] = [10000 - v for v in ss[0]["valores"]]
    preparar(ss)
    h = dict(
        lente="ajedrecista",
        evidencia=dict(
            archivo_origen="a.xlsx", hoja="H", celda="D2", periodo=2003, regla="pico_aislado", factor_escala=20000
        ),
        severidad="alta",
    )
    enriquecer([h], ss)
    assert h["evidencia"]["materialidad"]["porcentaje_total"] < 0.1
    assert h["evidencia"]["materialidad"]["porcentaje_desvio"] > 39
    assert casos_revision.prioridad(h) == "alta"
