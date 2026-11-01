"""Un libro de muchas hojas se abre una vez para detectar encabezados, no una vez por hoja.

Caso: planilla_oficial (13 hojas con casi 700.000 estilos): cada apertura tardaba unos doce segundos y
el análisis quedaba horas en la lectura.
"""
import io

import pandas as pd
from openpyxl import Workbook

from services import carga_archivos


def _libro(hojas):
    wb = Workbook()
    wb.remove(wb.active)
    for k in range(hojas):
        ws = wb.create_sheet(f"Cuadro {k + 1}")
        ws.append(["Concepto", "Ventas", "Costos", "Margen"])
        for fila in range(6):
            ws.append([f"Rubro {fila}", 100 + fila, 110 + fila, 120 + fila])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _aperturas(monkeypatch, contenido):
    cuenta = {"n": 0}
    original_excel, original_read = pd.ExcelFile, pd.read_excel

    class Contado(original_excel):
        def __init__(self, *a, **kw):
            cuenta["n"] += 1
            super().__init__(*a, **kw)

    def read_excel(io_, *a, **kw):
        if not isinstance(io_, original_excel):
            cuenta["n"] += 1
        return original_read(io_, *a, **kw)

    monkeypatch.setattr(pd, "ExcelFile", Contado)
    monkeypatch.setattr(pd, "read_excel", read_excel)
    datos, _ = carga_archivos.parse_archivos_con_cobertura([("libro.xlsx", contenido)])
    assert datos
    return cuenta["n"]


def test_las_aperturas_no_crecen_con_las_hojas(monkeypatch):
    assert _aperturas(monkeypatch, _libro(2)) == _aperturas(monkeypatch, _libro(8))
