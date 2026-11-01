"""Lector numérico único: el formato se decide por columna con evidencia de todo el archivo."""
import io

from openpyxl import Workbook

from services import carga_archivos
from services.perfilado import numero


def _xlsx(filas):
    wb = Workbook()
    for fila in filas:
        wb.active.append(fila)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_tres_decimales_en_ingles_no_se_leen_como_miles():
    """Antes, una columna con «0.125» hacía releer todo el archivo con punto de miles: 0.125 -> 125."""
    contenido = (
        "Indicador,2021,2022\n"
        "Tasa de mortalidad infantil,0.125,0.118\n"
        "Tasa de desempleo,0.105,0.098\n"
        "Tasa de pobreza,0.374,0.392\n"
        "Escolaridad media,9.875,9.912\n"
    ).encode()
    filas = carga_archivos.parse_archivo("indicadores.csv", contenido)
    assert [f["2021"] for f in filas] == [0.125, 0.105, 0.374, 9.875]
    assert filas[-1]["2022"] == 9.912


def test_parentesis_son_negativos_y_el_punto_es_de_miles_por_el_resto_del_archivo():
    contenido = (
        "Cuenta;2022;2023\n"
        "Ingresos corrientes;1.234.567;1.534.567\n"
        "Gastos corrientes;1.534.567;1.734.567\n"
        "Resultado económico;(300.000);(200.000)\n"
    ).encode()
    filas = carga_archivos.parse_archivo("cuentas.csv", contenido)
    assert [f["2022"] for f in filas] == [1234567, 1534567, -300000]
    assert filas[-1]["2023"] == -200000


def test_numero_resuelve_lo_inequivoco_sin_contexto():
    assert numero("1.234.567") == 1234567
    assert numero("1,234,567") == 1234567
    assert numero("(1.234.567)") == -1234567
    assert numero("1.234,5-") == -1234.5
    assert numero("-") is None and numero("s/d") is None
    # Ambiguo sin columna: se conserva el criterio anterior.
    assert numero("1.5") == 1.5


def test_interpretar_columna_decide_con_la_columna_y_desempata_con_el_archivo():
    from services.perfilado import interpretar_columna

    valores, informe = interpretar_columna(["1.738", "9.765", "16.911"], preferencia="es")
    assert valores == [1738, 9765, 16911] and informe["formato_decidido_por"] == "archivo"
    valores, informe = interpretar_columna(["1.738", "9.765", "16.911"], preferencia="en")
    assert valores == [1.738, 9.765, 16.911]
    valores, informe = interpretar_columna(["1.234,5", "2.000,1", "3.500"])
    assert valores == [1234.5, 2000.1, 3500] and informe["formato_decidido_por"] == "columna"


def test_numeros_como_texto_en_excel_se_incorporan():
    """«1.772.343.908» guardado como texto dejaba la hoja con 0 filas."""
    contenido = _xlsx([
        ["Concepto", 2019, 2020, 2021],
        ["Personal", "1.772.343.908", "2.309.004.700", "3.412.309.640"],
        ["Bienes de consumo", "3.302.779.022", "4.715.055.610", "5.955.697.453"],
        ["Total", "5.075.122.930", "7.024.060.310", "9.368.007.093"],
    ])
    datos, cobertura = carga_archivos.parse_archivos_con_cobertura([("gasto.xlsx", contenido)])
    assert len(datos) == 3
    assert datos[0]["2019"] == 1772343908
    assert cobertura["hojas"][0]["numeros_como_texto"][0]["formato"] == "es"


def test_celdas_no_interpretables_se_cuentan_y_declaran():
    contenido = (
        "Rubro;2023;2024\n"
        "Salud;1.234,5;2.345,6\n"
        "Educación;3.456,7;12abc\n"
        "Total;4.691,2;5.000,0\n"
    ).encode()
    datos, _, lectura = carga_archivos.parse_archivos_con_lectura([("gasto.csv", contenido)])
    assert datos[1]["2024"] == "12abc"  # se conserva, no se descarta en silencio
    declaradas = lectura[0]["celdas_no_interpretables"]
    assert declaradas == [{"columna": "2024", "celdas": 1, "ejemplos": ["fila 3: «12abc»"]}]
    assert any("1 celda no interpretable como número en columna «2024»" in a for a in lectura[0]["avisos"])


def test_las_celdas_citadas_en_la_cobertura_pasan_por_la_redaccion():
    contenido = (
        "Rubro;Monto\nA;1.234,5\nB;ver juan.perez@correo.com\nC;2.000,0\nD;3.000,0\n"
    ).encode()
    _, _, lectura = carga_archivos.parse_archivos_con_lectura([("gasto.csv", contenido)])
    texto = str(lectura)
    assert "juan.perez" not in texto and "[EMAIL_REDACTADO]" in texto
