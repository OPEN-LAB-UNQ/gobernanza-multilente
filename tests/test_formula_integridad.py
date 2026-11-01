"""Tests de services.formula_integridad (deteccion de formulas/integridad)."""
from __future__ import annotations

import io

from openpyxl import Workbook

from services import formula_integridad


def _hoja_con_formulas(nombre_hoja: str, encabezados: list[str], filas: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = nombre_hoja
    ws.append(encabezados)
    for fila in filas:
        ws.append(fila)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

def _hoja_fila_de_cierre(con_gap: bool, con_etiqueta_cierre: bool, cubre_bloque: bool = True) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Notas"
    ws.append(["Alumno", "N1", "N2", "N3", "N4", "N5", "N6", "Promedio"])
    for i in range(2, 10):
        ws.cell(i, 1, f"Alumno {i}")
        for c in range(2, 8):
            ws.cell(i, c, 5 + (i + c) % 5)
        ws.cell(i, 8, f"=AVERAGE(B{i}:G{i})")
    fila_cierre = 11 if con_gap else 10
    etiqueta = "Promedio general" if con_etiqueta_cierre else "Fila extra"
    ws.cell(fila_cierre, 1, etiqueta)
    rango = "H2:H5" if not cubre_bloque else "H2:H9"
    ws.cell(fila_cierre, 8, f"=AVERAGE({rango})")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

def test_formula_integridad_detecta_formula_fuera_de_patron():
    """Fila 2: B,C,F referencian la celda de la fila de arriba en su misma
    columna (*2) -- patron mayoritario. E referencia la columna de al lado
    (D1 en vez de E1), como pasa cuando una formula arrastrada no se corrio.
    Eso debe marcarse como formula_fuera_de_patron, no como hardcode."""
    encabezados = ["Programa", "Ind B", "Ind C", "Ind D", "Ind E", "Ind F"]
    fila_base = ["Base", 10, 20, 30, 40, 50]
    fila_formulas = ["Formacion", "=B1*2", "=C1*2", "=D1*2", "=D1*2", "=F1*2"]
    contenido = _hoja_con_formulas("Datos", encabezados, [fila_base, fila_formulas])
    hallazgos = formula_integridad.analizar_archivo("reporte.xlsx", contenido)
    patron = [h for h in hallazgos if h["evidencia"]["regla"] == "formula_fuera_de_patron"]
    assert patron
    assert patron[0]["evidencia"]["celda"] == "E3"
    assert patron[0]["severidad"] == "media"


def test_formula_integridad_detecta_valor_fijo_entre_formulas():
    """Fila 2: B,C,E,F usan la misma formula (*2); D tiene un numero fijo,
    sentado entre celdas con formula a izquierda y derecha -- se marca como
    valor fijo en una serie que deberia ser toda formula."""
    encabezados = ["Programa", "Ind B", "Ind C", "Ind D", "Ind E", "Ind F"]
    fila_base = ["Base", 10, 20, 30, 40, 50]
    fila_con_hardcode = ["Formacion", "=B1*2", "=C1*2", 999, "=E1*2", "=F1*2"]
    contenido = _hoja_con_formulas("Datos", encabezados, [fila_base, fila_con_hardcode])
    hallazgos = formula_integridad.analizar_archivo("reporte.xlsx", contenido)
    hardcode = [h for h in hallazgos if h["evidencia"]["regla"] == "valor_fijo_en_serie_de_formulas"]
    assert hardcode
    assert hardcode[0]["evidencia"]["celda"] == "D3"
    assert hardcode[0]["evidencia"]["valor"] == "999"


def test_formula_integridad_sin_falsos_positivos_todas_las_formulas_iguales():
    """Calibracion: si todas las celdas de la fila siguen el mismo patron
    y no hay ningun valor fijo intercalado, no debe haber hallazgos."""
    encabezados = ["Programa", "Ind B", "Ind C", "Ind D", "Ind E", "Ind F"]
    fila_base = ["Base", 10, 20, 30, 40, 50]
    fila_formulas = ["Formacion", "=B1*2", "=C1*2", "=D1*2", "=E1*2", "=F1*2"]
    contenido = _hoja_con_formulas("Datos", encabezados, [fila_base, fila_formulas])
    hallazgos = formula_integridad.analizar_archivo("reporte.xlsx", contenido)
    assert hallazgos == []


def test_formula_integridad_ignora_hojas_con_actor_detalle():
    """Calibracion/alcance: si la fila de encabezados o el titulo de hoja
    mencionan CUIT/proveedores/etc. (actor identificable), la hoja se
    descarta entera aunque tenga el mismo patron de formula rota."""
    encabezados = ["CUIT", "Ind B", "Ind C", "Ind D", "Ind E", "Ind F"]
    fila_base = ["Base", 10, 20, 30, 40, 50]
    fila_formulas = ["30-12345678-9", "=B1*2", "=C1*2", "=D1*2", "=D1*2", "=F1*2"]
    contenido = _hoja_con_formulas("Datos", encabezados, [fila_base, fila_formulas])
    assert formula_integridad.analizar_archivo("reporte.xlsx", contenido) == []


def test_formula_integridad_ignora_encabezado_proveedor_singular():
    """Regresion: ACTOR_DETALLE_RE excluia 'proveedores' (plural) pero no
    'Proveedor' (singular), un encabezado igual de plausible. Corregido a
    proveedor(?:es)? -- este test fija que el singular tambien excluye."""
    encabezados = ["Proveedor", "Ind B", "Ind C", "Ind D", "Ind E", "Ind F"]
    fila_base = ["Base", 10, 20, 30, 40, 50]
    fila_formulas = ["ACME SA", "=B1*2", "=C1*2", "=D1*2", "=D1*2", "=F1*2"]
    contenido = _hoja_con_formulas("Datos", encabezados, [fila_base, fila_formulas])
    assert formula_integridad.analizar_archivo("reporte.xlsx", contenido) == []


def test_formula_integridad_no_falso_positivo_fila_de_cierre_con_gap():
    """Caso reportado: H2:H9 promedios por fila, H11 promedio general de la
    columna, separado por una fila vacia. No debe comunicarse como formula
    fuera de patron."""
    contenido = _hoja_fila_de_cierre(con_gap=True, con_etiqueta_cierre=False)
    hallazgos = formula_integridad.analizar_archivo("notas.xlsx", contenido)
    assert not [h for h in hallazgos if h["evidencia"].get("regla") == "formula_fuera_de_patron"]


def test_formula_integridad_no_falso_positivo_fila_de_cierre_con_etiqueta():
    """Sin fila vacia de separacion, pero con etiqueta de cierre ('Promedio
    general') -- tambien debe descartarse."""
    contenido = _hoja_fila_de_cierre(con_gap=False, con_etiqueta_cierre=True)
    hallazgos = formula_integridad.analizar_archivo("notas.xlsx", contenido)
    assert not [h for h in hallazgos if h["evidencia"].get("regla") == "formula_fuera_de_patron"]


def test_formula_integridad_sigue_detectando_cierre_que_no_cubre_el_bloque():
    """Calibracion/regresion: si la formula 'de cierre' no referencia todo
    el bloque del patron (solo una parte), no debe tratarse como cierre
    legitimo -- sigue siendo una celda atipica real."""
    contenido = _hoja_fila_de_cierre(con_gap=True, con_etiqueta_cierre=False, cubre_bloque=False)
    hallazgos = formula_integridad.analizar_archivo("notas.xlsx", contenido)
    patron = [h for h in hallazgos if h["evidencia"].get("regla") == "formula_fuera_de_patron"]
    assert patron


def test_formula_integridad_sigue_detectando_celda_atipica_sin_relacion_con_bloque():
    """Regresion: una celda que rompe el patron pero cuya formula no tiene
    nada que ver con el bloque (no es un cierre disfrazado) debe seguir
    detectandose igual que antes."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Notas"
    ws.append(["Alumno", "N1", "N2", "N3", "N4", "N5", "N6", "Otra"])
    for i in range(2, 10):
        ws.cell(i, 1, f"Alumno {i}")
        for c in range(2, 8):
            ws.cell(i, c, 5 + (i + c) % 5)
        ws.cell(i, 8, f"=AVERAGE(B{i}:G{i})")
    ws.cell(10, 1, "Alumno 10")
    for c in range(2, 8):
        ws.cell(10, c, 6)
    ws.cell(10, 8, "=AVERAGE(B9:G9)")  # referencia corrida real, no es cierre
    buf = io.BytesIO()
    wb.save(buf)
    hallazgos = formula_integridad.analizar_archivo("notas.xlsx", buf.getvalue())
    patron = [h for h in hallazgos if h["evidencia"].get("regla") == "formula_fuera_de_patron"]
    assert patron
    assert patron[0]["evidencia"]["celda"] == "H10"

