"""Fórmulas sin resultado guardado: la fila Total sigue siendo una fila de datos y se declara."""
import io

from openpyxl import Workbook

from services import carga_archivos, excel_cobertura


def _libro_sin_cache():
    # openpyxl guarda las fórmulas sin su resultado: es exactamente un libro «sin caché».
    wb = Workbook()
    ws = wb.active
    ws.title = "Gasto"
    ws.append(["Concepto", 2022, 2023, 2024])
    ws.append(["Personal", 100, 110, 120])
    ws.append(["Bienes de consumo", 50, 55, 60])
    ws.append(["Servicios", 30, 33, 36])
    ws.append(["Total", "=SUM(B2:B4)", "=SUM(C2:C4)", "=SUM(D2:D4)"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_total_con_formulas_sin_valor_no_es_titulo_ni_nota():
    datos, cobertura = carga_archivos.parse_archivos_con_cobertura([("gasto.xlsx", _libro_sin_cache())])
    assert [f["Concepto"] for f in datos] == ["Personal", "Bienes de consumo", "Servicios", "Total"]
    assert datos[-1]["2022"] is None
    hoja = cobertura["hojas"][0]
    assert 5 not in hoja["filas_estructura"]
    assert hoja["formulas_sin_valor"]["celdas"] == 3
    assert hoja["formulas_sin_valor"]["ejemplos"] == ["B5", "C5", "D5"]
    assert "guardá el archivo desde la planilla" in hoja["formulas_sin_valor"]["mensaje"]


def test_formulas_sin_valor_aparecen_en_el_resumen_de_cobertura():
    _, cobertura = carga_archivos.parse_archivos_con_cobertura([("gasto.xlsx", _libro_sin_cache())])
    texto = " ".join(excel_cobertura.resumen_lineas(cobertura))
    assert "3 celdas con fórmula sin resultado guardado" in texto
    assert "no evaluables" in texto
