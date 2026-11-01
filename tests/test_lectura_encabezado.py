"""Encabezado reconocido por la estructura del cuadro, no por una lista de palabras."""
import io

from openpyxl import Workbook

from services import carga_archivos


def _libro(hojas):
    wb = Workbook()
    wb.remove(wb.active)
    for nombre, filas in hojas.items():
        ws = wb.create_sheet(nombre)
        for fila in filas:
            ws.append(fila)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_balance_de_cooperativa_con_titulo_se_lee():
    contenido = _libro({
        "Estado de resultados": [
            ["Cooperativa de Servicios Villa del Sur Ltda."],
            ["Estado de resultados - en pesos"],
            [],
            ["Concepto", "Ejercicio 2025", "Ejercicio 2024"],
            ["Ventas de servicios", 4812455300, 4530118900],
            ["Costo de los servicios prestados", -3402119850, -3388744120],
            ["Resultado bruto", 1410335450, 1141374780],
        ],
        "Situación patrimonial": [
            ["Estado de situación patrimonial al 30/06/2025 y 30/06/2024"],
            [],
            ["Rubro", "30/06/2025", "30/06/2024"],
            ["Caja y bancos", 182334100, 141220870],
            ["Inversiones", 95000000, 60500000],
            ["Créditos por servicios", 612884230, 588010440],
        ],
        "Indicadores": [
            ["Indicadores sociales por provincia"],
            ["Tasas en porcentaje"],
            [],
            ["Código", "Provincia", "Población", "Tasa de actividad (%)"],
            [2, "Ciudad Autónoma de Buenos Aires", 3121707, 46.6],
            [6, "Buenos Aires", 17569053, 49.1],
            [10, "Catamarca", 429556, 46.0],
        ],
    })
    datos, cobertura = carga_archivos.parse_archivos_con_cobertura([("coop.xlsx", contenido)])
    assert [h["estado"] for h in cobertura["hojas"]] == ["incluida", "incluida", "incluida"]
    assert datos[0] == {"Concepto": "Ventas de servicios", "Ejercicio 2025": 4812455300, "Ejercicio 2024": 4530118900}
    assert any(f.get("30/06/2025") == 182334100 for f in datos)
    assert any(f.get("Población") == 17569053 for f in datos)


def test_periodos_como_texto_cuentan_para_el_encabezado():
    """El patrón tenía la barra duplicada en un texto crudo y nunca reconocía «2023-01»."""
    contenido = _libro({"Hoja": [
        ["Cuadro A"],
        ["x", "2023-01", "2023-02", "2023-03"],
        ["uno", 10, 11, 12],
        ["dos", 20, 21, 22],
        ["tres", 30, 31, 32],
    ]})
    assert carga_archivos._detectar_filas_encabezado(contenido) == [1]


def test_hoja_con_numeros_sin_cuadro_queda_declarada_no_revisada():
    contenido = _libro({
        "Datos": [["Concepto", "Monto"], ["A", 10], ["B", 20], ["C", 30]],
        "Suelta": [["Notas"], [], [None, 120, 130], [None, 140, 150]],
    })
    _, cobertura = carga_archivos.parse_archivos_con_cobertura([("libro.xlsx", contenido)])
    suelta = cobertura["hojas"][1]
    assert suelta["no_revisada"]["celdas_numericas"] == 4
    assert suelta["no_revisada"]["motivo"]
