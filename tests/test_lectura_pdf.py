"""PDF: tabla partida sin encabezado repetido, bloques descartados y páginas sumadas."""
import io

import pytest

from routers.carga_rapida import _resumen_pdf
from services import carga_archivos

reportlab = pytest.importorskip("reportlab")


def _fmt(v):
    return f"{v:,.0f}".replace(",", ".")


def _tabla_partida(repetir: bool) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

    filas = [["Mes", "Recaudación", "Gasto", "Resultado"]]
    for i in range(48):
        rec, gas = 800_000 + 7_000 * i, 900_000 + 3_000 * (i % 9)
        filas.append([f"{i % 12 + 1:02d}/{2022 + i // 12}", _fmt(rec), _fmt(gas), _fmt(rec - gas)])
    filas.append(["Total", "1.000", "2.000", ""])
    buf = io.BytesIO()
    tabla = Table(filas, repeatRows=1 if repetir else 0)
    tabla.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black), ("FONTSIZE", (0, 0), (-1, -1), 8)]))
    SimpleDocTemplate(buf, pagesize=A4).build([Paragraph("Cuadro 2. Resultado mensual", getSampleStyleSheet()["Heading2"]), tabla])
    return buf.getvalue()


def test_tabla_partida_sin_encabezado_hereda_el_encabezado():
    datos, _, lectura = carga_archivos.parse_archivos_con_lectura([("partida.pdf", _tabla_partida(False))])
    assert len(datos) == 49
    assert {tuple(k for k in f if k in {"Mes", "Recaudación", "Gasto", "Resultado"}) for f in datos} == {
        ("Mes", "Recaudación", "Gasto", "Resultado")
    }
    assert datos[-1]["Mes"] == "Total"
    assert lectura[0]["encabezados_heredados"][0]["pagina"] == 2
    assert lectura[0]["bloques_descartados"] == []


def test_puntos_de_miles_del_cuadro_se_normalizan_en_todas_las_estrategias():
    datos = carga_archivos.parse_archivo("partida.pdf", _tabla_partida(True))
    assert datos[0]["Recaudación"] == "800000"


def test_bloque_descartado_se_informa_por_pagina(monkeypatch):
    """Si las filas de una página no se pueden incorporar, se dice cuántas y en qué página."""
    original = carga_archivos._filas_tabla_pdf

    def sin_pagina_2(table, pagina, *args, **kwargs):
        return [] if pagina == 2 else original(table, pagina, *args, **kwargs)

    monkeypatch.setattr(carga_archivos, "_filas_tabla_pdf", sin_pagina_2)
    datos, _, lectura = carga_archivos.parse_archivos_con_lectura([("partida.pdf", _tabla_partida(True))])
    descartados = lectura[0]["bloques_descartados"]
    assert [d["pagina"] for d in descartados] == [2]
    assert descartados[0]["filas"] == 49 - len(datos)
    assert any("página 2" in a and "no incorporada" in a for a in lectura[0]["avisos"])


def test_paginas_leidas_son_la_suma_de_los_pdf():
    filas = [
        {"archivo_origen": "a.pdf", "extraccion_pdf": "tabla", "paginas_documento": 100, "paginas_pdf_analizadas": 100,
         "pdf_truncado_por_paginas": False, "pagina_pdf": 3, "tabla_pdf": 1},
        {"archivo_origen": "b.pdf", "extraccion_pdf": "tabla", "paginas_documento": 40, "paginas_pdf_analizadas": 40,
         "pdf_truncado_por_paginas": False, "pagina_pdf": 1, "tabla_pdf": 1},
    ]
    resumen = _resumen_pdf(filas, 150)
    assert resumen["paginas_analizadas"] == 140
    assert resumen["paginas_documento"] == 140


def test_tabla_despues_del_limite_sugiere_subir_el_limite():
    filas = [
        {"archivo_origen": "largo.pdf", "extraccion_pdf": "texto_por_pagina", "paginas_documento": 160,
         "paginas_pdf_analizadas": 150, "pdf_truncado_por_paginas": True, "pagina": p}
        for p in range(1, 151)
    ]
    resumen = _resumen_pdf(filas, 150)
    assert any("subí limite_paginas_pdf" in a and "150 de 160" in a for a in resumen["avisos"])


def test_pdf_columna_con_enteros_y_miles_con_punto():
    from services.carga_archivos import _normalizar_miles_pdf

    registros = [{"Rubro": r, "2019": v} for r, v in
                 [("Rescates", "984"), ("Incendios", "1.054"), ("Otros", "312"), ("Total", "2.350")]]
    _normalizar_miles_pdf(registros)
    assert [r["2019"] for r in registros] == ["984", "1054", "312", "2350"]

