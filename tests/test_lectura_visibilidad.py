"""Hojas, filas y columnas ocultas: se leen, se declaran y se marcan en la ubicación del dato."""
import io

from openpyxl import Workbook

from services import carga_archivos, excel_cobertura


def _libro():
    wb = Workbook()
    ws = wb.active
    ws.title = "Gasto"
    ws.append(["Concepto", 2022, 2023, 2024])
    for i, rubro in enumerate(["Personal", "Bienes", "Servicios", "Transferencias"]):
        ws.append([rubro, 100 + i, 110 + i, 120 + i])
    ws.row_dimensions[4].hidden = True
    ws.column_dimensions["C"].hidden = True
    oculta = wb.create_sheet("Datos_reales")
    oculta.sheet_state = "hidden"
    oculta.append(["Concepto", 2022, 2023, 2024])
    oculta.append(["Personal", 1, 2, 3])
    oculta.append(["Bienes", 4, 5, 6])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_visibilidad_queda_en_la_cobertura_de_hoja_y_cuadro():
    _, cobertura = carga_archivos.parse_archivos_con_cobertura([("libro.xlsx", _libro())])
    gasto, oculta = cobertura["hojas"]
    assert gasto["visibilidad"] == {"estado_hoja": "visible", "filas_ocultas": [4], "columnas_ocultas": ["C"]}
    assert oculta["visibilidad"]["estado_hoja"] == "hidden"
    bloque_gasto, bloque_oculto = cobertura["bloques"]
    assert bloque_gasto["origen_oculto"] == {"hoja_oculta": False, "filas_ocultas": [4], "columnas_ocultas": {"2023": "C"}}
    assert bloque_oculto["origen_oculto"]["hoja_oculta"] is True
    assert any("oculta" in a for a in gasto["advertencias"])


def test_la_ubicacion_de_un_hallazgo_dice_si_sale_de_contenido_oculto():
    _, cobertura = carga_archivos.parse_archivos_con_cobertura([("libro.xlsx", _libro())])
    bloque_gasto, bloque_oculto = cobertura["bloques"]
    h = excel_cobertura.ubicar({"descripcion": "x", "evidencia": {"filas": [2], "columna": "2023"}}, bloque_gasto)
    assert h["evidencia"]["visibilidad_origen"] == ["fila 4 oculta", "columna C oculta"]
    h = excel_cobertura.ubicar({"descripcion": "x", "evidencia": {"filas": [0], "columna": "2022"}}, bloque_gasto)
    assert "visibilidad_origen" not in h["evidencia"]
    h = excel_cobertura.ubicar({"descripcion": "x", "evidencia": {"filas": [0], "columna": "2022"}}, bloque_oculto)
    assert h["evidencia"]["visibilidad_origen"] == ["hoja «Datos_reales» oculta"]
