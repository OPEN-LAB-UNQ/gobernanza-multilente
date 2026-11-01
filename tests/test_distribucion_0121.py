"""Motor 0.10.21: en una distribución porcentual, una participación chica no está fuera de escala."""
import io

import openpyxl


def _analizar(filas):
    from services import carga_archivos, controles_excel, excel_cobertura
    from services.sanitizacion import sanear

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Distribución porcentual de mujeres por grupo de edad"])
    ws.append(["Grupo de edad", "No madres", "Madres"])
    for f in filas:
        ws.append(f)
    buf = io.BytesIO()
    wb.save(buf)
    contenido = buf.getvalue()
    datos, cobertura = carga_archivos.parse_archivos_con_cobertura([("dist.xlsx", contenido)])
    saneados, reporte, _ = excel_cobertura.preparar(datos, cobertura, lambda f: (f, {}), sanear)
    hs = controles_excel.analizar([("dist.xlsx", contenido)], saneados, reporte["excel"])
    return [h for h in hs if (h.get("evidencia") or {}).get("regla") == "valor_fuera_de_escala_columna"]


def test_participacion_chica_en_una_columna_que_suma_100_no_se_marca():
    filas = [["14-19", 20.0, 0.6], ["20-24", 20.7, 2.0], ["25-29", 16.4, 4.6], ["30-39", 17.0, 16.8],
             ["40-49", 6.6, 17.5], ["50-59", 6.0, 19.6], ["60-69", 5.5, 18.2], ["70 y más", 7.8, 20.7]]
    assert _analizar(filas) == []


def test_fuera_de_una_distribucion_el_valor_chico_se_sigue_marcando():
    filas = [["Programa A", 1520.0, 0.6], ["Programa B", 1480.0, 2010.0], ["Programa C", 1610.0, 1950.0],
             ["Programa D", 1590.0, 2120.0], ["Programa E", 1530.0, 1980.0], ["Programa F", 1555.0, 2040.0],
             ["Programa G", 1500.0, 1990.0], ["Programa H", 1575.0, 2075.0]]
    assert _analizar(filas)
