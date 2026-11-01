"""Casos de la séptima medición (14/10/2026)."""

import datetime as dt
import io

from openpyxl import Workbook

from services import excel_cobertura
from services.controles_excel import rubro_escala, series
from services.estructura_revision import _rotulo_periodo
from services.perfilado import numero_con_formato, tiene_llamada_nota


def test_llamada_de_nota_pegada_al_numero():
    assert numero_con_formato("171.535*", "es") == 171535
    assert numero_con_formato("1.234 (p)", "es") == 1234
    assert numero_con_formato("98,5¹", "es") == 98.5
    assert tiene_llamada_nota("171.535*") and not tiene_llamada_nota("171.535")


def test_columna_con_llamadas_de_nota_se_lee_entera_y_se_avisa():
    wb = Workbook()
    ws = wb.active
    ws.title = "Cuadro 1"
    ws.append(["Cuadro 1. Chatarra recuperada"])
    ws.append(["En toneladas"])
    ws.append(["Origen", 2022, 2023, 2024, 2025])
    ws.append(["Industrial", 171461, 165961, 164561, "171.535*"])
    ws.append(["Automotor", 22796, 22322, 22548, "24.347*"])
    ws.append(["Total", 194257, 188283, 187109, "195.882*"])
    ws.append(["(*) Dato provisorio."])
    buffer = io.BytesIO()
    wb.save(buffer)
    filas, meta = excel_cobertura.leer_libro(buffer.getvalue(), "nota.xlsx")
    assert {f["Origen"]: f["2025"] for f in filas if f.get("Origen") in ("Industrial", "Total")} == {
        "Industrial": 171535, "Total": 195882}
    avisos = " ".join(a for h in meta["hojas"] for a in h.get("avisos_lectura") or [])
    assert "llamada de nota" in avisos


def _serie(etiqueta, valores, fila):
    periodos = list(range(2017, 2017 + len(valores)))
    return {"archivo": "a.xlsx", "hoja": "Cuadro", "cuadro": 1, "etiqueta": etiqueta, "nivel": 0,
            "periodos": periodos, "valores": valores, "celdas": [f"{c}{fila}" for c in "BCDEFGHIJ"[: len(valores)]],
            "periodos_validos": periodos, "unidad": None}


def test_rubro_en_otra_escala_con_importes_de_un_decimal():
    contratos = [34345.3, 34908.4, 35737.5, 35654.2, 38643.0]
    inmuebles = [4508.2, 4703.3, 4660.5, 4682.6, 5252.3]
    otros = [17793.2, 17497.3, 17267.6, 16937.0, 18763.4]
    total = [round(a + b + c, 1) for a, b, c in zip(contratos, inmuebles, otros)]
    cuadro = [_serie("Contratos", contratos, 2), _serie("Inmuebles", [round(v * 1000, 1) for v in inmuebles], 3),
              _serie("Otros", otros, 4), _serie("Total", total, 5)]
    hallazgos = rubro_escala.analizar(cuadro)
    assert [h["evidencia"]["indicador"] for h in hallazgos] == ["Inmuebles"]


def test_rotulo_del_periodo_sin_dato():
    assert _rotulo_periodo(dt.datetime(2025, 9, 1), 24308) == "2025-09"
    assert _rotulo_periodo("2025-09-01 00:00:00", 24308) == "2025-09"
    assert _rotulo_periodo(2020, 2020) == "2020"


def test_signo_aislado_en_el_primer_periodo():
    s = _serie("Valle de Uco", [-7466, 7711, 7672, 7523, 8397, 8270, 8396, 8386, 9050], 6)
    reglas = [h["evidencia"]["regla"] for h in series.analizar(s)]
    assert "signo_aislado" in reglas
